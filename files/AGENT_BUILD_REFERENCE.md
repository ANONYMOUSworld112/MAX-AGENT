# MAX OS — Agent Build Reference
## Terminal · Filesystem · Computer Control · Browser

Covers the four agents behind your three picks (Terminal+Filesystem was one
combined option). Each section: purpose, exact libraries/CLI tools with
install commands, how it plugs into the Phase 1 core you already have
(`RiskEngine`, `tools/interfaces.py`, `Orchestrator`), risk classification,
verification approach, and known pitfalls. This is a build reference, not
finished code — architecture snippets are illustrative, not the full backend.

---

## 0. Where these fit

All four implement an ABC already defined in `tools/interfaces.py`:
`TerminalTool`, `FilesystemTool`, `ComputerTool`, `BrowserTool`. An agent is
a thin function that calls its tool, wraps the result, and is registered
with `orchestrator.register_agent(name, executor)` — the pattern proven in
`smoke_test.py`. Nothing below should import `subprocess`, `xdotool`, or
`playwright` directly into an *agent* function — that belongs in the tool
backend, one layer down. This is the seam that keeps Section 4's platform
abstraction clean.

```
Task → Orchestrator._execute() → RiskEngine.enforce() → agent_executor(task)
                                                              │
                                                              ▼
                                                    calls a Tool interface
                                                              │
                                                              ▼
                                              concrete backend (this doc)
```

---

## 1. Terminal Agent

### 1.1 Purpose & features
Inspect, execute, parse output, diagnose errors, retry, chain commands.
Doc §18/§25 — this is also the backbone the Coding Agent will sit on top of
later (git, test runners, package managers all go through this).

### 1.2 Libraries & tools

| Tool | Use | Install |
|---|---|---|
| `asyncio.create_subprocess_exec` | Primary execution path — stdlib, no shell string parsing, avoids shell-injection class of bugs entirely | built-in |
| `shlex` | Tokenizing when a command genuinely must go through a shell (pipes, redirects) | built-in |
| `pexpect` | Interactive sessions (REPLs, prompts expecting input mid-command) | `pip install pexpect` |
| `psutil` | Process inspection, resource limits, killing runaway children | `pip install psutil` |

**Prefer `create_subprocess_exec` (argument list) over `create_subprocess_shell`
(string) by default.** Only drop to the shell form when the task genuinely
needs pipes/redirects — and when you do, that command should be classified
at least MEDIUM regardless of what it does, because shell-string execution
is where injection risk lives.

### 1.3 Architecture pattern

```python
# tools/backends/terminal_subprocess.py
import asyncio
from tools.interfaces import TerminalTool, CommandResult

class SubprocessTerminalTool(TerminalTool):
    async def run(self, command: str, timeout: float | None = 30) -> CommandResult:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError(f"'{command}' exceeded {timeout}s")
        return CommandResult(proc.returncode, stdout.decode(), stderr.decode())
```

Command **risk classification happens before this runs**, in the agent
function that calls it — not inside the tool. Keep the tool dumb; keep
policy in one place (see 1.4).

### 1.4 Risk classification

| Risk | Examples |
|---|---|
| LOW | `ls`, `cat`, `git status`, `ps`, `df -h`, `echo` |
| MEDIUM | `git commit`, `pip install`, `npm install`, `mkdir`, `mv` within project dirs |
| HIGH | `rm` (non-recursive, user files), `chmod`/`chown` outside project dir, `kill`, `git push --force`, `systemctl restart` |
| CRITICAL | `rm -rf /`, `dd`, `mkfs`, `shutdown`/`reboot`, any `sudo`, `passwd`, `iptables -F`, `> /dev/sd*`, `curl \| bash` |

Implement this as a classifier function the agent calls before submitting
the task risk — a deny/allow regex list is a reasonable v1; don't try to
make it "smart" (no LLM-based risk classification for this — deterministic
pattern matching is the point, since the LLM's own output is one of the
things this gate exists to check).

