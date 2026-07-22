import os
import re
import webbrowser
import subprocess
import time
import threading
import signal
import json
from datetime import datetime

import config_manager as cfgmod

from core_engine import (
    speak_blocking as speak,
    stream_ollama_sentences,
    get_time_text,
    get_system_summary,
)

LOG_FILE = "day2_command_log.json"


def log_event(command, action_type, result):
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "command": command,
        "action_type": action_type,
        "result": result,
    }
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []
        data.append(log_entry)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[Log Error]: {e}")


APPS = {
    "terminal": "gnome-terminal",
    "calculator": "gnome-calculator",
    "files": "nautilus",
    "text editor": "gedit",
    "settings": "gnome-control-center",
    "libreoffice writer": "libreoffice --writer",
    "libreoffice calc": "libreoffice --calc",
    "vlc": "vlc",
    "music player": "rhythmbox",
    "browser": "firefox",
    "camera": "cheese",
    "system monitor": "gnome-system-monitor",
}

PROCESS_NAMES = {
    "terminal": "gnome-terminal",
    "calculator": "gnome-calculator",
    "files": "nautilus",
    "text editor": "gedit",
    "settings": "gnome-control-center",
    "libreoffice": "libreoffice",
    "vlc": "vlc",
    "music player": "rhythmbox",
    "browser": "firefox",
    "camera": "cheese",
    "system monitor": "gnome-system-monitor",
}

def apps_list():
    for i in APPS:
        print(i)


def print_list():
    print("""
MAX — commands:
 - open <app>                (e.g., open terminal)
 - close <app>               (e.g., close calculator)
 - list apps
 - search <query>            (e.g., search Python tutorial)
 - <query> on youtube        (e.g., song on youtube)
 - remind me in <time> to <task> (e.g., remind me in 10 minutes to check mail)
 - run <command>             (e.g., run ls -l)
 - what / define / explain <query>
 - system status / cpu / memory / time
 - exit
 -
""")


def safe_run(cmd):
    try:
        subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        speak(f"Error running command: {e}")


def open_app(command: str) -> bool:
    for name, cmd in APPS.items():
        if name in command:
            speak(f"Opening {name}")
            safe_run(cmd)
            log_event(command, "open_app", f"Opened {name}")
            return True
    return False


def close_app(command: str) -> bool:
    for name, proc_name in PROCESS_NAMES.items():
        if name in command:
            res = subprocess.run(["pgrep", "-x", proc_name], capture_output=True, text=True)
            if res.stdout.strip():
                os.system(f"pkill -x {proc_name} >/dev/null 2>&1")
                speak(f"Closed {name}")
                log_event(command, "close_app", f"Closed {name}")
            else:
                speak(f"{name} is not running.")
                log_event(command, "close_app", f"{name} not running")
            return True
    return False


