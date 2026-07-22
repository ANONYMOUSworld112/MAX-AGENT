import os
import re
import sys
import json
import time
import threading
import datetime

import psutil

import config_manager as cfgmod

tts_engine = None
tts_lock = threading.Lock()
tts_active = threading.Event()


def clean_text_for_tts(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[\*_`~#\[\]\(\)\{\}\|<>@=]', ' ', text)
    text = re.sub(r':[a-zA-Z0-9_+-]+:', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def speak_blocking(text: str):
    text = clean_text_for_tts(text)
    if not text:
        return
    try:
        tts_active.set()
        print(f"\n[MAX]: {text}")
        with tts_lock:
            cfgmod.speak_text(text)
    except Exception as e:
        print("[TTS error]", e)
    finally:
        tts_active.clear()


def listen_once() -> str:
    try:
        user_input = input("\n[You]: ").strip()
        return user_input.lower()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print("[Input error]", e)
        return ""


def get_time_text() -> str:
    now = datetime.datetime.now()
    return now.strftime("The current time is %I:%M %p on %B %d, %Y.")


def get_cpu_text() -> str:
    cpu = psutil.cpu_percent(interval=0.6)
    return f"CPU usage is {cpu:.1f} percent."


def get_memory_text() -> str:
    vm = psutil.virtual_memory()
    used = (vm.total - vm.available) / (1024 ** 3)
    total = vm.total / (1024 ** 3)
    percent = vm.percent
    return f"Memory usage: {used:.2f} GB used of {total:.2f} GB ({percent:.1f} percent)."


def get_system_summary() -> str:
    return f"{get_cpu_text()} {get_memory_text()}"


def stream_ai_sentences(prompt: str, provider: str = None):
    buffer = ""
    try:
        for chunk in cfgmod.get_ai_response(prompt, provider=provider, stream=True):
            if not chunk:
                continue
            buffer += chunk
            parts = re.split(r'(?<=[\.!\?])\s+', buffer)
            for part in parts[:-1]:
                cleaned = clean_text_for_tts(part)
                if cleaned:
                    yield cleaned
            buffer = parts[-1]
        if buffer.strip():
            yield clean_text_for_tts(buffer.strip())
    except Exception as e:
        yield f"[AI error] {e}"


stream_ollama_sentences = stream_ai_sentences


def ask_ai_once(prompt: str, provider: str = None) -> str:
    try:
        parts = []
        for chunk in cfgmod.get_ai_response(prompt, provider=provider, stream=False):
            parts.append(chunk)
        return "".join(parts)
    except Exception as e:
        return f"[AI error] {e}"


__all__ = [
    "speak_blocking",
    "listen_once",
    "stream_ollama_sentences",
    "stream_ai_sentences",
    "ask_ai_once",
    "get_time_text",
    "get_cpu_text",
    "get_memory_text",
    "get_system_summary",
    "tts_active",
]
