# ──────────────────────────────────────────────
# Project Ella v1.0 — Configuration
# Central config for all modules
# ──────────────────────────────────────────────

import os
import sys
import json
import warnings
from pathlib import Path

# Add CUDA DLL paths globally for ONNX Runtime/Torch
def _add_cuda_dll_paths_global():
    site_packages_nvidia = Path(sys.executable).parent / "Lib" / "site-packages" / "nvidia"
    if site_packages_nvidia.exists():
        for bin_dir in site_packages_nvidia.glob("*/bin"):
            bin_path_str = str(bin_dir.resolve())
            if bin_path_str not in os.environ.get("PATH", ""):
                os.environ["PATH"] = bin_path_str + os.path.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(bin_path_str)
            except Exception:
                pass
_add_cuda_dll_paths_global()

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

# Model to use — Gemma4:e4b (Google's latest, strong instruction-following, English + Hinglish)
MODEL_NAME = "gemma4:e4b"

# Ollama keep_alive (-1 = keep model pinned in GPU VRAM indefinitely)
KEEP_ALIVE = -1

# Generation parameters (GPU-First, Ultra-Fast Instant Replies)
GENERATION_CONFIG = {
    "temperature": 0.6,          # Slightly creative but controlled
    "top_p": 0.85,
    "top_k": 30,
    "num_predict": 150,          # Short 1-4 sentence conversational replies
    "num_ctx": 4096,             # 4k context — good for multi-turn without being slow
    "num_gpu": 99,               # Force ALL layers to 100% GPU offload (RTX 5060)
    "use_mmap": True,            # Memory mapping for faster loads
    "num_thread": 8,             # CPU thread fallback if needed
    "repeat_penalty": 1.3,       # Prevents repetition loops like .Clear.Clear
    "repeat_last_n": 64,         # Look back 64 tokens for repetition check
}

# STT model — faster-whisper (Large-v3-Turbo model for high accuracy English/Hinglish)
STT_MODEL = "large-v3-turbo"

# ── Voice Preprocessing (VAD & Noise Reduction) ──
VAD_MODEL_PATH = DATA_DIR / "silero_vad.onnx"
VAD_THRESHOLD = 0.5            # Speech probability threshold for Silero VAD
NOISE_REDUCE_ENABLED = True     # Use noisereduce spectral gating
NOISE_REDUCE_PROP = 0.8         # Noise reduction proportion (0.8 = 80% reduction)

# ── Voice Output (Kokoro TTS) ───────────────────
KOKORO_MODEL_DIR = DATA_DIR / "kokoro"
KOKORO_VOICE = "af_heart"       # Default voice (American English female, warm and clear)
KOKORO_SPEED = 1.0              # Voice output speed factor


# ── User ───────────────────────────────────────

# Default user name (will be overridden from settings.json)
USER_NAME = "Arnav"


# ── Session ────────────────────────────────────

# Sleep timeout in seconds (2 minutes)
SLEEP_TIMEOUT = 120

# Wake word
WAKE_WORD = "ella"


# ── Voice (Phase 2 / Kokoro Upgrade) ───────────

# Keep compatibility with old code where TTS_VOICE / TTS_RATE are used
TTS_VOICE = "af_heart"
TTS_RATE = "1.0"




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