def perform_search(command: str) -> bool:
    if "youtube" in command:
        query = re.sub(r"(search|on|youtube)", " ", command, flags=re.IGNORECASE).strip()
        if query:
            speak(f"Searching {query} on YouTube")
            webbrowser.open(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
            log_event(command, "search_youtube", f"Searched YouTube for '{query}'")
            return True
    if "google" in command or "search" in command:
        query = re.sub(r"(search|on|google)", " ", command, flags=re.IGNORECASE).strip()
        if query:
            speak(f"Searching {query} on Google")
            webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
            log_event(command, "search_google", f"Searched Google for '{query}'")
            return True
    if "wikipedia" in command:
        query = re.sub(r"(search|on|wikipedia)", " ", command, flags=re.IGNORECASE).strip()
        if query:
            speak(f"Searching {query} on Wikipedia")
            webbrowser.open(f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}")
            log_event(command, "search_wikipedia", f"Searched Wikipedia for '{query}'")
            return True
    return False


def reminder_timer(delay, message):
    time.sleep(delay)
    speak(f"Reminder: {message}")
    log_event(message, "reminder_triggered", f"Reminder: {message}")


def handle_reminder(command):
    match = re.search(r"remind me in (\d+)\s*(seconds?|minutes?|hours?)\s*to (.+)", command)
    if not match:
        return False
    amount = int(match.group(1))
    unit = match.group(2)
    task = match.group(3)
    if "hour" in unit:
        delay = amount * 3600
    elif "min" in unit:
        delay = amount * 60
    else:
        delay = amount
    speak(f"Okay, I\u2019ll remind you in {amount} {unit} to {task}.")
    log_event(command, "set_reminder", f"Reminder set for {amount} {unit} to {task}")
    t = threading.Thread(target=reminder_timer, args=(delay, task))
    t.daemon = True
    t.start()
    return True


def execute_terminal_command(command):
    cmd = command.replace("run ", "", 1).strip()
    if not cmd:
        speak("Please tell me what to run.")
        return
    speak(f"Running command: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout.strip() or result.stderr.strip()
        if output:
            print(f"[Terminal Output]:\n{output}\n")
            speak("Command executed successfully.")
            log_event(command, "terminal", output)
        else:
            speak("Command executed.")
            log_event(command, "terminal", "Command executed without output")
    except Exception as e:
        speak(f"Error: {e}")
        log_event(command, "terminal_error", str(e))


def dynamic_action(command: str):
    c = command.lower().strip()

    if "remind me" in c:
        if handle_reminder(c):
            return

    if c.startswith("run "):
        execute_terminal_command(c)
        return

    if "open " in c:
        if open_app(c):
            return
        if perform_search(c):
            return
        speak("I couldn\u2019t find the app you requested.")
        log_event(c, "open_app_failed", "Unknown app")
        return

    if "close " in c:
        if close_app(c):
            return
        speak("I couldn\u2019t find a matching app to close.")
        log_event(c, "close_app_failed", "Unknown app")
        return

    if "list apps" in c:
        apps_list()
        return

    if any(x in c for x in ("time", "current time")):
        result = get_time_text()
        speak(result)
        log_event(c, "system_time", result)
        return

    if any(x in c for x in ("cpu", "memory", "ram", "system info", "system status")):
        result = get_system_summary()
        speak(result)
        log_event(c, "system_info", result)
        return

    if "search" in c or "on youtube" in c or "on google" in c or "wikipedia" in c:
        if perform_search(c):
            return

    cfg = cfgmod.load_config()
    if cfg and cfg["ai"]["providers"].get(cfg["ai"]["default_provider"], {}).get("api_key"):
        provider_label = cfg["ai"]["default_provider"]
        ch = input(f"Use AI ({provider_label})? [Y/n]: ").strip().lower()
    else:
        ch = input("Enter YES if you want response from local AI (Ollama), NO to skip: ").strip().lower()

    if ch in ("", "y", "yes"):
        prompt = f"Answer concisely: {command}"
        full_response = ""
        for sentence in stream_ollama_sentences(prompt):
            if sentence:
                speak(sentence)
                full_response += sentence + " "
                time.sleep(0.05)
        log_event(command, "ai_response", full_response.strip())
    else:
        speak("Skipping AI response.")
        log_event(command, "ai_skipped", "User skipped AI response.")


def handle_sigint(sig, frame):
    print("\n[Max]: Interruption detected. Type a new command to continue.")


signal.signal(signal.SIGINT, handle_sigint)


def main():
    speak("MAX COMMANDS STARTED ")
    print("__________________________")
    try:
        while True:
            typed = input("\nYou: ").strip()
            if not typed:
                continue
            if typed.lower() in ("list", "help"):
                print_list()
                continue
            if typed.lower() in ("exit", "quit", "stop"):
                log_event(typed, "session_end", "User exited assistant.")
                break
            dynamic_action(typed)
    except KeyboardInterrupt:
        handle_sigint(None, None)
    finally:
        print("Session closed.")


if __name__ == "__main__":
    main()
