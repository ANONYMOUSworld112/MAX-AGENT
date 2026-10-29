"""
friday_cli.py — Phase 1 Interactive CLI Chat for FRIDAY.

Run:
    python friday_cli.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.agent_loop import AgentLoop
from core.config_loader import get_config
from core.events import AuditWriter, EventBus
from core.llm.client import UnifiedLLMClient
from core.max_infra.state_db import StateDB
from core.tool_registry import ToolRegistry


def cli_confirmation_handler(tool_name: str, arguments: dict) -> bool:
    """Prompt the user in the CLI for Tier 2 confirmation."""
    print(f"\n[⚠️  SECURITY ALERT — TIER 2 SENSITIVE ACTION]")
    print(f"Tool:      {tool_name}")
    print(f"Arguments: {arguments}")
    sys.stdout.write("Authorize this action, boss? (y/N): ")
    sys.stdout.flush()
    try:
        ans = input().strip().lower()
        allowed = ans in ("y", "yes")
        if allowed:
            print("Action authorized.\n")
        else:
            print("Action denied.\n")
        return allowed
    except (EOFError, KeyboardInterrupt):
        print("\nAction aborted.\n")
        return False


def cli_preamble_handler(preamble: str) -> None:
    """Print the pre-action announcement."""
    print(f"\n[FRIDAY ACTION] {preamble}")


async def main() -> None:
    base_dir = Path(__file__).resolve().parent
    config = get_config()

    print("=" * 65)
    print(f"  F.R.I.D.A.Y. — Personal AI Operating Layer (Phase 1 CLI)")
    print(f"  Identity: {config.assistant.name} | Addressing: {config.assistant.title}")
    print(f"  Primary LLM: {config.llm.primary_provider} ({config.llm.primary_model})")
    print(f"  Budget Cap: ${config.llm.monthly_budget_usd:.2f} USD")
    print("=" * 65)

    # Initialize subsystem
    event_bus = EventBus()
    state_db = StateDB()
    audit_writer = AuditWriter(state_db=state_db)
    tool_registry = ToolRegistry(
        tools_dir=base_dir / "tools",
        event_bus=event_bus,
        audit_writer=audit_writer,
    )
    llm_client = UnifiedLLMClient(config=config)

    from core.kill_switch import is_armed, rearm, trigger_kill_switch, WatchdogHotkeyListener
    watchdog = WatchdogHotkeyListener()
    watchdog.start()

    persona_file = base_dir / "config" / "persona.md"
    persona_prompt = persona_file.read_text(encoding="utf-8") if persona_file.exists() else "You are FRIDAY."

    agent = AgentLoop(
        llm_client=llm_client,
        tool_registry=tool_registry,
        persona_prompt=persona_prompt,
        event_bus=event_bus,
    )

    print("\nSystem online. Commands: 'tools', 'budget', 'kill', 'rearm', 'quit'.")
    print("Safety Hotkey: [Ctrl+Alt+Shift+K] halts all operations immediately.\n")

    while True:
        try:
            armed_str = "ARMED" if is_armed() else "DISARMED"
            sys.stdout.write(f"\n[{armed_str}] {config.assistant.title} > ")
            sys.stdout.flush()
            user_input = input().strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print(f"Standing down, {config.assistant.title}.")
                break

            if user_input.lower() == "kill":
                trigger_kill_switch("Manual kill command issued by boss in CLI")
                continue

            if user_input.lower() == "rearm":
                rearm()
                continue

            if user_input.lower() == "tools":
                print("\nRegistered Tools:")
                for t in tool_registry.list_tools():
                    print(f"  • {t.name:<18} [{t.permission_tier}] — {t.description}")
                continue

            if user_input.lower() == "budget":
                spend = llm_client.budget_tracker.current_spend
                cap = config.llm.monthly_budget_usd
                print(f"\nBudget Status: ${spend:.4f} / ${cap:.2f} USD spent this month.")
                continue

            # Run agent loop
            response = await agent.run(
                user_input=user_input,
                confirm_callback=cli_confirmation_handler,
                preamble_callback=cli_preamble_handler,
            )

            print(f"\nFRIDAY: {response}")

        except (KeyboardInterrupt, EOFError):
            print(f"\nInterrupted. Standing down, {config.assistant.title}.")
            break
        except Exception as e:
            print(f"\n[System Error]: {e}")


if __name__ == "__main__":
    asyncio.run(main())
