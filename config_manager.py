import json
import os
import sys
import time
import threading

CONFIG_FILE = os.path.expanduser("~/.maxai_config.json")

DEFAULT_CONFIG = {
    "ai": {
        "default_provider": "openrouter",
        "providers": {
            "openrouter": {
                "api_key": "",
                "model": "openai/gpt-4o",
                "base_url": "https://openrouter.ai/api/v1"
            },
            "openai": {
                "api_key": "",
                "model": "gpt-4o",
                "base_url": "https://api.openai.com/v1"
            },
            "anthropic": {
                "api_key": "",
                "model": "claude-3-5-sonnet-20241022",
                "base_url": "https://api.anthropic.com/v1"
            },
            "minimax": {
                "api_key": "",
                "model": "minimax-text-01",
                "base_url": "https://api.minimax.chat/v1"
            },
            "nvidia": {
                "api_key": "",
                "model": "nvidia/llama-3.1-nemotron-70b-instruct",
                "base_url": "https://integrate.api.nvidia.com/v1"
            },
            "google": {
                "api_key": "",
                "model": "gemini-2.0-flash",
                "base_url": ""
            },
            "deepseek": {
                "api_key": "",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com/v1"
            },
            "mistral": {
                "api_key": "",
                "model": "mistral-large-latest",
                "base_url": "https://api.mistral.ai/v1"
            },
            "cohere": {
                "api_key": "",
                "model": "command-r-plus",
                "base_url": "https://api.cohere.com/v1"
            },
            "ollama": {
                "api_key": "",
                "model": "gemma:7b",
                "base_url": "http://localhost:11434"
            }
        }
    },
    "tts": {
        "default_provider": "edge",
        "providers": {
            "pyttsx3": {
                "api_key": "",
                "rate": 170,
                "voice": ""
            },
            "openai": {
                "api_key": "",
                "model": "tts-1",
                "voice": "alloy"
            },
            "elevenlabs": {
                "api_key": "",
                "model": "eleven_multilingual_v2",
                "voice": "21m00Tcm4TlvDq8ikWAM"
            },
            "edge": {
                "api_key": "",
                "voice": "en-US-JennyNeural"
            }
        }
    }
}

_config_cache = None


def load_config(force_reload=False):
    global _config_cache
    if _config_cache is not None and not force_reload:
        return _config_cache
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            _config_cache = _merge_defaults(cfg)
            return _config_cache
        except Exception as e:
            print(f"[Config] Error reading config: {e}")
    return None


def save_config(cfg):
    global _config_cache
    _config_cache = cfg
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[Config] Error saving config: {e}")


def _merge_defaults(cfg):
    merged = DEFAULT_CONFIG.copy()
    if "ai" in cfg:
        merged["ai"].update(cfg.get("ai", {}))
        for prov in merged["ai"]["providers"]:
            if prov in cfg.get("ai", {}).get("providers", {}):
                merged["ai"]["providers"][prov].update(cfg["ai"]["providers"][prov])
    if "tts" in cfg:
        merged["tts"].update(cfg.get("tts", {}))
        for prov in merged["tts"]["providers"]:
            if prov in cfg.get("tts", {}).get("providers", {}):
                merged["tts"]["providers"][prov].update(cfg["tts"]["providers"][prov])
    return merged


