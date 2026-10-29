"""Handler for write_note tool."""
from pathlib import Path


def handle(params: dict) -> dict:
    note_name = params.get("note_name")
    content = params.get("content")
    if not note_name:
        return {"error": "Missing required argument 'note_name'"}
    if content is None:
        return {"error": "Missing required argument 'content'"}

    # Base workspace / notes folder
    base_dir = Path(__file__).resolve().parent.parent.parent
    notes_dir = base_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    # Normalize filename
    safe_name = Path(note_name).name
    if not safe_name.endswith((".txt", ".md")):
        safe_name = f"{safe_name}.txt"

    target_file = notes_dir / safe_name
    append_mode = bool(params.get("append", False))

    try:
        if append_mode and target_file.exists():
            existing = target_file.read_text(encoding="utf-8")
            new_content = existing + "\n" + content
            target_file.write_text(new_content, encoding="utf-8")
        else:
            target_file.write_text(content, encoding="utf-8")

        return {
            "success": True,
            "file_path": str(target_file),
            "bytes_written": len(content.encode("utf-8")),
            "note_name": safe_name,
            "mode": "append" if append_mode else "overwrite",
        }
    except Exception as e:
        return {"error": f"Failed to write note: {e}"}
