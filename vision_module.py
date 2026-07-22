#!/usr/bin/env python3
import os
import sys
import json
import time
import datetime
import threading
import traceback

import config_manager as cfgmod

try:
    import cv2
    import numpy as np
    import pyautogui
    import pytesseract
    from ultralytics import YOLO
    from pyzbar import pyzbar
    import requests
except Exception as e:
    print("Missing dependency:", e)
    print("Install required packages: opencv-python, numpy, pyautogui, pytesseract, ultralytics, pyzbar, requests")

HOME = os.path.expanduser("~")
BASE_DIR = os.path.join(HOME, "day3_data")
SNAP_DIR = os.path.join(BASE_DIR, "snaps")
TEXT_DIR = os.path.join(BASE_DIR, "texts")
LOG_PATH = os.path.join(BASE_DIR, "data_log.json")
COMMANDS_PATH = os.path.join(BASE_DIR, "commands_map.json")
YOLO_WEIGHTS = os.path.join(os.getcwd(), "yolov8n.pt")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(SNAP_DIR, exist_ok=True)
os.makedirs(TEXT_DIR, exist_ok=True)

GREEN = "\033[1;92m"
YELLOW = "\033[1;93m"
RED = "\033[1;91m"
CYAN = "\033[1;96m"
RESET = "\033[0m"


def info(display_msg: str, speak_msg: str = None):
    print(f"{CYAN}INFO:{RESET} {display_msg}")
    if speak_msg:
        speak_blocking(speak_msg)

def success(display_msg: str, speak_msg: str = None):
    print(f"{GREEN}SUCCESS:{RESET} {display_msg}")
    if speak_msg:
        speak_blocking(speak_msg)

def warning(display_msg: str, speak_msg: str = None):
    print(f"{YELLOW}WARNING:{RESET} {display_msg}")
    if speak_msg:
        speak_blocking(speak_msg)

def error(display_msg: str, speak_msg: str = None):
    print(f"{RED}ERROR:{RESET} {display_msg}")
    if speak_msg:
        speak_blocking(speak_msg)


def speak_blocking(text: str):
    text = (text or "").strip()
    if not text:
        return
    try:
        cfgmod.speak_text(text)
    except Exception as e:
        print("TTS error:", e)


def append_log(entry: dict):
    logs = []
    try:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                logs = json.loads(content) if content else []
    except Exception:
        logs = []
    logs.insert(0, entry)
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Failed to write log:", e)


_default_commands = {
    "detect": ["detect", "object detection", "analyze objects", "detect objects"],
    "ocr": ["ocr", "read screen text", "read the text","read text", "extract text"],
    "qr": ["qr", "barcode", "scan code", "scan qr"],
    "snap": ["take snap", "capture photo", "take photo", "camera snap", "snap"],
    "screenshot": ["take screenshot", "screen capture", "capture screen", "screenshot"],
    "list": ["list", "help", "commands"],
    "exit": ["exit", "quit", "close", "stop"]
}

def ensure_commands_json():
    try:
        if not os.path.exists(COMMANDS_PATH):
            with open(COMMANDS_PATH, "w", encoding="utf-8") as f:
                json.dump(_default_commands, f, indent=2)
    except Exception as e:
        print("Failed to create commands JSON:", e)

def load_commands_map():
    try:
        with open(COMMANDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _default_commands

def match_command(user_text: str):
    lowered = user_text.lower()
    cmap = load_commands_map()
    for key, aliases in cmap.items():
        for a in aliases:
            if a in lowered:
                return key
    return None


_yolo = None
def maybe_load_yolo():
    global _yolo
    if _yolo is not None:
        return _yolo
    try:
        if os.path.exists(YOLO_WEIGHTS):
            info(f"Loading YOLO weights from {YOLO_WEIGHTS} ...")
            _yolo = YOLO(YOLO_WEIGHTS)
            success("YOLO model loaded.")
        else:
            warning(f"YOLO weights not found at {YOLO_WEIGHTS}. Detection will be disabled.")
            _yolo = None
    except Exception as e:
        error(f"Failed to load YOLO model: {e}")
        _yolo = None
    return _yolo


def open_camera(index=1):
    try:
        cap = cv2.VideoCapture(index)
        time.sleep(0.1)
        if not cap or not cap.isOpened():
            return None
        return cap
    except Exception:
        return None

def save_image_bgr(bgr, prefix="snap"):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{prefix}_{ts}.png"
    path = os.path.join(SNAP_DIR, fname)
    try:
        cv2.imwrite(path, bgr)
    except Exception as e:
        error(f"Failed saving image: {e}")
    return path


def detect_objects_task(seconds=10, min_conf=0.35):
    yolo = maybe_load_yolo()
    if yolo is None:
        error("Object detection model not available.", "Object detection is not available because the model is missing.")
        append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "detect", "result": "no_model"})
        return
    cap = open_camera(1)
    if cap is None:
        error("Camera not detected.", "Camera not found. Please connect a camera and try again.")
        append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "detect", "result": "no_camera"})
        return

    info(f"Starting object detection for {int(seconds)} seconds...", "Starting object detection.")
    start = time.time()
    detected = set()
    win = "MAX - Object Detection (10s)"
    try:
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win, 960, 640)
    except Exception:
        pass

    while time.time() - start < seconds:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue
        try:
            res = yolo(frame, verbose=False)
        except Exception as e:
            error(f"YOLO inference error: {e}", "Detection failed due to an internal error.")
            break
        if res and len(res) > 0:
            for box in res[0].boxes:
                try:
                    conf = float(box.conf[0])
                except Exception:
                    conf = float(box.conf)
                if conf < min_conf:
                    continue
                try:
                    cls_id = int(box.cls[0])
                except Exception:
                    cls_id = int(box.cls)
                label = yolo.names.get(cls_id, str(cls_id))
                detected.add(label)
        try:
            annotated = res[0].plot() if (res and len(res) > 0) else frame
            cv2.imshow(win, annotated)
        except Exception:
            try:
                cv2.imshow(win, frame)
            except Exception:
                pass
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    try:
        cv2.destroyWindow(win)
    except Exception:
        pass

    det_list = sorted(detected)
    if det_list:
        success("Detection finished. I saw: " + ", ".join(det_list) + ".", "Detection completed.")
    else:
        success("Detection finished. No prominent objects detected.", "Detection completed; no prominent objects found.")
    append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "detect", "objects": det_list})