def run_first_run_setup():
    print("\n" + "=" * 60)
    print("  MAX AI — First-Time Setup")
    print("=" * 60)
    print("\nWelcome! Let's configure your AI assistant.\n")
    print("You can leave fields empty and press Enter to skip — ")
    print("the assistant will use local Ollama as fallback.\n")

    cfg = DEFAULT_CONFIG.copy()

    print("--- AI Provider ---")
    print("Enter your OpenRouter API key (recommended — works with 200+ models):")
    or_key = input("  OpenRouter API key: ").strip()
    if or_key:
        cfg["ai"]["providers"]["openrouter"]["api_key"] = or_key

    print("\nEnter other AI API keys if you want (or press Enter to skip):")
    for prov in ["openai", "anthropic", "google", "deepseek", "mistral"]:
        label = {"openai": "OpenAI", "anthropic": "Anthropic/Claude",
                 "google": "Google Gemini", "deepseek": "DeepSeek",
                 "mistral": "Mistral AI"}.get(prov, prov)
        key = input(f"  {label} API key: ").strip()
        if key:
            cfg["ai"]["providers"][prov]["api_key"] = key

    providers_with_keys = [p for p in cfg["ai"]["providers"]
                           if cfg["ai"]["providers"][p].get("api_key") or p == "ollama"]
    if providers_with_keys:
        print("\nAvailable AI providers with keys:")
        for i, p in enumerate(providers_with_keys, 1):
            print(f"  {i}. {p}")
        sel = input(f"Select default AI provider (1-{len(providers_with_keys)}) [1]: ").strip()
        try:
            idx = int(sel) - 1 if sel else 0
            cfg["ai"]["default_provider"] = providers_with_keys[idx]
        except (ValueError, IndexError):
            cfg["ai"]["default_provider"] = providers_with_keys[0] if providers_with_keys else "ollama"

    print("\n--- Text-to-Speech Provider ---")
    print("Enter an API key for cloud TTS, or press Enter to use local pyttsx3:")
    tts_key = input("  OpenAI TTS / ElevenLabs API key: ").strip()
    if tts_key:
        cfg["tts"]["providers"]["openai"]["api_key"] = tts_key
        cfg["tts"]["providers"]["elevenlabs"]["api_key"] = tts_key
        print("Available TTS providers:")
        print("  1. openai (OpenAI TTS)")
        print("  2. elevenlabs (ElevenLabs)")
        print("  3. edge (Edge-TTS)")
        print("  4. pyttsx3 (local, no key needed)")
        sel = input("Select default TTS provider (1-4) [4]: ").strip()
        tts_opts = ["openai", "elevenlabs", "edge", "pyttsx3"]
        try:
            idx = int(sel) - 1 if sel else 3
            cfg["tts"]["default_provider"] = tts_opts[idx] if 0 <= idx < len(tts_opts) else "pyttsx3"
        except (ValueError, IndexError):
            cfg["tts"]["default_provider"] = "pyttsx3"
    else:
        cfg["tts"]["default_provider"] = "pyttsx3"

    save_config(cfg)
    print("\n" + "=" * 60)
    print("  Setup complete! Config saved to ~/.maxai_config.json")
    print("  You can edit this file anytime to add more API keys.")
    print("=" * 60 + "\n")
    return cfg


def get_ai_response(prompt, provider=None, stream=True):
    cfg = load_config()
    if not cfg:
        cfg = run_first_run_setup()

    provider = provider or cfg["ai"]["default_provider"]
    prov_cfg = cfg["ai"]["providers"].get(provider, {})
    api_key = prov_cfg.get("api_key", "")
    model = prov_cfg.get("model", "gemma:7b")
    base_url = prov_cfg.get("base_url", "")

    if provider == "ollama":
        return _call_ollama(prompt, model, base_url, stream)
    elif provider == "openai" or provider == "openrouter":
        return _call_openai_compat(prompt, model, api_key, base_url, stream)
    elif provider == "anthropic":
        return _call_anthropic(prompt, model, api_key, stream)
    elif provider == "google":
        return _call_google(prompt, model, api_key, stream)
    elif provider == "mistral":
        return _call_mistral(prompt, model, api_key, stream)
    elif provider == "cohere":
        return _call_cohere(prompt, model, api_key, stream)
    elif provider in ("nvidia", "minimax", "deepseek"):
        return _call_openai_compat(prompt, model, api_key, base_url, stream)
    else:
        return _call_ollama(prompt, "gemma:7b", "http://localhost:11434", stream)


def _call_ollama(prompt, model, base_url, stream):
    import requests
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": stream}
    try:
        if stream:
            return _stream_ollama(url, payload)
        r = requests.post(url, json=payload, timeout=120)
        if r.status_code != 200:
            r.close()
            return iter([f"[Ollama error] HTTP {r.status_code}"])
        lines = r.text.strip().split("\n")
        r.close()
        full = []
        for line in lines:
            try:
                obj = json.loads(line)
                full.append(obj.get("response", ""))
            except Exception:
                full.append(line)
        return iter(["".join(full)])
    except requests.exceptions.RequestException as e:
        return iter([f"[Ollama connection error] {e}. Is Ollama running?"])


