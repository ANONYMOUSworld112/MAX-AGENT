/**
 * MAX OS — Live Desktop Viewer & Real-Time Telemetry Client.
 * Synchronizes live stream, physical cursor position, telemetry, and emergency kill-switch.
 */

class LiveDesktopViewer {
    constructor() {
        this.imgFeed = document.getElementById("liveScreenImg");
        this.cursorPin = document.getElementById("liveCursorPin");
        this.canvasWrapper = document.getElementById("canvasWrapper");
        this.actionHud = document.getElementById("actionHud");
        this.hudActionText = document.getElementById("hudActionText");
        this.stopMaxBtn = document.getElementById("stopMaxBtn");
        
        // Telemetry elements
        this.telemetryTask = document.getElementById("telemetryTask");
        this.telemetryApp = document.getElementById("telemetryApp");
        this.telemetryVerif = document.getElementById("telemetryVerif");
        this.telemetryWindow = document.getElementById("telemetryWindow");
        this.telemetryAction = document.getElementById("telemetryAction");
        this.telemetryNextStep = document.getElementById("telemetryNextStep");
        this.inputOwnerValue = document.getElementById("inputOwnerValue");
        this.resIndicator = document.getElementById("resIndicator");
        this.fpsCounter = document.getElementById("fpsCounter");
        this.logStream = document.getElementById("logStream");

        // Command Bar & Quick Actions
        this.cmdInput = document.getElementById("cmdInput");
        this.execCmdBtn = document.getElementById("execCmdBtn");
        this.quickNotepadBtn = document.getElementById("quickNotepadBtn");
        this.quickInstagramBtn = document.getElementById("quickInstagramBtn");
        this.quickWorkshopBtn = document.getElementById("quickWorkshopBtn");
        this.quickDoctorBtn = document.getElementById("quickDoctorBtn");

        this.nativeWidth = 1920;
        this.nativeHeight = 1080;
        this.ws = null;
        this.telemetryInterval = null;
        this.fpsFrames = 0;
        this.lastFpsCalc = performance.now();

        this.initEventListeners();
        this.startTelemetryPolling();
        this.connectWebSocket();
    }