### 1.5 Verification & recovery
Exit code + stderr inspection, not "the call didn't throw." On non-zero
exit: capture stderr, let the Coding/Recovery agent decide retry vs.
alternate command vs. surface to user. Cap retries (doc §51 — max retries,
time limit, failure budget).

### 1.6 Security
Never build commands via naive string concatenation of user/LLM-generated
text into a shell string — that's the injection surface. Sandboxed test
directory for anything destructive during development (doc §63).

---

## 2. Filesystem Agent

### 2.1 Purpose & features
Read, write, copy, move, rename, delete, search. First real demoable
skill: `organize_downloads` (doc §15 example — PDFs → Documents/PDFs,
images → Pictures, archives → Archives).

### 2.2 Libraries & tools

| Tool | Use | Install |
|---|---|---|
| `pathlib` | All path handling — stdlib | built-in |
| `shutil` | copy/move/rmtree | built-in |
| `send2trash` | Recoverable delete (moves to OS trash instead of `unlink`) — use this as the *default* delete path | `pip install Send2Trash` |
| `watchdog` | Filesystem event monitoring — feeds `FILE_CREATED`/`FILE_CHANGED` into your `EventBus` | `pip install watchdog` |
| `python-magic` | File-type detection by content, not just extension (a renamed `.exe` won't fool it) | `pip install python-magic` + `sudo apt install libmagic1` |
| `hashlib` | Checksum-based verification after copy/move | built-in |

### 2.3 Architecture pattern

```python
# tools/backends/filesystem_local.py
import shutil
from pathlib import Path
from send2trash import send2trash
from tools.interfaces import FilesystemTool

class LocalFilesystemTool(FilesystemTool):
    def read(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def write(self, path: str, content: bytes) -> None:
        Path(path).write_bytes(content)

    def move(self, src: str, dst: str) -> None:
        shutil.move(src, dst)

    def delete(self, path: str) -> None:
        send2trash(path)  # recoverable — see rollback note below

    def search(self, root: str, pattern: str) -> list[str]:
        return [str(p) for p in Path(root).rglob(pattern)]
```

**Rollback pattern (doc §13):** before any batch operation, record
`{original_path: new_path}` for every file moved. On failure mid-batch,
replay the map in reverse. Since `delete()` uses `send2trash`, "rollback"
for deletes is "restore from trash" — which is also why delete is still
HIGH risk even though it's recoverable: recoverable isn't the same as safe
to do unattended.

### 2.4 Risk classification

| Risk | Examples |
|---|---|
| LOW | read, list, search |
| MEDIUM | write new file, copy, create folder, move within user dirs |
| HIGH | delete (even via `send2trash`), overwrite existing file, bulk rename |
| CRITICAL | delete outside `$HOME`, anything touching system directories, permanent purge (bypassing trash) |

### 2.5 Verification
File-count and checksum comparison, not "the API call returned." For
`organize_downloads`: verify destination file count matches source
selection count, and spot-check a hash on at least one moved file.

---

## 3. Computer Control Agent (xdotool)

### 3.1 Purpose & features
Mouse, keyboard, screenshots, window management — the primitives doc §8
lists. This is the one where your detector's platform read genuinely
matters: **the `detector.py` self-test on this container resolved
`input_backend="xdotool"` only because `$DISPLAY`/`$WAYLAND_DISPLAY` were
unset in this sandbox — re-run it on your real dev machine before trusting
that value**, since a Wayland session will correctly resolve to `ydotool`
instead, and the two are not interchangeable.

### 3.2 Libraries & tools

| Tool | Use | Install |
|---|---|---|
| `xdotool` | Mouse/keyboard/window control on X11 — CLI, wrap via subprocess | `sudo apt install xdotool` |
| `wmctrl` | Window listing, activation, workspace switching (X11) | `sudo apt install wmctrl` |
| `ydotool` + `ydotoold` | X11-equivalent for Wayland — needs its daemon running with input-group permissions | `sudo apt install ydotool` |
| `mss` | Fast cross-platform screenshot capture, region/window support | `pip install mss` |
| `Pillow` | Image handling for screenshots (diffing, cropping) | `pip install Pillow` |
| PyGObject + AT-SPI2 | Accessibility tree — preferred over pixel/vision per doc §9/UFO | `sudo apt install at-spi2-core gir1.2-atspi-2.0` + `pip install PyGObject` |
| `pytesseract` + `tesseract-ocr` | OCR fallback when neither AT-SPI nor a known selector is available | `pip install pytesseract` + `sudo apt install tesseract-ocr` |

**Tool-selection hierarchy in practice for this agent** (doc §3): try
AT-SPI2 element lookup first (semantic — "the Save button" not "pixel
412,290"), fall back to `xdotool`/`wmctrl` coordinate or keyboard-shortcut
control, fall back to OCR/vision only when nothing else identifies the
target. UI-TARS (Alibaba, open-source, 7B model, purpose-built for UI
coordinate prediction — see prior turn's research) is worth benchmarking
as that last-resort vision path instead of a general VLM, if/when you get
there — it's specifically trained for this rather than doing double duty.

### 3.3 Architecture pattern

```python
# tools/backends/computer_xdotool.py
import subprocess
from tools.interfaces import ComputerTool

class XdotoolComputerTool(ComputerTool):
    def move_mouse(self, x: int, y: int) -> None:
        subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=True)

    def click(self, x=None, y=None, button="left") -> None:
        if x is not None and y is not None:
            self.move_mouse(x, y)
        btn = {"left": "1", "middle": "2", "right": "3"}[button]
        subprocess.run(["xdotool", "click", btn], check=True)

    def type_text(self, text: str) -> None:
        subprocess.run(["xdotool", "type", "--clearmodifiers", text], check=True)

    def press_keys(self, *keys: str) -> None:
        subprocess.run(["xdotool", "key", "+".join(keys)], check=True)

    def list_windows(self) -> list[dict]:
        out = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, check=True)
        return [{"raw": line} for line in out.stdout.splitlines()]
```

`screenshot()` implementation uses `mss` directly (Python, no subprocess
needed) rather than shelling out to `scrot`/`gnome-screenshot`.

### 3.4 Risk classification

| Risk | Examples |
|---|---|
| LOW | screenshot, list windows, non-clicking mouse move |
| MEDIUM | click inside a known/focused app, type into a focused field, switch windows |
| HIGH | blind coordinate click in an unfamiliar app (no AT-SPI/vision confirmation the target is correct) |
| — | A click is never CRITICAL *by itself* — but it inherits the risk of whatever it triggers. Clicking "confirm" on a CRITICAL filesystem/terminal action must trip that action's CRITICAL gate, not the click's own LOW/MEDIUM default. Wire this by having Computer Control agents check "does this click resolve to a known dangerous UI target" via the accessibility tree label, not just treat all clicks the same. |

### 3.5 Verification — the closed loop, literally
This is the one agent where doc §9's `OBSERVE → THINK → ACT → OBSERVE →
VERIFY` isn't optional flavor text — skipping it is *the* documented
failure mode (UFO/Stonic-class tools break silently on OS UI changes).
Every action: screenshot or AT-SPI read before, act, screenshot/AT-SPI read
after, diff. Never chain more than one unverified action.

---

## 4. Browser Agent (Browser Use)

### 4.1 Purpose & features
Navigate, search, extract, click, type, scroll, upload, download, tabs,
page inspection, research workflows (doc §23).

### 4.2 Libraries & tools

| Tool | Use | Install |
|---|---|---|
| `browser-use` | LLM-driven browser agent loop, built on Playwright | `pip install browser-use` (needs **Python ≥3.11**) |
| `playwright` | Underlying browser automation — also usable directly, no LLM loop, for deterministic known-shape tasks | `pip install playwright` then `playwright install chromium --with-deps` |

Verified current usage pattern (from `browser-use` PyPI docs, checked this
session):

```python
import asyncio
from browser_use import Agent, ChatAnthropic

async def main():
    agent = Agent(
        task="Find the current price of X on example.com",
        llm=ChatAnthropic(model="claude-sonnet-4-6"),
    )
    await agent.run()

asyncio.run(main())
```

### 4.3 Two execution modes — pick per task, not globally

Doc §3's tool-selection hierarchy applies *inside* this agent too:

- **Deterministic Playwright script** — when the page/workflow shape is
  known (a specific site's login flow, a specific form). Faster, cheaper,
  no LLM tokens per action, no risk of the agent misreading the page.
- **`browser-use` Agent loop** — when the task is exploratory/ambiguous
  ("find the best laptop under ₹80,000 and compare specs" — doc's own
  example). This is where the LLM-per-step cost is actually worth paying.

Default to the first; escalate to the second only when the task can't be
scripted deterministically. This mirrors the same "cheapest reliable method
wins" principle as Computer Control's AT-SPI-before-vision rule.

### 4.4 Risk classification

| Risk | Examples |
|---|---|
| LOW | navigate, read/extract page text, search |
| MEDIUM | click links/buttons, fill forms, scroll, open tabs |
| HIGH | download files, login flows, upload files |
| CRITICAL (override, not default) | "Purchase," "delete account," "transfer funds," "send message/email" style actions — **hard-code a keyword/URL-pattern override that forces these to CRITICAL regardless of the agent's generic MEDIUM/HIGH default.** A browser agent that can technically click "Place Order" needs that specific action pinned to the same human-confirm gate as `rm -rf`, not left to whatever risk tier the page happened to get classified at. |

### 4.5 Architecture note
Same `BrowserTool` interface from `tools/interfaces.py` wraps either
execution mode — `navigate()`/`click_selector()`/`extract_text()` can be
backed by raw Playwright calls; a higher-level `research()`-style method
(not yet in the interface) would be the natural place to hand off to
`browser-use`'s `Agent`.

---

## 5. Combined dependency manifest

```
# requirements.txt additions for these four agents
browser-use>=0.7
playwright>=1.62
pexpect>=4.9
psutil>=6.0
Send2Trash>=1.8
watchdog>=4.0
python-magic>=0.4
mss>=9.0
Pillow>=10.0
PyGObject>=3.48
pytesseract>=0.3.10
```

```bash
# apt packages (Ubuntu — matches your detected environment)
sudo apt install xdotool wmctrl at-spi2-core gir1.2-atspi-2.0 \
                 libmagic1 tesseract-ocr scrot

# Wayland only — skip if your session is X11 (check detector.py output)
sudo apt install ydotool wl-clipboard grim

# Playwright browser binaries (separate from the pip package)
playwright install chromium --with-deps
```

---

## 6. Build order & integration checklist

1. `pip install` the manifest above; `playwright install chromium --with-deps`.
2. Implement `SubprocessTerminalTool` and `LocalFilesystemTool` for real
   (the snippets above are close to complete — mainly need the remaining
   `TerminalTool`/`FilesystemTool` abstract methods filled in).
3. Write the command-risk classifier (1.4) as its own module — this is
   policy, test it in isolation before wiring it to anything that executes.
4. `orchestrator.register_agent("terminal", ...)`, `register_agent("filesystem", ...)` — rerun `smoke_test.py`-style checks with real commands in a throwaway test directory, never against real files first.
5. Re-run `detector.py` on your actual dev machine (not this sandbox) to
   confirm `xdotool` vs `ydotool` before building `XdotoolComputerTool`.
6. Build the AT-SPI element-lookup path *before* the coordinate-click path
   — doing it in this order forces you to actually use the accessibility
   tree rather than defaulting to pixel coordinates because it's easier.
7. Browser Agent: start with a raw Playwright script for one concrete task
   you actually need, only add the `browser-use` Agent loop once that
   works — validates the interface before paying for the LLM-loop version.
8. Every agent's first real test target should be something with a
   trivially checkable outcome (file exists on disk, terminal exit code 0,
   a specific window title appears, a specific page title loads) — per
   doc §20, "the code imports" is not a passing test.
