#!/usr/bin/env python3
import subprocess
import os
import threading
import time
import sys

import config_manager as cfgmod
from core_engine import speak_blocking as speak, get_time_text


def run_automation():
    try:
        subprocess.run(["python3", "-u", "automation_commands.py"], check=True)
    except subprocess.CalledProcessError:
        pass

def run_vision():
    try:
        subprocess.run(["python3", "-u", "vision_module.py"], check=True)
    except subprocess.CalledProcessError:
        pass

def run_file_manager():
    try:
        subprocess.run(["python3", "-u", "file_manager.py"], check=True)
    except subprocess.CalledProcessError:
        pass


def show_all_commands():
    print("\n MAX \u2014 FULL COMMAND REFERENCE ")
    print("\u2500" * 46)

    print('''
    MAX \u2014 commands:
 - open <app>                (e.g., open terminal)
 - close <app>               (e.g., close calculator)
 - list apps
 - search <query>            (e.g., search Python tutorial)
 - <query> on youtube        (e.g., song on youtube)
 - remind me in <time> to <task> (e.g., remind me in 10 minutes to check mail)
 - run <command>             (e.g., run ls -l)
 - what / define / explain <query>
 - system status / cpu / memory / time
 - exit ''')
    print("\u2500" * 46)

    print('''\n VISION COMMANDS :
detect: Analyze objects in front of the camera for 10 seconds.
take snap: Open camera preview and capture a photo manually.
take screenshot: Capture your entire screen and save an image.
read the text: Read text on screen and produce a short summary (OCR).
scan qr: Scan a QR or barcode using your camera.
list: Show this list of commands.
exit: Exit the vision module.''')
    print("\u2500" * 46)

    print("\n FILE HANDLING COMMANDS :")
    print(''' Folder:
  - create folder <path>
  - delete folder <path>
  - list files in <path>
  - list

 File:
  - read file <path>
  - write file <path> : <content>
  - create file <path>
  - delete file <path>
  - file info <path>
  - search file <name>
  - summarize file <path>

 Move/Copy/Zip:
  - move file <src> to <dest>
  - copy file <src> to <dest>
  - zip folder <path> to <output>
  - unzip <zipfile> to <folder>

 System:
  - help
  - exit''')
    print("\u2500" * 46)


def main():
    cfg = cfgmod.load_config()
    if cfg is None:
        cfgmod.run_first_run_setup()
    else:
        ai_prov = cfg["ai"]["default_provider"]
        tts_prov = cfg["tts"]["default_provider"]
        print(f"[Config] AI: {ai_prov} | TTS: {tts_prov}")

    speak("MAX IS ONLINE  ")
    speak("SYSTEM IS FULLY INITIALIZE ")
    time.sleep(2)
    if "time":
        result = get_time_text()
        speak(result)

    time.sleep(0.5)
    show_all_commands()
    time.sleep(1)

    while True:
        print("\nSelect option:")
        print("1. Run MAX COMMANDS ")
        print("2. Run VISION COMMANDS")
        print("3. Run FILE HANDLING COMMANDS")
        print("4. List all the commands")
        print("5. Exit")

        choice = input("Enter your choice: ").strip()

        if choice == "1":
            run_automation()
        elif choice == "2":
            run_vision()
        elif choice == "3":
            run_file_manager()
        elif choice == "4":
            speak("SHOWING ALL THE COMMANDS")
            show_all_commands()
        elif choice == "5":
            speak("MAX IS DEACTIVATING ")
            break
        else:
            speak("MAX CANT VALID IT")


if __name__ == "__main__":
    main()