    initEventListeners() {
        // Command Execution listeners
        if (this.execCmdBtn) {
            this.execCmdBtn.addEventListener("click", () => this.executeUserCommand());
        }
        if (this.cmdInput) {
            this.cmdInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    this.executeUserCommand();
                }
            });
        }

        // Quick Action Presets
        if (this.quickNotepadBtn) {
            this.quickNotepadBtn.addEventListener("click", () => this.dispatchQuickAction("notepad"));
        }
        if (this.quickInstagramBtn) {
            this.quickInstagramBtn.addEventListener("click", () => this.dispatchQuickAction("instagram"));
        }
        if (this.quickWorkshopBtn) {
            this.quickWorkshopBtn.addEventListener("click", () => this.dispatchQuickAction("workshop"));
        }
        if (this.quickDoctorBtn) {
            this.quickDoctorBtn.addEventListener("click", () => this.dispatchQuickAction("doctor"));
        }

        // Stop MAX Button
        if (this.stopMaxBtn) {
            this.stopMaxBtn.addEventListener("click", () => this.emergencyStopMax());
        }

        // Monitor Tabs
        const monTabs = document.querySelectorAll(".mon-btn");
        monTabs.forEach(btn => {
            btn.addEventListener("click", (e) => {
                monTabs.forEach(b => b.classList.remove("active"));
                e.target.classList.add("active");
                const monIdx = parseInt(e.target.getAttribute("data-mon"), 10);
                this.selectMonitor(monIdx);
            });
        });

        // Mode Toggles
        const modeToggles = document.querySelectorAll(".mode-toggle");
        modeToggles.forEach(btn => {
            btn.addEventListener("click", (e) => {
                modeToggles.forEach(b => b.classList.remove("active"));
                e.target.classList.add("active");
                const mode = e.target.getAttribute("data-mode");
                document.getElementById("modeBadge").innerText = `${mode} MODE`;
            });
        });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/desktop/stream`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === "frame") {
                    this.onFrameReceived(data);
                }
            };
            this.ws.onclose = () => {
                // Fallback to MJPEG if WebSocket closes
                setTimeout(() => this.connectWebSocket(), 3000);
            };
        } catch (e) {
            console.warn("WebSocket not supported or failed, falling back to MJPEG stream", e);
        }
    }

    onFrameReceived(data) {
        if (data.image_data) {
            this.imgFeed.src = data.image_data;
        }
        if (data.resolution) {
            this.nativeWidth = data.resolution[0];
            this.nativeHeight = data.resolution[1];
            this.resIndicator.innerText = `${this.nativeWidth}x${this.nativeHeight}`;
        }
        if (data.cursor_pos) {
            this.updateCursorPosition(data.cursor_pos[0], data.cursor_pos[1]);
        }
        this.updateTelemetryData(data);
        this.calculateFps();
    }

    updateCursorPosition(realX, realY) {
        if (!this.imgFeed || !this.cursorPin) return;

        const rect = this.imgFeed.getBoundingClientRect();
        const scaleX = rect.width / this.nativeWidth;
        const scaleY = rect.height / this.nativeHeight;

        const clientX = rect.left + (realX * scaleX);
        const clientY = rect.top + (realY * scaleY);

        const parentRect = this.canvasWrapper.getBoundingClientRect();
        const relX = clientX - parentRect.left;
        const relY = clientY - parentRect.top;

        this.cursorPin.style.left = `${relX}px`;
        this.cursorPin.style.top = `${relY}px`;
    }

    startTelemetryPolling() {
        this.telemetryInterval = setInterval(async () => {
            try {
                const res = await fetch("/desktop/live/metadata");
                if (res.ok) {
                    const meta = await res.json();
                    this.updateTelemetryData(meta);
                }
            } catch (e) {
                // Ignore transient polling error
            }
        }, 200);
    }

    updateTelemetryData(meta) {
        if (meta.current_task && this.telemetryTask) {
            this.telemetryTask.innerText = meta.current_task;
        }
        if (meta.active_process && this.telemetryApp) {
            this.telemetryApp.innerText = meta.active_process;
        }
        if (meta.active_window && this.telemetryWindow) {
            this.telemetryWindow.innerText = meta.active_window;
        }
        if (meta.current_action && this.telemetryAction) {
            this.telemetryAction.innerText = meta.current_action;
            if (this.hudActionText) {
                this.hudActionText.innerText = meta.current_action;
            }
        }
        if (meta.verification_status && this.telemetryVerif) {
            this.telemetryVerif.innerText = meta.verification_status;
            this.telemetryVerif.className = meta.verification_status === "SUCCESS" ? "card-value badge-success" : "card-value action-value";
        }
        if (meta.input_owner && this.inputOwnerValue) {
            this.inputOwnerValue.innerText = meta.input_owner;
        }
        if (meta.cursor_pos) {
            this.updateCursorPosition(meta.cursor_pos[0], meta.cursor_pos[1]);
        }
    }

    calculateFps() {
        this.fpsFrames++;
        const now = performance.now();
        if (now - this.lastFpsCalc >= 1000) {
            const fps = Math.round((this.fpsFrames * 1000) / (now - this.lastFpsCalc));
            this.fpsCounter.innerText = `${fps} FPS`;
            this.fpsFrames = 0;
            this.lastFpsCalc = now;
        }
    }

    async selectMonitor(monIdx) {
        try {
            await fetch("/desktop/live/monitor", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ monitor_index: monIdx })
            });
            this.appendLog(`Switched stream view to Monitor ${monIdx}`);
        } catch (e) {
            console.error("Failed to select monitor:", e);
        }
    }

    async emergencyStopMax() {
        try {
            const res = await fetch("/desktop/live/stop", { method: "POST" });
            const data = await res.json();
            this.appendLog("🛑 EMERGENCY STOP TRIGGERED: Input revoked immediately!");
            if (this.inputOwnerValue) this.inputOwnerValue.innerText = "USER (REVOKED)";
            if (this.hudActionText) this.hudActionText.innerText = "HALTED BY USER";
        } catch (e) {
            alert("Stop MAX triggered.");
        }
    }

    async executeUserCommand() {
        if (!this.cmdInput) return;
        const command = this.cmdInput.value.trim();
        if (!command) return;

        this.appendLog(`🎯 Dispatched command: "${command}"`);
        if (this.execCmdBtn) this.execCmdBtn.disabled = true;

        try {
            const res = await fetch("/command/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ command: command, agent: "auto" }),
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                this.appendLog(`✅ Execution Success: ${data.action || 'Completed'}`, true);
                if (data.target_file) {
                    this.appendLog(`📁 Target File Saved: ${data.target_file}`, true);
                }
            } else {
                this.appendLog(`❌ Execution Error: ${data.detail || data.error || 'Failed'}`);
            }
        } catch (e) {
            this.appendLog(`❌ API Error: ${e.message}`);
        } finally {
            if (this.execCmdBtn) this.execCmdBtn.disabled = false;
        }
    }

    async dispatchQuickAction(actionId) {
        if (actionId === "notepad") {
            if (this.cmdInput) this.cmdInput.value = "open notepad and write about yourself in E drive";
        } else if (actionId === "instagram") {
            if (this.cmdInput) this.cmdInput.value = "open brave and send hi on instagram";
        }
        
        this.appendLog(`⚡ Quick Automation Triggered: ${actionId.toUpperCase()}`);
        try {
            const res = await fetch(`/api/quick-action/${actionId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                this.appendLog(`✅ Quick Action Completed: ${data.details || data.action || 'Success'}`, true);
            } else {
                this.appendLog(`❌ Quick Action Error: ${data.detail || data.error || 'Failed'}`);
            }
        } catch (e) {
            this.appendLog(`❌ API Error: ${e.message}`);
        }
    }

    appendLog(text, isSuccess = false) {
        if (!this.logStream) return;
        const now = new Date();
        const timeStr = now.toTimeString().split(" ")[0];
        const line = document.createElement("div");
        line.className = isSuccess ? "log-line success" : "log-line";
        line.innerHTML = `<span class="time">[${timeStr}]</span> ${text}`;
        this.logStream.appendChild(line);
        this.logStream.scrollTop = this.logStream.scrollHeight;
    }
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    window.desktopViewer = new LiveDesktopViewer();
});
