# ──────────────────────────────────────────────
# Project Ella v1.0 — Configuration
# Central config for all modules
# ──────────────────────────────────────────────

import os
import json
import warnings
from pathlib import Path

# Suppress HuggingFace cache/symlink warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


# ── Paths ──────────────────────────────────────

# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Data directory
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Logs directory
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Settings file
SETTINGS_FILE = DATA_DIR / "settings.json"

# Memory database
MEMORY_DB = DATA_DIR / "memory.db"

# Voice profile (speaker fingerprint — Phase 2)
VOICE_PROFILE = DATA_DIR / "voice_profile.bin"


# ── LLM / Brain ───────────────────────────────

# Ollama server URL (local)
OLLAMA_BASE_URL = "http://localhost:11434"

# Model to use — Gemma4:e4b (GPU-accelerated)
MODEL_NAME = "gemma3:4b"

# Ollama keep_alive (-1 = keep model pinned in GPU VRAM indefinitely)
KEEP_ALIVE = -1

# Generation parameters (GPU-First, Ultra-Fast)
GENERATION_CONFIG = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 512,          # max tokens to generate
    "num_ctx": 4096,             # 4k context window for ultra-fast TTFT
    "num_gpu": 99,               # Force ALL layers to 100% GPU offload (RTX 5060)
    "use_mmap": True,            # Memory mapping for faster loads
    "num_thread": 8,             # CPU thread fallback if needed
}



# ── User ───────────────────────────────────────

# Default user name (will be overridden from settings.json)
USER_NAME = "Arnav"


# ── Session ────────────────────────────────────

# Sleep timeout in seconds (2 minutes)
SLEEP_TIMEOUT = 120

# Wake word
WAKE_WORD = "ella"


# ── Voice (Phase 2) ───────────────────────────

# TTS voice — Indian English female
TTS_VOICE = "en-IN-NeerjaNeural"

# TTS speech rate — +35% faster (matches natural human conversational speed)
TTS_RATE = "+35%"


# STT model — faster-whisper
STT_MODEL = "base"



# ── Logging ────────────────────────────────────

# Log level
LOG_LEVEL = "INFO"

# Log file rotation
LOG_ROTATION = "10 MB"

# Log retention
LOG_RETENTION = "7 days"


# ── Version ────────────────────────────────────

VERSION = "1.0.0"
APP_NAME = "Ella"
TAGLINE = "Your Personal Offline AI Desktop Assistant"


# ── Settings Loader ───────────────────────────

def load_settings() -> dict:
    """Load user settings from settings.json. Creates defaults if not found."""
    defaults = {
        "user_name": USER_NAME,
        "model": MODEL_NAME,
        "tts_voice": TTS_VOICE,
        "stt_model": STT_MODEL,
        "sleep_timeout": SLEEP_TIMEOUT,
        "wake_word": WAKE_WORD,
        "theme": "dark",
        "language": "hinglish",     # hinglish | english
        "verbose": False,
    }
    
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
            # Merge: user settings override defaults
            defaults.update(user_settings)
        except (json.JSONDecodeError, IOError):
            pass
    
    return defaults


def save_settings(settings: dict) -> None:
    """Save settings to settings.json."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


# Load settings on import
settings = load_settings()

# Override globals from settings
USER_NAME = settings.get("user_name", USER_NAME)
MODEL_NAME = settings.get("model", MODEL_NAME)