def _stream_ollama(url, payload):
    import requests
    resp = None
    try:
        resp = requests.post(url, json=payload, stream=True, timeout=120)
        if resp.status_code != 200:
            yield f"[Ollama error] HTTP {resp.status_code}"
            return
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
                chunk = obj.get("response", "")
                if chunk:
                    yield chunk
            except Exception:
                if line.strip():
                    yield line
    except GeneratorExit:
        pass
    except Exception as e:
        yield f"[Ollama error] {e}"
    finally:
        if resp:
            try:
                resp.close()
            except Exception:
                pass


def _call_openai_compat(prompt, model, api_key, base_url, stream):
    from openai import OpenAI
    if not api_key:
        return _call_ollama(prompt, "gemma:7b", "http://localhost:11434", stream)
    try:
        client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/") + "/")
        messages = [{"role": "user", "content": prompt}]
        if stream:
            return _stream_openai(client, model, messages)
        r = client.chat.completions.create(model=model, messages=messages, stream=False)
        return iter([r.choices[0].message.content or ""])
    except Exception as e:
        return iter([f"[{base_url.split('/')[2] if '//' in base_url else 'AI'} error] {e}"])


def _stream_openai(client, model, messages):
    try:
        r = client.chat.completions.create(model=model, messages=messages, stream=True)
        for chunk in r:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
    except GeneratorExit:
        pass
    except Exception as e:
        yield f"[AI stream error] {e}"


def _call_anthropic(prompt, model, api_key, stream):
    if not api_key:
        return _call_ollama(prompt, "gemma:7b", "http://localhost:11434", stream)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        if stream:
            return _stream_anthropic(client, model, prompt)
        r = client.messages.create(
            model=model, max_tokens=1024, messages=[{"role": "user", "content": prompt}]
        )
        return iter([r.content[0].text])
    except Exception as e:
        return iter([f"[Anthropic error] {e}"])


