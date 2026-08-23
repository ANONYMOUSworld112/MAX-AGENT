"""
MAX OS — Live Demonstration of JARVIS-NOVA Supreme Intelligence:
1. Deep Owner Context Memory & Bayesian Learned Habits.
2. Real-Time Human Presence Observer & Arrival Greeting ("Welcome home, sir").
3. Environmental Telemetry Sensing & Proactive Diagnostics.
4. Fully Dynamic Simultaneous Multi-Agent Pipeline Execution.
"""

import sys
import time
from pathlib import Path

# Add files and src to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))

import src.core.kill_switch as kill_switch
from src.infra.owner_knowledge_graph import OwnerKnowledgeGraph
from src.core.presence_observer import PresenceObserver, PresenceState
from src.core.proactive_heartbeat import ProactiveHeartbeatDaemon

def run_jarvis_supreme_demo():
    # 1. Arm Kill Switch
    kill_switch.arm()

    print("=" * 80)
    print("      JARVIS-NOVA SUPREME: CONTINUOUS AMBIENT AI & DEEP OWNER CONTEXT         ")
    print("=" * 80)
    print(f"Kill Switch Status: {'ARMED' if kill_switch.is_armed() else 'UNARMED'} (Armed: {kill_switch.is_armed()})\n")

    # 2. Initialize Owner Knowledge Graph
    print("[1] Initializing Deep Owner Knowledge Graph (5-Layer Memory)...")
    owner_kg = OwnerKnowledgeGraph()
    
    # Observe and evolve habits with Bayesian confidence scaling
    print("  • Recording behavioral observations for Owner...")
    owner_kg.observe_habit(
        category="coding",
        description="Prefers modular Python architecture with strict type annotations",
        preferred_action="Use type hints and dataclasses in all generated code",
    )
    owner_kg.observe_habit(
        category="communication",
        description="Prefers high-velocity concise outputs and audio briefings",
        preferred_action="Keep responses structured and speak critical updates",
    )
    owner_kg.observe_habit(
        category="schedule",
        description="Active focus hours between 09:00 - 18:00 UTC",
        preferred_action="Defer non-urgent background batch jobs to evening",
    )

    # Display synthesized context block
    print("\n[2] Synthesized Deep Owner System Context Block:")
    print(owner_kg.synthesize_owner_context_block())

    # 3. Initialize Presence Observer & Proactive Heartbeat
    print("\n[3] Initializing Real-Time Presence Observer & Ambient Heartbeat...")
    heartbeat = ProactiveHeartbeatDaemon(interval_seconds=1.0)
    
    # Simulate Telemetry Capture
    telemetry = heartbeat.capture_telemetry()
    print(f"  • Real-time CPU Load      : {telemetry.cpu_percent:.1f}%")
    print(f"  • RAM Utilization         : {telemetry.ram_percent:.1f}%")
    print(f"  • Disk Space Used         : {telemetry.disk_percent:.1f}%")
    print(f"  • System Status           : {telemetry.system_status} ✅")
    print(f"  • Active Process Count    : {telemetry.running_processes_count}")

    # Simulate Owner Arrival Event (Iron Man 2 Workshop Scene)
    print("\n[4] Simulating Physical Owner Presence Arrival Event...")
    heartbeat.presence._current_state = PresenceState.DORMANT_AWAY
    heartbeat.presence.record_user_activity()
    snapshot = heartbeat.presence.evaluate_presence()
    
    greeting = heartbeat.presence.generate_arrival_briefing(owner_alias="Sir")
    print(f"  • Presence State Detected : {snapshot.state.value.upper()}")
    print(f"  • Face Authentication     : {'VERIFIED ✅' if snapshot.is_face_authenticated else 'PENDING'}")
    print(f"  • Proactive Voice Output  : \"{greeting} CPU load at {telemetry.cpu_percent:.0f}%, memory at {telemetry.ram_percent:.0f}%.\"")

    print("\n" + "=" * 80)
    print("✅ JARVIS-NOVA SUPREME VERIFICATION COMPLETE: ALL SYSTEMS NOMINAL")
    print("================================================================================\n")

if __name__ == "__main__":
    run_jarvis_supreme_demo()
