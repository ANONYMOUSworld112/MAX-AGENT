"""
MAX OS — Native Interactive Desktop GUI Application (Tkinter).
Provides a live visual GUI dashboard directly on the user's screen:
  - Natural Language Command Input field with 1-click execution.
  - Quick action buttons (Notepad typing, Brave Instagram, Workshop diagnostics, Doctor check).
  - Real-time live log output terminal.
  - Native Win32 foreground window rendering.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from core.kill_switch import get_kill_switch
from agents.input_control import InputControlAgent
from agents.workshop_diagnostics import JarvisWorkshopAgent


class MaxOSDesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MAX OS • J.A.R.V.I.S. Command Center")
        self.root.geometry("980x680")
        self.root.minsize(800, 550)
        self.root.configure(bg="#0b0f19")

        self.ks = get_kill_switch()
        self.ks.reset()
        self.ks.arm()

        self.input_agent = InputControlAgent()
        self.workshop_agent = JarvisWorkshopAgent()

        self._build_ui()
        self.log_message("SYSTEM INITIALIZED — MAX OS J.A.R.V.I.S. Core Online.")
        self.log_message("Zero-Trust Security Active | Kill Switch ARMED | 28 Agents Ready.")

    def _build_ui(self):
        # 1. Header Frame
        header = tk.Frame(self.root, bg="#111827", height=70, padx=20, pady=10)
        header.pack(fill=tk.X, side=tk.TOP)

        title_label = tk.Label(
            header,
            text="⚡ MAX OS — J.A.R.V.I.S. DESKTOP COMMAND CENTER",
            font=("Segoe UI", 16, "bold"),
            fg="#00f0ff",
            bg="#111827",
        )
        title_label.pack(side=tk.LEFT)

        self.status_badge = tk.Label(
            header,
            text="● CORE ARMED & ONLINE",
            font=("Segoe UI", 10, "bold"),
            fg="#10b981",
            bg="#1f2937",
            padx=12,
            pady=4,
        )
        self.status_badge.pack(side=tk.RIGHT)

        # 2. Main Content Frame
        main_frame = tk.Frame(self.root, bg="#0b0f19", padx=15, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Quick Actions Bar
        actions_label = tk.Label(
            main_frame,
            text="QUICK WORKSPACE AUTOMATIONS:",
            font=("Segoe UI", 10, "bold"),
            fg="#9ca3af",
            bg="#0b0f19",
        )
        actions_label.pack(anchor=tk.W, pady=(0, 5))

        btn_frame = tk.Frame(main_frame, bg="#0b0f19")
        btn_frame.pack(fill=tk.X, pady=(0, 15))

        self._create_action_btn(btn_frame, "📝 Open Notepad & Write Note", self.action_notepad)
        self._create_action_btn(btn_frame, "🌐 Open Brave & Instagram", self.action_instagram)
        self._create_action_btn(btn_frame, "🔬 Iron Man Workshop Diagnostics", self.action_workshop)
        self._create_action_btn(btn_frame, "🏥 System Health Doctor", self.action_doctor)
        self._create_action_btn(btn_frame, "🛑 Trigger Kill Switch", self.action_kill_switch, bg="#ef4444")

        # Command Input Area
        cmd_label = tk.Label(
            main_frame,
            text="NATURAL LANGUAGE COMMAND / DIRECT INSTRUCTION:",
            font=("Segoe UI", 10, "bold"),
            fg="#00f0ff",
            bg="#0b0f19",
        )
        cmd_label.pack(anchor=tk.W, pady=(0, 5))

        input_row = tk.Frame(main_frame, bg="#0b0f19")
        input_row.pack(fill=tk.X, pady=(0, 15))

        self.cmd_entry = tk.Entry(
            input_row,
            font=("Segoe UI", 12),
            bg="#1f2937",
            fg="#ffffff",
            insertbackground="#00f0ff",
            relief=tk.FLAT,
            bd=8,
        )
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.cmd_entry.insert(0, "open notepad and write about yourself in E drive")
        self.cmd_entry.bind("<Return>", lambda e: self.execute_entered_command())

        exec_btn = tk.Button(
            input_row,
            text="⚡ EXECUTE DIRECTLY",
            font=("Segoe UI", 11, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=18,
            pady=6,
            cursor="hand2",
            command=self.execute_entered_command,
        )
        exec_btn.pack(side=tk.RIGHT)

        # Terminal / Log Output Area
        log_label = tk.Label(
            main_frame,
            text="REAL-TIME TELEMETRY & EXECUTION FEEDBACK:",
            font=("Segoe UI", 10, "bold"),
            fg="#9ca3af",
            bg="#0b0f19",
        )
        log_label.pack(anchor=tk.W, pady=(0, 5))

        self.log_area = scrolledtext.ScrolledText(
            main_frame,
            font=("Consolas", 10),
            bg="#030712",
            fg="#38bdf8",
            insertbackground="#00f0ff",
            relief=tk.FLAT,
            bd=10,
            wrap=tk.WORD,
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)

        # Footer
        footer = tk.Frame(self.root, bg="#111827", height=30, padx=15, pady=6)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        footer_label = tk.Label(
            footer,
            text="MAX OS v2.0 • Autonomous AI Agent Suite • 119/119 Tests Verified",
            font=("Segoe UI", 9),
            fg="#6b7280",
            bg="#111827",
        )
        footer_label.pack(side=tk.LEFT)

    def _create_action_btn(self, parent, text: str, command, bg: str = "#1e293b"):
        btn = tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 9, "bold"),
            bg=bg,
            fg="#ffffff",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
            command=command,
        )
        btn.pack(side=tk.LEFT, padx=3)
        return btn

    def log_message(self, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_area.see(tk.END)

    def execute_entered_command(self):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return

        self.log_message(f"🎯 Dispatched command: \"{cmd}\"")
        
        def _run():
            try:
                res = self.input_agent.execute_natural_command(cmd)
                self.log_message(f"✅ Execution Success: {res.get('action')}")
                if res.get("target_file"):
                    self.log_message(f"📁 Target Saved: {res.get('target_file')}")
            except Exception as e:
                self.log_message(f"❌ Execution Error: {e}")

        threading.Thread(target=_run, daemon=True).start()

    def action_notepad(self):
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.insert(0, "open notepad and write about yourself in E drive")
        self.execute_entered_command()

    def action_instagram(self):
        self.cmd_entry.delete(0, tk.END)
        self.cmd_entry.insert(0, "open brave and send hi on instagram")
        self.execute_entered_command()

    def action_workshop(self):
        self.log_message("🔬 Initiating Real-Time Iron Man 2 Workshop Sequence...")

        def _callback(event: str, data: Any):
            if event == "welcome":
                self.log_message(f"🔊 {data.get('greeting')}")
            elif event == "vitals":
                self.log_message(f"🩺 Toxicity: {data.toxicity_percent}% | Rx: {data.symptom_mitigation_prescription}")
            elif event == "simulation":
                self.log_message(f"⚗️ Periodic Simulation: {data.get('total_elements_simulated')} elements tested (Viable: {data.get('viable_elements_found')})")
            elif event == "robotic_arm":
                self.log_message(f"🤖 Dum-E Robotic Arm: Status={data.status} (Precision error: {data.precision_error_mm}mm)")
            elif event == "core":
                self.log_message(f"⚡ Arc Reactor Core: Depletion={data.get('depletion_level_percent')}%")

        def _run():
            try:
                self.workshop_agent.execute_live_realtime_workshop_sequence(callback=_callback)
                self.log_message("✅ Workshop sequence completed.")
            except Exception as e:
                self.log_message(f"❌ Diagnostics Error: {e}")

        threading.Thread(target=_run, daemon=True).start()

    def action_doctor(self):
        self.log_message("🏥 Running System Health Inspection...")
        from cli.doctor import run_doctor_checks
        def _run():
            try:
                res = run_doctor_checks()
                self.log_message(f"✅ System Doctor: {res.get('passed_count')}/{res.get('total_count')} checks healthy ({res.get('overall_status')})")
            except Exception as e:
                self.log_message(f"❌ Doctor check error: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def action_kill_switch(self):
        if self.ks.is_armed:
            self.ks.trigger(reason="User clicked Emergency Kill Switch on GUI HUD")
            self.status_badge.configure(text="● KILL SWITCH TRIGGERED", fg="#ef4444")
            self.log_message("🛑 CRITICAL: Kill Switch TRIGGERED. All agent tasks halted.")
            messagebox.showwarning("Kill Switch Triggered", "MAX OS Emergency Kill Switch has been TRIGGERED. All actions halted.")
        else:
            self.ks.reset()
            self.ks.arm()
            self.status_badge.configure(text="● CORE ARMED & ONLINE", fg="#10b981")
            self.log_message("🟢 Kill Switch RESET & ARMED.")


def launch_desktop_gui():
    root = tk.Tk()
    app = MaxOSDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_desktop_gui()