def _stream_anthropic(client, model, prompt):
    try:
        with client.messages.stream(
            model=model, max_tokens=1024, messages=[{"role": "user", "content": prompt}]
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield text
    except GeneratorExit:
        pass
    except Exception as e:
        yield f"[Anthropic stream error] {e}"


def _call_google(prompt, model, api_key, stream):
    if not api_key:
        return _call_ollama(prompt, "gemma:7b", "http://localhost:11434", stream)
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        if stream:
            return _stream_google(client, model, prompt)
        r = client.models.generate_content(model=model, contents=prompt)
        return iter([r.text])
    except Exception as e:
        return iter([f"[Google AI error] {e}"])


def _stream_google(client, model, prompt):
    try:
        r = client.models.generate_content_stream(model=model, contents=prompt)
        for chunk in r:
            if chunk.text:
                yield chunk.text
    except GeneratorExit:
        pass
    except Exception as e:
        yield f"[Google stream error] {e}"


def _call_mistral(prompt, model, api_key, stream):
    if not api_key:
        return _call_ollama(prompt, "gemma:7b", "http://localhost:11434", stream)
    try:
        from mistralai import Mistral
        client = Mistral(api_key=api_key)
        if stream:
            return _stream_mistral(client, model, prompt)
        r = client.chat.complete(model=model, messages=[{"role": "user", "content": prompt}])
        return iter([r.choices[0].message.content])
    except Exception as e:
        return iter([f"[Mistral error] {e}"])


def _stream_mistral(client, model, prompt):
    try:
        r = client.chat.stream(model=model, messages=[{"role": "user", "content": prompt}])
        for chunk in r:
            delta = chunk.data.choices[0].delta if chunk.data and chunk.data.choices else None
            if delta and delta.content:
                yield delta.content
    except GeneratorExit:
        pass
    except Exception as e:
        yield f"[Mistral stream error] {e}"


def _call_cohere(prompt, model, api_key, stream):
    if not api_key:
        return _call_ollama(prompt, "gemma:7b", "http://localhost:11434", stream)
    try:
        import cohere
        client = cohere.ClientV2(api_key=api_key)
        r = client.chat(model=model, messages=[{"role": "user", "content": prompt}])
        return iter([r.message.content[0].text])
    except Exception as e:
        return iter([f"[Cohere error] {e}"])


_tts_lock = threading.Lock()
_tts_engine = None


def speak_text(text, provider=None):
    global _tts_engine
    if not text or not text.strip():
        return

    cfg = load_config()
    if not cfg:
        cfg = run_first_run_setup()

    provider = provider or cfg["tts"]["default_provider"]
    prov_cfg = cfg["tts"]["providers"].get(provider, {})
    api_key = prov_cfg.get("api_key", "")

    if provider == "pyttsx3":
        _speak_pyttsx3(text, prov_cfg)
    elif provider == "openai":
        _speak_openai_tts(text, model=prov_cfg.get("model", "tts-1"),
                           voice=prov_cfg.get("voice", "alloy"), api_key=api_key)
    elif provider == "elevenlabs":
        _speak_elevenlabs(text, api_key=api_key,
                          voice=prov_cfg.get("voice", "21m00Tcm4TlvDq8ikWAM"))
    elif provider == "edge":
        _speak_edge_tts(text, voice=prov_cfg.get("voice", "en-US-JennyNeural"))
    else:
        _speak_pyttsx3(text, prov_cfg)


def _speak_pyttsx3(text, prov_cfg):
    global _tts_engine
    import pyttsx3
    import re
    text = re.sub(r'[*_`~#\[\](){}|<>@=]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return
    try:
        with _tts_lock:
            if _tts_engine is None:
                _tts_engine = pyttsx3.init()
            _tts_engine.setProperty("rate", prov_cfg.get("rate", 170))
            _tts_engine.say(text)
            _tts_engine.runAndWait()
    except Exception as e:
        print(f"[TTS pyttsx3 error] {e}")
        _fallback_espeak(text)


def _speak_openai_tts(text, model, voice, api_key):
    if not api_key:
        _speak_pyttsx3(text, {"rate": 170})
        return
    import requests
    try:
        url = "https://api.openai.com/v1/audio/speech"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "input": text, "voice": voice, "response_format": "wav"}
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            import tempfile
            import subprocess
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(r.content)
            tmp.close()
            subprocess.Popen(["aplay", tmp.name],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print(f"[TTS OpenAI error] HTTP {r.status_code}: {r.text[:200]}")
            _speak_pyttsx3(text, {"rate": 170})
    except Exception as e:
        print(f"[TTS OpenAI error] {e}")
        _speak_pyttsx3(text, {"rate": 170})


def _speak_elevenlabs(text, api_key, voice, model="eleven_multilingual_v2"):
    if not api_key:
        _speak_pyttsx3(text, {"rate": 170})
        return
    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs.play import play
        client = ElevenLabs(api_key=api_key)
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice,
            model_id=model,
            output_format="mp3_44100_128",
        )
        play(audio)
    except Exception as e:
        print(f"[TTS ElevenLabs error] {e}")
        _speak_pyttsx3(text, {"rate": 170})


def _speak_edge_tts(text, voice):
    import asyncio
    import edge_tts
    try:
        async def _do():
            tts = edge_tts.Communicate(text, voice=voice)
            await tts.save("/tmp/_max_tts_edge.mp3")
            import subprocess
            subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "/tmp/_max_tts_edge.mp3"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        asyncio.run(_do())
    except Exception as e:
        print(f"[TTS Edge error] {e}")
        _speak_pyttsx3(text, {"rate": 170})


def _fallback_espeak(text):
    import subprocess
    safe = text.replace('"', "'")
    try:
        subprocess.Popen(f'espeak -ven+f3 -s150 "{safe}" >/dev/null 2>&1',
                         shell=True)
    except Exception:
        pass


def cleanup():
    global _tts_engine
    try:
        if _tts_engine:
            _tts_engine.stop()
    except Exception:
        pass
