# ──────────────────────────────────────────────
# Project Ella v1.0 — Speech-To-Text (STT)
# Powered by faster-whisper (GPU-accelerated)
# ──────────────────────────────────────────────

import numpy as np
import time

from config import STT_MODEL
from logger import get_logger
from events import event_bus, Event

log = get_logger("voice.stt")


class WhisperSTT:
    """
    Ella's ears — converts spoken audio to text using faster-whisper.
    
    Uses the Whisper model locally (no internet needed for STT).
    Runs on CPU by default (GPU CUDA if available).
    
    Usage:
        stt = WhisperSTT()
        text = stt.transcribe(audio_numpy_array, sample_rate=16000)
        print(text)  # "Hello Ella, how are you?"
    """

    def __init__(self, model_size: str = None):
        self.model_size = model_size or STT_MODEL
        self.model = None
        self._load_model()

    def _add_cuda_dll_paths(self):
        """Add NVIDIA CUDA site-packages DLL paths to PATH and DLL search path."""
        import sys
        import os
        from pathlib import Path
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

    def _load_model(self):
        """Load the faster-whisper model."""
        import warnings
        import os
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        warnings.filterwarnings("ignore")
        
        # Ensure NVIDIA CUDA DLLs are accessible
        self._add_cuda_dll_paths()
        
        try:
            from faster_whisper import WhisperModel
            
            # Try GPU first (CUDA), fallback to CPU
            try:
                self.model = WhisperModel(
                    self.model_size,
                    device="cuda",
                    compute_type="float16"
                )
                log.info(f"WhisperSTT loaded — model: {self.model_size} (GPU/CUDA)")
            except Exception as gpu_err:
                log.warning(f"GPU STT failed ({gpu_err}), falling back to CPU")
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8"
                )
                log.info(f"WhisperSTT loaded — model: {self.model_size} (CPU/int8)")
                
        except ImportError:
            log.error("faster-whisper not installed. Run: pip install faster-whisper")
            self.model = None

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe audio numpy array to text.
        
        Args:
            audio:       Numpy float32 array of audio samples
            sample_rate: Sample rate (default 16000 Hz for Whisper)
            
        Returns:
            Transcribed text string
        """
        if self.model is None:
            log.error("STT model not loaded")
            return ""
        
        start_time = time.time()
        
        try:
            # Apply noisereduce (DSP Spectral Gating)
            from voice.noise import NoiseReducer
            reducer = NoiseReducer(sample_rate=sample_rate)
            audio = reducer.reduce_noise(audio)
            
            # Ensure audio is float32 and correct shape
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            
            # Normalize if needed
            if np.abs(audio).max() > 1.0:
                audio = audio / np.abs(audio).max()
            
            # Transcribe with language="en" for accurate Hinglish/English Latin script
            segments, info = self.model.transcribe(
                audio,
                beam_size=3,
                language="en",
                initial_prompt="Hello Ella. Kaise ho? Kya kar rahi ho?",
                vad_filter=True,           # Voice Activity Detection filter
                vad_parameters=dict(
                    min_silence_duration_ms=400,
                ),
                condition_on_previous_text=False,  # Prevents infinite repetition loops like '.Clear.Clear.Clear'
                no_speech_threshold=0.6,           # Drops segments where the model predicts background noise/silence
            )
            
            # Collect all segment texts
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            
            full_text = " ".join(text_parts).strip()
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            if full_text:
                log.info(f"STT: '{full_text[:60]}' ({elapsed_ms:.0f}ms)")
                
                event_bus.emit(Event(
                    name="TranscriptionReady",
                    source="voice.stt",
                    data={
                        "text": full_text,
                        "source": "voice",
                        "language": info.language,
                        "confidence": info.language_probability,
                        "latency_ms": round(elapsed_ms),
                    }
                ))
            
            return full_text
            
        except Exception as e:
            log.error(f"STT transcription error: {e}")
            return ""

    def is_available(self) -> bool:
        """Check if STT model is loaded and ready."""
        return self.model is not None