def detect_objects():
    th = threading.Thread(target=detect_objects_task, daemon=True)
    th.start()


def take_snap_task():
    cap = open_camera(1)
    if cap is None:
        error("Camera not found.", "Camera not found. Please connect a camera.")
        append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "snap", "result": "no_camera"})
        return
    info("Opening camera preview. Press SPACE to take photo or ESC to cancel.", "Opening camera preview. Press space to capture.")
    win = "Camera Preview - Press SPACE to capture"
    try:
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    except Exception:
        pass

    while True:
        ret, frame = cap.read()
        if not ret:
            warning("Failed to read from camera.", "Failed to read from camera.")
            break
        cv2.imshow(win, frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            info("Snapshot cancelled by user.", "Snapshot cancelled.")
            break
        elif key == 32:
            path = save_image_bgr(frame, prefix="photo")
            success(f"Photo captured and saved: {path}", "Photo captured and saved.")
            append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "snap", "file": path})
            try:
                img = cv2.imread(path)
                cv2.imshow("Captured Photo", img)
                cv2.waitKey(2000)
            except Exception:
                pass
            break

    cap.release()
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass

def take_snap():
    th = threading.Thread(target=take_snap_task, daemon=True)
    th.start()


def take_screenshot_task():
    try:
        info("Capturing full screen now.", "Capturing full screen.")
        shot = pyautogui.screenshot()
        arr = np.array(shot)
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR) if arr.ndim == 3 else arr
        path = os.path.join(SNAP_DIR, f"screen_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        cv2.imwrite(path, bgr)
        try:
            cv2.imshow("Screen Snapshot", arr)
            cv2.waitKey(2000)
            cv2.destroyWindow("Screen Snapshot")
        except Exception:
            pass
        success(f"Screen snapshot captured and saved: {path}", "Screen captured and saved.")
        append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "screenshot", "file": path})
    except Exception as e:
        error(f"Screenshot failed: {e}", "Failed to capture screen.")
        append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "screenshot", "result": "failed", "error": str(e)})

def take_screenshot():
    th = threading.Thread(target=take_screenshot_task, daemon=True)
    th.start()


def ask_ai_short(prompt: str, max_sentences: int = 2):
    try:
        full = ""
        for chunk in cfgmod.get_ai_response(prompt, stream=True):
            if chunk:
                full += chunk
        sentences = [s.strip() for s in full.replace("!",".").replace("?",".").split(".") if s.strip()]
        if sentences:
            return ". ".join(sentences[:max_sentences]) + "."
        return full[:200]
    except Exception:
        return prompt[:200] + ("..." if len(prompt) > 200 else "")


def ocr_screen_task():
    try:
        info("Capturing screen for OCR (showing preview)...", "Capturing the screen now.")
        shot = pyautogui.screenshot()
        arr = np.array(shot)
        try:
            cv2.imshow("Screen Capture (for OCR)", arr)
            cv2.waitKey(2000)
            cv2.destroyWindow("Screen Capture (for OCR)")
        except Exception:
            pass

        if 'pytesseract' not in sys.modules:
            warning("OCR engine (pytesseract) not available.", "OCR engine not available. Install pytesseract.")
            append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "ocr", "result": "no_engine"})
            return

        text = pytesseract.image_to_string(arr).strip()
        if not text:
            warning("No readable text found on the screen.", "I could not find readable text on the screen.")
            append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "ocr", "result": "no_text"})
            return

        fname = os.path.join(TEXT_DIR, f"screen_ocr_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(text)

        prompt = f"Summarize this in 1-2 sentences:\n\n{text[:2000]}"
        summary = ask_ai_short(prompt, max_sentences=2)

        success("OCR completed and text saved.", "I found text on the screen and saved it.")
        print("\n--- OCR excerpt ---\n")
        print(text[:1000] + ("\n..." if len(text) > 1000 else ""))
        print("\n--- Ollama summary ---\n")
        print(summary)
        speak_blocking(summary if summary else "I read some text but could not summarize it.")
        append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "ocr", "file": fname, "summary": summary})
    except Exception as e:
        error(f"OCR failed: {e}", "OCR failed due to an internal error.")
        append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "ocr", "result": "failed", "error": str(e)})

