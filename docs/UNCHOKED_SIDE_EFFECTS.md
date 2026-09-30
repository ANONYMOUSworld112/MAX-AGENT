# MAX-AGENT: Unchoked Side-Effect Audit

> **Document Version**: 1.0.0  
> **Status**: VERIFIED against commit HEAD on branch `max/p0-baseline`  
> **Audience**: Master Implementation Agent & System Owner  
> **Authority**: Governed by Section 1-S2 & Section 13 of Master Engineering Specification v2  

---

## 1. Executive Summary

Per **Rule 1-S2**:
> *"All side effects pass through the ExecutionGateway (Section 13). No agent, worker, adapter caller or plugin performs side effects directly."*

And Section 13:
> *"Only adapter modules may import OS-level libraries. An automated AST test fails the build if `subprocess`, `os.system`, `os.startfile`, `pyautogui`, `pywinauto`, `keyboard`, `ctypes.windll`, `shutil.rmtree` (and equivalents found in the audit) are imported outside the adapter package."*

Below is the complete, comprehensive list of every code path in the current repository performing side effects directly outside any gateway or choke point. These code paths represent the exact migration backlog for Phase 1 and subsequent adapter phases.

---

## 2. Inventory of Unchoked Side-Effect Paths

| Module | Function / Class | Line Range | Side Effect Type | Mechanism Used | Target / Impact |
|---|---|---|---|---|---|
| `main.py` | `_Popen` | 6–15 | Process creation flags | Monkeypatches `subprocess.Popen` | All child processes globally |
| `actions/desktop.py` | `_execute_generated_code` | 83–102 | Arbitrary Code Execution | `exec(compile(code, "<max_desktop>", "exec"), sandbox)` | Runs LLM-generated code directly on host |
| `actions/desktop.py` | `set_wallpaper` | 154–205 | System Configuration Change | `ctypes.windll.user32.SystemParametersInfoW`, `subprocess.run(["osascript"...])`, `gsettings` | Alters desktop wallpaper |
| `actions/computer_control.py` | `_type` | 157–162 | Input Injection | `pyautogui.typewrite(text)` | Types arbitrary keystrokes into active window |
| `actions/computer_control.py` | `_smart_type` | 164–179 | Clipboard & Input Injection | `pyperclip.copy(text)`, `pyautogui.hotkey("ctrl", "v")` | Overwrites clipboard, injects paste keystrokes |
| `actions/computer_control.py` | `_click`, `_press`, `_hotkey`, `_move`, `_drag` | 181–221 | Mouse / Keyboard Injection | `pyautogui.click()`, `pyautogui.press()`, `pyautogui.moveTo()`, `pyautogui.dragTo()` | Injects physical mouse/key inputs |
| `actions/computer_control.py` | `_focus_window` | 258–305 | Window Focus Modification | `subprocess.run(["powershell", ... "AppActivate"])`, `osascript`, `wmctrl` | Forces OS window focus |
| `actions/computer_control.py` | `_screenshot` | 242–248 | Screen Observation Capture | `pyautogui.screenshot()`, file write to Desktop | Saves desktop screenshot to disk |
| `actions/open_app.py` | `_launch_windows` | 80–116 | Process Launch & Keyboard Injection | `subprocess.Popen(app_name, shell=True)`, `subprocess.Popen(f"start {app_name}")`, `pyautogui.press("win")`, `pyautogui.write()`, `pyautogui.press("enter")` | Launches executables or performs blind Start menu search |
| `actions/open_app.py` | `_launch_macos`, `_launch_linux` | 119–205 | Process Launch & GUI Injection | `subprocess.run(["open", ...])`, `subprocess.Popen()`, `pyautogui.hotkey()` | Launches external applications |
| `actions/dev_agent.py` | `_write_file` | 153–236 | Filesystem Write | `full_path.write_text(code)` on `Desktop/MaxProjects` | Writes arbitrary code files to disk |
| `actions/dev_agent.py` | `_install_dependencies` | 237–271 | Package Installation | `subprocess.run([sys.executable, "-m", "pip", "install"] + to_install)` | Installs external PyPI packages directly into host Python environment |
| `actions/dev_agent.py` | `_open_vscode` | 272–292 | Application Launch | `subprocess.Popen([cmd, str(project_dir)], shell=True)` | Launches VS Code via shell |
| `actions/dev_agent.py` | `_run_project` | 293–320 | Arbitrary Process Execution | `subprocess.run([sys.executable, entry_path])` | Executes newly generated code on host |
| `actions/dev_agent.py` | `_fix_file` | 370–425 | Filesystem Modification | `full_path.write_text(code)` | Overwrites code files during fix loop |
| `actions/file_controller.py` | `create_folder` | 134–146 | Filesystem Creation | `target.mkdir(parents=True, exist_ok=True)` | Creates directories on filesystem |
| `actions/file_controller.py` | `write_file` | 148–172 | Filesystem Write | `target.write_text(content)` | Writes/overwrites files |
| `actions/file_controller.py` | `move_file` | 174–206 | Filesystem Move | `shutil.move(str(src), str(dst))` | Moves files and directories |
| `actions/file_controller.py` | `delete_file` | 208–230 | Filesystem Deletion | `send2trash.send2trash(str(target))` | Sends files to Recycle Bin |
| `actions/file_processor.py` | `_process_code` (run) | 455–474 | Process Execution | `subprocess.run(["python", str(path)])` | Runs arbitrary Python script on host |
| `actions/file_processor.py` | `_process_video`, `_process_audio` | 585–715 | Media Process Execution | `subprocess.run(["ffmpeg", ...])` | Runs ffmpeg encoding/conversion processes |
| `actions/reminder.py` | `_write_notify_script` | 46–145 | Filesystem Script Generation | `script_path.write_text(script_body)` in `~/.MAX/reminders` | Writes executable Python scripts to disk |
| `actions/reminder.py` | `_schedule_windows` | 146–200 | OS Scheduled Task Creation | `subprocess.run(["schtasks", "/Create", ...])` | Registers persistent OS task in Windows Task Scheduler |
| `actions/reminder.py` | `_schedule_mac`, `_schedule_linux` | 202–275 | OS LaunchDaemon / Cron Creation | Plist file write + `launchctl load`, crontab write | Registers persistent OS autostart jobs |
| `actions/computer_settings.py` | `set_volume`, `mute_volume` | 56–96 | Audio Device Modification | `pycaw.AudioUtilities`, `pyautogui.press("volumeup")` | Alters host audio endpoint volume |
| `actions/computer_settings.py` | `set_brightness` | 98–145 | Hardware Display Configuration | `WMI.WmiMonitorBrightnessMethods`, `powershell`, `xrandr` | Modifies hardware monitor brightness |
| `actions/computer_settings.py` | `toggle_wifi` | 147–185 | Network Interface Modification | `netsh wlan disconnect/connect`, `nmcli`, `networksetup` | Disconnects or reconnects host network |
| `actions/computer_settings.py` | Window Management & Shortcuts | 245–370 | Keyboard Injection | `pyautogui.hotkey("alt", "f4")`, `pyautogui.press("f11")`, etc. | Closes, minimizes, or resizes windows |
| `actions/computer_settings.py` | `restart_computer`, `shutdown_computer` | 390–445 | System Power State Modification | `subprocess.run(["shutdown", ...])` | Shuts down or reboots the computer |
| `actions/send_message.py` | `send_message` | 150–265 | GUI Navigation & Input Injection | `pyautogui.press("win")`, `pyautogui.typewrite()`, `pyautogui.hotkey()` | Blindly navigates WhatsApp/Telegram and sends messages |
| `actions/youtube_video.py` | `play_youtube` | 120–220 | Browser Launch & Navigation | `webbrowser.open()`, `playwright` launch | Opens external browser sessions |
| `actions/flight_finder.py` | `search_flights` | 80–150 | Browser Navigation | `webbrowser.open()` | Launches default browser with travel search URLs |
| `actions/game_updater.py` | `launch_game` | 310–360 | Game Process Launch | `subprocess.Popen([game_path])` | Launches game executables |
| `core/wake_word.py` | `install_and_download` | 165–195 | Dependency Installation | `subprocess.run([sys.executable, "-m", "pip", "install", "openwakeword"])` | Installs pip packages at runtime |
| `core/installer.py` | `_pip` | 72–87 | Dependency Installation | `subprocess.run([sys.executable, "-m", "pip", "install", ...])` | Installs pip packages on demand |
| `core/max_infra/kill_switch.py`| `_terminate_pid` | 108–122 | Process Termination | `os.kill(pid, signal.SIGTERM)`, `subprocess.run(["taskkill", ...])` | Terminates OS processes |
| `dashboard/server.py` | `_ensure_network_access` | 99–175 | Firewall Modification | `subprocess.run(["netsh", "advfirewall", ...])`, `ShellExecuteW(runas)` | Modifies Windows Firewall rules with UAC elevation |

---

## 3. Migration Roadmap to ExecutionGateway

1. **Phase 1**:
   - Introduce `ExecutionGateway` and `PolicyEngine`.
   - Implement `ActionRequest` and `ActionResult` schemas.
   - Establish banned-import AST scanner test.
2. **Phase 4**:
   - Implement platform adapters (`WindowsDesktopAdapter`, `LinuxDesktopAdapter`, `MacDesktopAdapter`, `FakeDesktopAdapter`).
   - Move all direct OS calls (`pyautogui`, `ctypes`, `subprocess`) into platform adapter packages.
3. **Phase 5 to 9**:
   - Sequentially migrate actions (`open_app`, `media`, `reminders`, `terminal`, `OpenCode`) to execute solely via `ExecutionGateway.execute(ActionRequest)`.
