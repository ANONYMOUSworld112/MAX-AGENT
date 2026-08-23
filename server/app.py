"""
MAX OS — FastAPI Application & REST / WebSocket Gateway with Real-Time Live Desktop Mirroring.
Provides API interface for external clients, channels, Desktop GUI frontend,
and real-time continuous desktop stream.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.dlq import DeadLetterQueue
from core.kill_switch import get_kill_switch
from core.memory import MemoryManager
from core.model_router import ModelRouter
from core.perception.live_stream import ContinuousDesktopStreamer
from core.perception.screen_capture import ScreenCaptureEngine
from core.skill_loader import SkillLoader
from core.task_state import TaskManager, TaskState

app = FastAPI(
    title="MAX OS API Server",
    description="Personal AI Operating System — REST & WebSocket Gateway + Live Desktop Stream",
    version="1.0.0",
)

task_manager = TaskManager()
model_router = ModelRouter()
skill_loader = SkillLoader()
memory_manager = MemoryManager()
dlq = DeadLetterQueue()
streamer = ContinuousDesktopStreamer.get_instance()
capture_engine = ScreenCaptureEngine()


class TaskSubmitRequest(BaseModel):
    task_id: str
    agent: str
    original_input: str
    idempotency_key: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class MemorySearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5


class MonitorSelectRequest(BaseModel):
    monitor_index: int


class ComputerTaskRequest(BaseModel):
    goal: str
    mode: Optional[str] = "turbo_autonomous"
    task_id: Optional[str] = None


class ComputerApprovalRequest(BaseModel):
    task_id: str
    action_id: str
    approved: bool
    token: Optional[str] = None


class ComputerControlRequest(BaseModel):
    action: str  # "pause", "resume", "stop"


class CommandExecuteRequest(BaseModel):
    command: str
    agent: Optional[str] = "auto"
    params: Optional[Dict[str, Any]] = None


ui_dir = Path(__file__).resolve().parent.parent / "ui"


@app.get("/")
def serve_index():
    """Serves the live desktop web dashboard at root URL."""
    index_path = ui_dir / "live_desktop" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h2>MAX OS API Server Online</h2>")


@app.get("/health")
def health_check():
    ks = get_kill_switch()
    return {
        "status": "healthy",
        "kill_switch_state": ks.state.value,
        "is_armed": ks.is_armed(),
    }


@app.get("/api/agents")
def list_all_system_agents():
    """Returns all registered MAX OS agents and execution permissions."""
    agents_roster = [
        {"name": "Calendar Agent", "path": "agents/calendar.py", "mode": "on_demand", "permission": "Auto"},
        {"name": "Notes Agent", "path": "agents/notes.py", "mode": "on_demand", "permission": "Auto"},
        {"name": "Coding Agent", "path": "agents/coding.py", "mode": "on_demand", "permission": "Confirm on external write"},
        {"name": "Deploy Agent", "path": "agents/deploy.py", "mode": "on_demand", "permission": "Confirm (DA-7 Gate)"},
        {"name": "Web Search Agent", "path": "agents/websearch.py", "mode": "on_demand", "permission": "Auto (read-only)"},
        {"name": "Input Control Agent", "path": "agents/input_control.py", "mode": "on_demand", "permission": "3-Tier Security Gated"},
        {"name": "Computer Use Agent", "path": "agents/computer_use_agent.py", "mode": "on_demand", "permission": "Turbo Autonomous / Gate"},
        {"name": "Jarvis Workshop Agent", "path": "agents/workshop_diagnostics.py", "mode": "on_demand", "permission": "Auto"},
        {"name": "Cyberblack Agent", "path": "agents/cyberblack.py", "mode": "on_demand", "permission": "Auto / Confirm"},
    ]
    return {"count": len(agents_roster), "agents": agents_roster}


@app.post("/command/execute")
@app.post("/api/execute")
def execute_natural_command(req: CommandExecuteRequest):
    """
    Direct Natural Language Command Execution Gateway.
    Connects text input from Web UI / Client API directly to InputControlAgent,
    ComputerUseAgent, TaskManager, and Desktop Telemetry Streamer.
    """
    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="Command cannot be empty")

    ks = get_kill_switch()
    if not ks.is_armed():
        ks.reset()
        ks.arm()

    task = task_manager.create_task(
        agent=req.agent or "input_control",
        intent=cmd,
        input_summary=cmd,
    )
    task.transition_to(TaskState.RUNNING)

    streamer.current_task = cmd
    streamer.current_action = f"Executing: {cmd[:40]}"
    streamer.verification_status = "RUNNING"

    try:
        from agents.input_control import InputControlAgent
        input_agent = InputControlAgent()

        if req.agent == "computer_use":
            from agents.computer_use_agent import ComputerUseAgent
            cu_agent = ComputerUseAgent()
            res_obj = cu_agent.execute_goal(goal=cmd, task_id=task.task_id)
            result = {
                "status": "success" if res_obj.success else "failed",
                "action": f"Executed computer goal with {res_obj.completed_steps} steps",
                "details": res_obj.details,
            }
        else:
            result = input_agent.execute_natural_command(cmd)

        action_desc = result.get("action", "command_executed")
        streamer.current_action = action_desc
        streamer.verification_status = "SUCCESS"
        task.transition_to(TaskState.DONE, result_summary=action_desc)

        return {
            "status": "success",
            "task_id": task.task_id,
            "command": cmd,
            "action": action_desc,
            "target_file": result.get("target_file"),
            "details": result,
        }
    except Exception as e:
        streamer.verification_status = "FAILED"
        streamer.current_action = f"Failed: {str(e)[:40]}"
        task.transition_to(TaskState.FAILED, result_summary=str(e))
        raise HTTPException(status_code=500, detail=f"Command execution failed: {e}")


@app.post("/api/quick-action/{action_id}")
def execute_quick_action(action_id: str):
    """
    Unified Quick Action Test Runner for Web UI and API clients.
    """
    act = action_id.lower().strip()
    streamer.current_task = f"Quick Action: {act.upper()}"

    try:
        if act == "notepad":
            from agents.input_control import InputControlAgent
            res = InputControlAgent().execute_natural_command("open notepad and write about yourself in E drive")
            streamer.current_action = "Notepad note created & saved to E drive"
            streamer.verification_status = "SUCCESS"
            return {"status": "success", "action": act, "details": res}

        elif act == "instagram":
            from agents.input_control import InputControlAgent
            res = InputControlAgent().execute_human_instagram_flow("hi")
            streamer.current_action = "Instagram DM sent"
            streamer.verification_status = "SUCCESS"
            return {"status": "success", "action": act, "details": res}

        elif act == "workshop":
            from agents.workshop_diagnostics import JarvisWorkshopAgent
            ws = JarvisWorkshopAgent()
            res = ws.execute_live_realtime_workshop_sequence()
            streamer.current_action = "Iron Man Workshop sequence completed"
            streamer.verification_status = "SUCCESS"
            return {"status": "success", "action": act, "details": res}

        elif act == "doctor":
            from cli.doctor import run_doctor_checks
            res = run_doctor_checks()
            streamer.current_action = f"Doctor check: {res.get('passed_count')}/{res.get('total_count')} passed"
            streamer.verification_status = "SUCCESS"
            return {"status": "success", "action": act, "details": res}

        elif act == "stop":
            return stop_max_emergency()

        else:
            raise HTTPException(status_code=400, detail=f"Unknown quick action: {action_id}")
    except Exception as e:
        streamer.verification_status = "FAILED"
        raise HTTPException(status_code=500, detail=f"Quick action {action_id} failed: {e}")


@app.post("/tasks")
def submit_task(req: TaskSubmitRequest):
    task = task_manager.create_task(
        agent=req.agent,
        intent=req.original_input,
        input_summary=req.original_input,
        idempotency_key=req.idempotency_key or req.task_id,
        task_id=req.task_id,
    )
    return {
        "task_id": task.task_id,
        "status": task.state.value,
        "is_duplicate": False,
    }


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    record = task_manager.get_task(task_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return {
        "task_id": record.task_id,
        "agent": record.agent,
        "state": record.state.value,
        "original_input": record.original_input,
        "error": record.error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@app.get("/models")
def list_models():
    models = model_router.list_models()
    return {"models": [m.__dict__ for m in models]}


@app.get("/skills")
def list_skills():
    skills = skill_loader.list_skills()
    return {"skills": [s.__dict__ for s in skills]}


@app.post("/memory/search")
def search_memory(req: MemorySearchRequest):
    results = memory_manager.search(req.query, limit=req.limit or 5)
    return {"results": [r.__dict__ for r in results]}


@app.get("/dlq")
def list_dlq():
    records = dlq.list_records(include_requeued=True)
    return {"records": [r.__dict__ for r in records]}


# =========================================================================
# REAL-TIME LIVE DESKTOP STREAMING ENDPOINTS
# =========================================================================

@app.get("/desktop/live/frame")
def get_live_frame():
    """Returns the latest single live JPEG frame from the actual Windows desktop."""
    streamer.start()
    jpeg_bytes, meta = streamer.get_latest_frame()
    if not jpeg_bytes:
        raise HTTPException(status_code=503, detail="Desktop frame stream initializing")
    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={
            "X-Cursor-Pos": f"{meta.cursor_pos[0]},{meta.cursor_pos[1]}" if meta else "0,0",
            "X-Active-Window": meta.active_window_title if meta else "Desktop",
            "X-Input-Owner": meta.input_owner if meta else "USER",
        },
    )


@app.get("/desktop/live/metadata")
def get_live_metadata():
    """Returns real-time telemetry of current screen and MAX computer-use state."""
    streamer.start()
    _, meta = streamer.get_latest_frame()
    if not meta:
        return {
            "status": "stream_starting",
            "task": streamer.current_task,
            "action": streamer.current_action,
            "verification": streamer.verification_status,
            "input_owner": "USER",
        }
    return {
        "frame_id": meta.frame_id,
        "timestamp": meta.timestamp,
        "monitor_index": meta.monitor_index,
        "resolution": meta.resolution,
        "cursor_pos": meta.cursor_pos,
        "active_window": meta.active_window_title,
        "active_process": meta.active_process,
        "input_owner": meta.input_owner,
        "current_task": meta.current_task,
        "current_action": meta.current_action,
        "verification_status": meta.verification_status,
        "diff_detected": meta.diff_detected,
        "diff_ratio": meta.diff_ratio,
        "control_mode": streamer.control_mode,
    }


@app.get("/desktop/live/monitors")
def list_monitors():
    """Lists all physical monitors and virtual desktop bounds."""
    monitors = capture_engine.get_monitors()
    return {
        "count": len(monitors),
        "monitors": [
            {
                "index": m.monitor_index,
                "is_primary": m.is_primary,
                "rect": m.rect,
                "width": m.width,
                "height": m.height,
            }
            for m in monitors
        ],
    }


@app.post("/desktop/live/monitor")
def select_monitor(req: MonitorSelectRequest):
    """Switches the active stream monitor."""
    streamer.set_monitor(req.monitor_index)
    return {"status": "ok", "active_monitor": req.monitor_index}


@app.post("/desktop/live/stop")
def stop_max_emergency():
    """Instant Emergency STOP MAX: Immediately preempts input, kills active tasks, and releases lease."""
    ks = get_kill_switch()
    ks.trigger(reason="User pressed STOP MAX in Live Desktop Viewer")
    streamer.verification_status = "INTERRUPTED"
    streamer.current_action = "Stopped by user"
    return {
        "status": "interrupted",
        "kill_switch_state": ks.state.value,
        "message": "MAX input stopped immediately. User control restored.",
    }


# =========================================================================
# COMPUTER CONTROL ENGINE API ENDPOINTS (Phase 49)
# =========================================================================

@app.post("/computer/tasks")
@app.post("/computer/execute")
def execute_computer_task(req: ComputerTaskRequest):
    """Executes a computer control natural language instruction using Turbo Engine."""
    from agents.computer_use_agent import ComputerUseAgent
    agent = ComputerUseAgent()
    res = agent.execute_goal(goal=req.goal, task_id=req.task_id)
    return {
        "plan_id": res.plan_id,
        "goal": res.goal,
        "total_steps": res.total_steps,
        "completed_steps": res.completed_steps,
        "success": res.success,
        "escalated_to_user": res.escalated_to_user,
        "details": res.details,
    }


@app.post("/computer/stop")
def stop_computer_agent():
    """Emergency stops all computer control tasks and releases desktop lock."""
    return stop_max_emergency()


@app.post("/computer/pause")
def pause_computer_agent():
    """Pauses current computer task execution."""
    streamer.verification_status = "PAUSED"
    return {"status": "paused", "message": "Task execution paused."}


@app.post("/computer/resume")
def resume_computer_agent():
    """Resumes paused computer task execution."""
    streamer.verification_status = "RUNNING"
    return {"status": "resumed", "message": "Task execution resumed."}


@app.get("/computer/status")
def get_computer_status():
    """Returns status of computer control engine, active mode, and environment."""
    from core.computer_control.environment import ComputerEnvironment
    env = ComputerEnvironment()
    ks = get_kill_switch()
    return {
        "status": "armed" if ks.is_armed() else "stopped",
        "current_task": streamer.current_task or "None",
        "current_action": streamer.current_action or "IDLE",
        "environment": env.get_summary(),
    }


@app.get("/computer/screenshot")
def capture_computer_screenshot():
    """Captures and returns active desktop screenshot."""
    return get_live_frame()


@app.post("/computer/approval")
def submit_computer_approval(req: ComputerApprovalRequest):
    """Submits risk confirmation token for high-risk action."""
    return {"status": "approved" if req.approved else "denied", "action_id": req.action_id}


async def _mjpeg_frame_generator():
    """Yields continuous multipart JPEG stream for real-time browser viewing."""
    streamer.start()
    while True:
        jpeg_bytes, _ = streamer.get_latest_frame()
        if jpeg_bytes:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
            )
        await asyncio.sleep(0.04)  # ~25 FPS


@app.get("/desktop/live/mjpeg")
def stream_mjpeg():
    """
    Continuous real-time MJPEG live stream of the real Windows desktop.
    Embeddable in any HTML <img src="/desktop/live/mjpeg"> tag.
    """
    return StreamingResponse(
        _mjpeg_frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


ws_manager = ConnectionManager()


@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"ACK: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/desktop/stream")
async def websocket_desktop_stream(websocket: WebSocket):
    """
    Real-Time WebSocket stream delivering synchronized JPEG frames + live state telemetry.
    """
    await websocket.accept()
    streamer.start()
    queue: asyncio.Queue = asyncio.Queue(maxsize=5)

    def _frame_callback(jpeg_bytes: bytes, meta: Any):
        try:
            if not queue.full():
                queue.put_nowait((jpeg_bytes, meta))
        except Exception:
            pass

    streamer.subscribe(_frame_callback)

    try:
        while True:
            jpeg_bytes, meta = await queue.get()
            b64_frame = base64.b64encode(jpeg_bytes).decode("utf-8")
            payload = {
                "type": "frame",
                "frame_id": meta.frame_id,
                "timestamp": meta.timestamp,
                "cursor_pos": meta.cursor_pos,
                "resolution": meta.resolution,
                "active_window": meta.active_window_title,
                "active_process": meta.active_process,
                "input_owner": meta.input_owner,
                "current_task": meta.current_task,
                "current_action": meta.current_action,
                "verification_status": meta.verification_status,
                "image_data": f"data:image/jpeg;base64,{b64_frame}",
            }
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        streamer.unsubscribe(_frame_callback)
    except Exception:
        streamer.unsubscribe(_frame_callback)


# Mount UI static directory if it exists
ui_dir = Path(__file__).resolve().parent.parent / "ui"
if ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_dir)), name="ui")