def ocr_screen():
    th = threading.Thread(target=ocr_screen_task, daemon=True)
    th.start()


def qr_scan_task(timeout_seconds=15):
    if 'pyzbar' not in sys.modules:
        warning("QR decoder library (pyzbar) not available.", "QR decoder library not available.")
        append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "qr", "result": "no_lib"})
        return
    cap = open_camera(0)
    if cap is None:
        error("Camera not detected for QR scan.", "Camera not found.")
        append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "qr", "result": "no_camera"})
        return

    info("Starting QR and barcode scan. Press 'q' in window to cancel.", "Starting QR scan.")
    start = time.time()
    found = []
    win = "MAX - QR Scanner"
    try:
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    except Exception:
        pass

    while time.time() - start < timeout_seconds:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue
        try:
            decoded = pyzbar.decode(frame)
            for obj in decoded:
                try:
                    data = obj.data.decode("utf-8")
                except Exception:
                    data = str(obj.data)
                if data not in found:
                    found.append(data)
                    success(f"Found code: {data}", f"Found code: {data}")
            for obj in decoded:
                (x, y, w, h) = obj.rect
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                try:
                    t = obj.data.decode("utf-8")
                except Exception:
                    t = str(obj.data)
                cv2.putText(frame, t[:40], (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
        except Exception:
            pass
        try:
            cv2.imshow(win, frame)
        except Exception:
            pass
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if found:
            time.sleep(0.5)
            break

    cap.release()
    try:
        cv2.destroyWindow(win)
    except Exception:
        pass

    if found:
        success(f"{len(found)} code(s) found.", "QR scan completed.")
        for d in found:
            print(f"[QR]: {d}")
            speak_blocking(d)
    else:
        warning("No QR or barcode detected.", "No QR or barcode detected.")
    append_log({"timestamp": datetime.datetime.now().isoformat(), "event": "qr", "codes": found})

def qr_scan():
    th = threading.Thread(target=qr_scan_task, daemon=True)
    th.start()


def list_commands():
    commands = {
        "detect": "Analyze objects in front of the camera for 10 seconds (shows annotated live preview).",
        "take snap": "Open camera preview and capture a photo manually (SPACE to capture, ESC to cancel).",
        "take screenshot": "Capture your entire screen and save an image (shows preview).",
        "read the text": "Read text visible on your screen and produce a short summary (uses OCR).",
        "scan qr": "Scan a QR or barcode using your camera (10-15s scan).",
        "list": "Show this list of commands and short usage notes.",
        "exit": "Exit the vision module."
    }
    print("\n MAX Vision Assistant \u2014 Commands\n")
    for k, v in commands.items():
        print(f" - {k:<16} {v}")
    print("")
    speak_blocking("Displayed the list of available commands.")


def main_loop():
    ensure_commands_json()
    while True:
        try:
            user_input = input("\nEnter command -> ").strip()
        except (EOFError, KeyboardInterrupt):
            info("Input closed or interrupted. Exiting.", "Exiting the vision module.")
            break
        if not user_input:
            continue

        cmd = match_command(user_input)
        if cmd is None:
            lowered = user_input.lower()
            if lowered.startswith("take snap") or lowered.startswith("take photo") or "camera" in lowered and "snap" in lowered:
                cmd = "snap"
            elif lowered.startswith("take screenshot") or "capture screen" in lowered or "screen shot" in lowered:
                cmd = "screenshot"
            elif lowered in ("help", "list", "commands"):
                cmd = "list"
            elif lowered in ("exit", "quit", "q"):
                cmd = "exit"

        if any(x in user_input.lower() for x in ("stop", "cancel", "enough")):
            info("Interrupt requested (stop/cancel).", "Stopping current operation.")
            continue

        if cmd == "detect":
            detect_objects()
        elif cmd == "snap":
            take_snap()
        elif cmd == "screenshot":
            take_screenshot()
        elif cmd == "read the text":
            ocr_screen()
        elif cmd == "qr":
            qr_scan()
        elif cmd == "list":
            list_commands()
        elif cmd == "exit":
            break
        else:
            warning("Command not recognized. Type 'list' to see all options.", "Command not recognized. Type list to see options.")

    try:
        cv2.destroyAllWindows()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main_loop()
    except Exception:
        traceback.print_exc()
        error("An unexpected error occurred; check the terminal for details.", "An unexpected error occurred.")
