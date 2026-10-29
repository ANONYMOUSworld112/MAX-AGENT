"""Handler for read_file tool."""
from pathlib import Path


def handle(params: dict) -> dict:
    file_path = params.get("file_path")
    if not file_path:
        return {"error": "Missing required argument 'file_path'"}

    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    if not path.is_file():
        return {"error": f"Path is not a regular file: {file_path}"}

    max_lines = int(params.get("max_lines", 200))
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        truncated = len(lines) > max_lines
        selected_lines = lines[:max_lines]
        return {
            "file_path": str(path),
            "total_lines": len(lines),
            "lines_read": len(selected_lines),
            "truncated": truncated,
            "content": "\n".join(selected_lines),
        }
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}
