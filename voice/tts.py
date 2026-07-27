# ──────────────────────────────────────────────
# Project Ella v1.0 — Text-To-Speech (TTS)
# Powered by Kokoro-TTS (100% Offline, GPU-Accelerated)
# ──────────────────────────────────────────────

import os
import sys
import time
import urllib.request
from pathlib import Path
from logger import get_logger
from events import event_bus, Event
from config import KOKORO_MODEL_DIR, KOKORO_VOICE, KOKORO_SPEED, DATA_DIR

log = get_logger("voice.tts")


class BaseTTS:
    """Abstract Base Class for modular TTS engines."""
    def speak(self, text: str, block: bool = True) -> bool:
        raise NotImplementedError


class TextToSpeech(BaseTTS):
    """
    Ella's local voice output engine using Kokoro-TTS.
    
    Generates natural-sounding speech from text using the Kokoro-82M model
    running offline via ONNX Runtime with CUDA GPU acceleration.
    
    Supports dynamic voice packs (e.g. af_heart, af_bella, am_adam, pm_alex).
    """

    def __init__(self, voice: str = None, speed: float = None):
        self.voice = voice or KOKORO_VOICE
        self.speed = speed or KOKORO_SPEED
        self.model_dir = Path(KOKORO_MODEL_DIR)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.model_path = self.model_dir / "kokoro-v1.0.onnx"
        self.voices_path = self.model_dir / "voices-v1.0.bin"
        
        self.kokoro = None
        self.enabled = True
        
        # Trigger lazy-load check
        self._ensure_model_files_exist()

    def _ensure_model_files_exist(self):
        """Checks if Kokoro ONNX model and voice packs are downloaded. Downloads if missing."""
        model_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
        voices_url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
        
        try:
            if not self.model_path.exists():
                log.info(f"Downloading Kokoro ONNX model to {self.model_path} (this happens only once)...")
                self._download_file(model_url, self.model_path)
                
            if not self.voices_path.exists():
                log.info(f"Downloading Kokoro voice packs to {self.voices_path} (this happens only once)...")
                self._download_file(voices_url, self.voices_path)
                
        except Exception as e:
            log.error(f"Failed to download Kokoro models: {e}")
            self.enabled = False

    def _download_file(self, url: str, dest_path: Path):
        """Helper to download a file with progress logging."""
        import requests
        from rich.progress import Progress, BarColumn, DownloadColumn, TextColumn, TimeRemainingColumn
        
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dest = dest_path.with_suffix(".tmp")
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TimeRemainingColumn(),
            transient=True
        ) as progress:
            task = progress.add_task(f"Downloading {dest_path.name}...", total=total_size)
            
            with open(temp_dest, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))
                        
        if temp_dest.exists():
            temp_dest.rename(dest_path)
            log.info(f"Successfully downloaded {dest_path.name}")

    def _lazy_load(self):
        """Lazy loads Kokoro model onto GPU (CUDA ONNX Provider)."""
        if self.kokoro is not None:
            return
            
        if not self.enabled:
            return
            
        try:
            log.info("Initializing Kokoro TTS engine...")
            import onnxruntime as ort
            from kokoro_onnx import Kokoro
            
            # Suppress verbose ONNX Runtime warnings (red/green text on Windows)
            ort.set_default_logger_severity(3)
            
            # Check for CUDA GPU provider availability
            available_providers = ort.get_available_providers()
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if 'CUDAExecutionProvider' in available_providers else ['CPUExecutionProvider']
            
            log.info(f"ONNX Execution Providers: {providers}")
            
            # Explicitly set ONNX_PROVIDER to force CUDA if available
            if 'CUDAExecutionProvider' in available_providers:
                os.environ["ONNX_PROVIDER"] = "CUDAExecutionProvider"
            
            # Load ONNX model (Kokoro handles providers natively in its __init__)
            self.kokoro = Kokoro(
                model_path=str(self.model_path),
                voices_path=str(self.voices_path),
            )
            
            log.info("Kokoro TTS engine ready.")
        except Exception as e:
            log.error(f"Error loading Kokoro TTS: {e}")
            self.enabled = False

    def speak(self, text: str, block: bool = True) -> bool:
        """
        Convert text to speech and play it out loud.
        
        Args:
            text:  The text string for Ella to speak
            block: If True, waits until speech completes before returning
            
        Returns:
            True if audio generated & played successfully
        """
        if not self.enabled or not text.strip():
            return False
            
        # Clean text for speech
        clean_text = self._clean_text_for_speech(text)
        if not clean_text:
            return False
            
        log.info(f"Speaking (local Kokoro): '{clean_text[:60]}{'...' if len(clean_text) > 60 else ''}'")
        
        try:
            self._lazy_load()
            if self.kokoro is None:
                return False
                
            start_time = time.time()
            
            # Generate raw audio float32 numpy array
            samples, sample_rate = self.kokoro.create(
                text=clean_text,
                voice=self.voice,
                speed=self.speed,
                lang="en-us"
            )
            
            generation_time = time.time() - start_time
            log.debug(f"Audio generated in {generation_time:.3f}s (Speed factor: {len(samples)/sample_rate/generation_time:.1f}x)")
            
            # Emit event
            event_bus.emit(Event(
                name="VoiceReply",
                source="voice.tts",
                data={"text": clean_text, "voice": self.voice}
            ))
            
            # Play the generated audio instantly in-memory using sounddevice
            import sounddevice as sd
            sd.play(samples, sample_rate)
            
            if block:
                sd.wait()
                
            return True
            
        except Exception as e:
            log.error(f"Kokoro TTS generation/playback error: {e}")
            return False

    def _clean_text_for_speech(self, text: str) -> str:
        """Clean markdown formatting, code blocks, emojis, and symbols."""
        import re
        
        # Remove code blocks ```...```
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # Remove inline code `...`
        text = re.sub(r'`.*?`', '', text)
        # Remove markdown headers #, ##, etc.
        text = re.sub(r'#+\s*', '', text)
        # Remove markdown bold/italic *, _
        text = re.sub(r'[*_]{1,3}', '', text)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove JSON memory blocks if any left
        text = re.sub(r'```ella_memory.*?```', '', text, flags=re.DOTALL)
        
        # Remove ALL emojis and Unicode symbols
        emoji_pattern = re.compile(
            "["
            "\U00010000-\U0010FFFF"  # Emojis & pictographs
            "\u2600-\u27BF"          # Misc symbols & dingbats
            "\u2300-\u23FF"          # Tech symbols
            "\u2300-\u23FF"          # Tech symbols
            "\u2B00-\u2BFF"          # Misc symbols
            "]+", flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)
        
        # Clean extra spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()


if __name__ == "__main__":
    # Test script
    import logging
    logging.basicConfig(level=logging.INFO)
    tts = TextToSpeech()
    tts.speak("Hello Arnav! Kokoro is fully running offline on our local laptop GPU. It is super fast and crystal clear.")
