#!/usr/bin/env python3
import os
import json
import shutil
import datetime
import zipfile

import config_manager as cfgmod
from core_engine import ask_ai_once

LOG_FILE = "command_logs.json"


def log_command(command_type, details):
    entry = {
        "time": str(datetime.datetime.now()),
        "command": command_type,
        "details": details
    }
    data = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                data = json.load(f)
        except:
            data = []
    data.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)


def summarize_text_with_ai(text):
    try:
        return ask_ai_once(f"Summarize clearly:\n{text}")
    except Exception as e:
        return f"[AI Summary Error] {e}"


def safe_path(path):
    path = path.strip()
    path = os.path.expanduser(path)
    return os.path.abspath(path)


def list_files_in_folder(path):
    path = safe_path(path)
    log_command("list_files", {"path": path})
    if not os.path.exists(path):
        return "Folder not found."
    items = os.listdir(path)
    return "\n".join(items) if items else "Folder is empty."


def read_file(path):
    path = safe_path(path)
    log_command("read_file", {"path": path})
    if not os.path.exists(path):
        return "File not found."
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        try:
            with open(path, "r", errors="ignore") as f:
                return f.read()
        except:
            return "Unable to read file."


def write_file(path, content):
    path = safe_path(path)
    log_command("write_file", {"path": path, "content": content})
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return "File created/updated."
    except:
        return "Error writing file."


def create_empty_file(path):
    path = safe_path(path)
    log_command("create_file", {"path": path})
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
    try:
        open(path, "w").close()
        return "Blank file created."
    except:
        return "Error creating file."


def delete_file(path):
    path = safe_path(path)
    log_command("delete_file", {"path": path})
    if not os.path.exists(path):
        return "File not found."
    try:
        os.remove(path)
        return "File deleted."
    except:
        return "Error deleting file."


def file_info(path):
    path = safe_path(path)
    log_command("file_info", {"path": path})
    if not os.path.exists(path):
        return "File not found."
    size = os.path.getsize(path)
    created = datetime.datetime.fromtimestamp(os.path.getctime(path))
    modified = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    return f"""
File Info:
- Path: {path}
- Size: {size} bytes
- Created: {created}
- Modified: {modified}
"""


def search_file(name, root="."):
    name = name.strip().lower()
    root = safe_path(root)
    log_command("search_file", {"name": name})
    matches = []
    for folder, _, files in os.walk(root):
        for f in files:
            if name in f.lower():
                matches.append(os.path.join(folder, f))
    if not matches:
        return "No matches found."
    if len(matches) > 100:
        return f"Found {len(matches)} results. Showing first 100:\n" + "\n".join(matches[:100])
    return "\n".join(matches)


def create_folder(path):
    path = safe_path(path)
    log_command("create_folder", {"path": path})
    try:
        os.makedirs(path, exist_ok=True)
        return "Folder created."
    except:
        return "Error creating folder."


def delete_folder(path):
    path = safe_path(path)
    log_command("delete_folder", {"path": path})
    if not os.path.exists(path):
        return "Folder not found."
    try:
        shutil.rmtree(path)
        return "Folder deleted."
    except:
        return "Failed deleting folder."


def move_file(src, dst):
    src = safe_path(src)
    dst = safe_path(dst)
    log_command("move_file", {"from": src, "to": dst})
    try:
        folder = os.path.dirname(dst)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        shutil.move(src, dst)
        return "File moved."
    except:
        return "Move failed."


def copy_file(src, dst):
    src = safe_path(src)
    dst = safe_path(dst)
    log_command("copy_file", {"from": src, "to": dst})
    try:
        folder = os.path.dirname(dst)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        shutil.copy2(src, dst)
        return "File copied."
    except:
        return "Copy failed."


def zip_folder(path, output):
    path = safe_path(path)
    output = safe_path(output).replace(".zip", "")
    log_command("zip_folder", {"path": path, "output": output})
    try:
        shutil.make_archive(output, "zip", path)
        return "Folder zipped."
    except:
        return "Zip failed."


def unzip_file(zip_path, extract_to):
    zip_path = safe_path(zip_path)
    extract_to = safe_path(extract_to)
    log_command("unzip_file", {"zip": zip_path, "to": extract_to})
    try:
        os.makedirs(extract_to, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_to)
        return "Zip extracted."
    except:
        return "Unzip failed."


def summarize_file(path):
    path = safe_path(path)
    log_command("summarize_file", {"path": path})
    if not os.path.exists(path):
        return "File not found."
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except:
        return "Cannot summarize non-text file."
    return summarize_text_with_ai(text)


def get_help_text():
    return """
MAX AI \u2013 File Commands

Folder:
  create folder <path>
  delete folder <path>
  list files in <path>
  list

File:
  read file <path>
  write file <path> : <content>
  create file <path>
  delete file <path>
  file info <path>
  search file <name>
  summarize file <path>

Move/Copy/Zip:
  move file <src> to <dest>
  copy file <src> to <dest>
  zip folder <path> to <output>
  unzip <zipfile> to <folder>

System:
  help
  exit
"""


def handle_file_command(command):
    command = command.strip()
    lower = command.lower()

    if lower == "list":
        return list_files_in_folder(".")
    if lower == "help":
        return get_help_text()
    if lower.startswith("list files in"):
        p = command[len("list files in"):].strip()
        return list_files_in_folder(p)
    if lower.startswith("read file"):
        p = command[len("read file"):].strip()
        return read_file(p)
    if lower.startswith("write file"):
        if ":" not in command:
            return "Use: write file <path> : <content>"
        path, content = command.split(":", 1)
        path = path.replace("write file", "").strip()
        return write_file(path, content.strip())
    if lower.startswith("create file"):
        p = command[len("create file"):].strip()
        return create_empty_file(p)
    if lower.startswith("delete file"):
        p = command[len("delete file"):].strip()
        return delete_file(p)
    if lower.startswith("file info"):
        p = command[len("file info"):].strip()
        return file_info(p)
    if lower.startswith("search file"):
        name = command[len("search file"):].strip()
        return search_file(name)
    if lower.startswith("create folder"):
        p = command[len("create folder"):].strip()
        return create_folder(p)
    if lower.startswith("delete folder"):
        p = command[len("delete folder"):].strip()
        return delete_folder(p)
    if "move file" in lower and " to " in lower:
        src, dst = command.replace("move file", "", 1).split(" to ")
        return move_file(src.strip(), dst.strip())
    if "copy file" in lower and " to " in lower:
        src, dst = command.replace("copy file", "", 1).split(" to ")
        return copy_file(src.strip(), dst.strip())
    if "zip folder" in lower and " to " in lower:
        folder, out = command.replace("zip folder", "", 1).split(" to ")
        return zip_folder(folder.strip(), out.strip())
    if lower.startswith("unzip") and " to " in lower:
        z, out = command.replace("unzip", "", 1).split(" to ")
        return unzip_file(z.strip(), out.strip())
    if lower.startswith("summarize file"):
        p = command[len("summarize file"):].strip()
        return summarize_file(p)

    return "Unknown command. Type 'help'."


if __name__ == "__main__":
    print("MAX AI \u2013 Offline File Manager")
    while True:
        try:
            cmd = input(" > ").strip()
            if cmd.lower() in ("exit", "quit"):
                break
            if cmd:
                print(handle_file_command(cmd))
        except KeyboardInterrupt:
            print("\nGoodbye.")
            break
