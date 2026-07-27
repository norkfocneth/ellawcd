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

    def _load_model(self):
        """Load the faster-whisper model."""
        import warnings
        import os
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        warnings.filterwarnings("ignore")
        
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
            except Exception:
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
            # Ensure audio is float32 and correct shape
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            
            # Normalize if needed
            if np.abs(audio).max() > 1.0:
                audio = audio / np.abs(audio).max()
            
            # Transcribe
            segments, info = self.model.transcribe(
                audio,
                beam_size=5,
                language="en",
                vad_filter=True,           # Voice Activity Detection filter
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                ),
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
