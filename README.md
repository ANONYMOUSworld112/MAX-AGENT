██████╗██╗   ██╗██████╗ ███████╗██████╗ ██████╗ ██╗      █████╗  ██████╗██╗  ██╗
██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝
██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝██████╔╝██║     ███████║██║     █████╔╝
██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗██╔══██╗██║     ██╔══██║██║     ██╔═██╗
╚██████╗   ██║   ██████╔╝███████╗██║  ██║██████╔╝███████╗██║  ██║╚██████╗██║  ██╗
 ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝

# MAX AI — Personal Voice Assistant

A modular offline-first AI assistant with voice output, vision capabilities, and file management. Built for Ubuntu/Linux.

## Quick Start

```bash
pip install -r requirements.txt
python3 main_launcher.py
```

On **first run**, you'll be prompted to enter API keys (or press Enter to skip and use free local options).

## Features

### AI Providers (choose any)
| Provider | API Key Needed | Default Model |
|----------|---------------|---------------|
| Ollama (local) | No | `gemma:7b` |
| OpenRouter | Optional | `openai/gpt-4o` |
| OpenAI | Optional | `gpt-4o` |
| Anthropic (Claude) | Optional | `claude-3-5-sonnet` |
| Google Gemini | Optional | `gemini-2.0-flash` |
| Mistral | Optional | `mistral-large-latest` |
| Cohere | Optional | `command-r-plus` |
| DeepSeek | Optional | `deepseek-chat` |
| MiniMax | Optional | `minimax-text-01` |
| NVIDIA | Optional | `nemotron-70b` |

> No keys? No problem. Falls back to **local Ollama** automatically.

### Text-to-Speech
| Provider | API Key | Notes |
|----------|---------|-------|
| pyttsx3 | No | Local, works offline |
| Edge-TTS | No | Free, natural voices |
| ElevenLabs | Yes | Premium voices |
| OpenAI TTS | Yes | GPT-quality speech |

### Modules

#### 1. Automation (`automation_commands.py`)
- Open/close apps (terminal, browser, calculator, etc.)
- Web search (Google, YouTube, Wikipedia)
- Reminders with timer
- Run terminal commands
- System info (CPU, memory, time)
- AI question answering

#### 2. Vision (`vision_module.py`)
- **Object detection** — YOLOv8 real-time camera analysis
- **Take photo** — Camera capture with preview
- **Screenshot** — Full screen capture
- **OCR** — Read text from screen via pytesseract
- **QR/Barcode** — Scan codes via camera
- All results logged to JSON

#### 3. File Manager (`file_manager.py`)
- Create/read/write/delete files
- Create/delete folders
- Search files by name
- Copy/move/zip/unzip
- AI-powered file summarization

## Configuration

All settings stored at `~/.maxai_config.json`:

```json
{
  "ai": { "default_provider": "ollama", "providers": { ... } },
  "tts": { "default_provider": "edge", "providers": { ... } }
}
```

Edit this file anytime to add API keys or change providers.

## Requirements

- Python 3.10+
- Ollama (optional, for local AI) — `curl -fsSL https://ollama.com/install.sh | sh`
- Tesseract (optional, for OCR) — `sudo apt install tesseract-ocr`
- espeak (optional, TTS fallback) — `sudo apt install espeak`

## Project Structure

```
MAX_AI/
├── config_manager.py       # API keys, TTS, first-run setup
├── core_engine.py          # Core TTS, AI streaming, system info
├── automation_commands.py  # App control, web, reminders, terminal
├── vision_module.py        # Camera, YOLO, OCR, QR, screenshots
├── file_manager.py         # File/folder manager
├── main_launcher.py        # Main launcher menu
├── requirements.txt    # Python dependencies
├── yolov8n.pt          # YOLO weights
└── .gitignore
```
