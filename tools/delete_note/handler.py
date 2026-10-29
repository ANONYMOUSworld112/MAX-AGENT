"""Handler for delete_note tool (T2 Sensitive)."""
from pathlib import Path


def handle(params: dict) -> dict:
    note_name = params.get("note_name")
    if not note_name:
        return {"error": "Missing required argument 'note_name'"}

    base_dir = Path(__file__).resolve().parent.parent.parent
    notes_dir = base_dir / "notes"
    safe_name = Path(note_name).name
    if not safe_name.endswith((".txt", ".md")):
        safe_name = f"{safe_name}.txt"

    target_file = notes_dir / safe_name
    if not target_file.exists():
        return {"error": f"Note '{safe_name}' not found at {target_file}"}

    try:
        target_file.unlink()
        return {"success": True, "deleted_note": safe_name}
    except Exception as e:
        return {"error": f"Failed to delete note: {e}"}
