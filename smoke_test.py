"""
Run: python smoke_test.py — proves task -> risk gate -> agent -> log actually executes.
"""
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from core.orchestrator import Orchestrator
from core.platform.detector import RiskLevel
from core.risk_engine import RiskEngine
from tasks.task_system import Task



def fake_open_browser(task: Task) -> str:
    return "Chrome opened (simulated tool call for smoke test)"


def fake_delete_files(task: Task) -> str:
    return "3 files deleted (simulated tool call for smoke test)"


def auto_confirm(request):
    print(f"[AUTO-CONFIRM CALLBACK] Approved confirmation for: {request.description}")
    return True


def main() -> None:
    orch = Orchestrator(
        risk_engine=RiskEngine(confirmation_callback=auto_confirm),
        log_dir="logs/smoke_test",
    )
    orch.register_agent("browser", fake_open_browser)
    orch.register_agent("filesystem", fake_delete_files)


    low_task = Task(description="Open Chrome", agent="browser", risk=RiskLevel.LOW)
    high_task = Task(description="Delete 3 old log files", agent="filesystem", risk=RiskLevel.HIGH)

    orch.submit(low_task)
    orch.submit(high_task)
    orch.run_pending()

    print(f"LOW  task -> state={low_task.state.value:<10} result={low_task.result}")
    print(f"HIGH task -> state={high_task.state.value:<10} result={high_task.result}")
    print(
        f"\nCapability profile in effect: {orch.risk_engine.profile.os_family.value}, "
        f"max autonomous risk = {orch.risk_engine.profile.max_autonomous_risk.value}"
    )


if __name__ == "__main__":
    main()
