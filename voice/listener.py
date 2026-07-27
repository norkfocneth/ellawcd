# ──────────────────────────────────────────────
# Project Ella v1.0 — Microphone Listener
# Captures voice input, detects speech end, sends to STT
# ──────────────────────────────────────────────

import numpy as np
import time

from logger import get_logger
from events import event_bus, Event

log = get_logger("voice.listener")

# Audio settings
SAMPLE_RATE = 16000       # 16kHz for Whisper
CHANNELS = 1              # Mono
CHUNK_DURATION = 0.3      # 300ms chunks (faster response)
SILENCE_DURATION = 1.2    # 1.2s of silence = speech ended
MIN_SPEECH_DURATION = 0.3 # Min speech to process
MAX_RECORD_SECONDS = 20   # Max recording length
MAX_WAIT_SECONDS = 15     # Max wait for speech to start


class MicListener:
    """
    Ella's microphone listener — captures voice and detects speech.
    
    Uses adaptive noise floor: samples ambient noise first, then
    sets threshold dynamically. This prevents getting stuck when
    there's background noise.
    """

    def __init__(self):
        self.sample_rate = SAMPLE_RATE
        self.channels = CHANNELS
        self.chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION)
        self.is_listening = False
        self.noise_floor = 0.01  # Will be calibrated
        self._sd = None
        self._load_sounddevice()

    def _load_sounddevice(self):
        """Import sounddevice."""
        try:
            import sounddevice as sd
            self._sd = sd
            sd.default.samplerate = self.sample_rate
            sd.default.channels = self.channels
            sd.default.dtype = 'float32'
            log.info("MicListener initialized — microphone ready")
        except Exception as e:
            log.error(f"Microphone not available: {e}")
            self._sd = None

    def is_available(self) -> bool:
        """Check if microphone is available."""
        if self._sd is None:
            return False
        try:
            devices = self._sd.query_devices()
            return devices is not None
        except Exception:
            return False

    def _calibrate_noise_floor(self, stream, duration: float = 0.5) -> float:
        """
        Sample ambient noise for a short period to determine baseline.
        Threshold will be set at 3x this level.
        """
        rms_values = []
        chunks_needed = int(duration / CHUNK_DURATION)
        
        for _ in range(max(chunks_needed, 2)):
            audio_chunk, _ = stream.read(self.chunk_samples)
            audio_chunk = audio_chunk.flatten()
            rms = np.sqrt(np.mean(audio_chunk ** 2))
            rms_values.append(rms)
        
        noise_floor = np.mean(rms_values)
        # Threshold = 3x noise floor, but at least 0.008 and at most 0.05
        threshold = max(0.008, min(noise_floor * 3.0, 0.05))
        log.debug(f"Noise floor: {noise_floor:.4f}, threshold: {threshold:.4f}")
        return threshold

    def listen_once(self) -> np.ndarray | None:
        """
        Listen for one complete speech utterance.
        
        1. Calibrates ambient noise level
        2. Waits for speech to start (volume > threshold)
        3. Records until speech ends (silence > 1.2 seconds)
        4. Returns audio numpy array
        
        Returns None if no speech detected within MAX_WAIT_SECONDS.
        """
        if self._sd is None:
            log.error("Microphone not available")
            return None

        audio_chunks = []
        is_speaking = False
        silence_start = None
        record_start = None
        wait_start = time.time()
        
        try:
            with self._sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                blocksize=self.chunk_samples
            ) as stream:
                
                # Step 1: Calibrate noise floor
                threshold = self._calibrate_noise_floor(stream)
                self.noise_floor = threshold
                
                self.is_listening = True
                
                while self.is_listening:
                    # Read audio chunk
                    audio_chunk, _ = stream.read(self.chunk_samples)
                    audio_chunk = audio_chunk.flatten()
                    
                    # Calculate RMS (volume level)
                    rms = np.sqrt(np.mean(audio_chunk ** 2))
                    
                    if not is_speaking:
                        # Waiting for speech to start
                        if rms > threshold:
                            is_speaking = True
                            record_start = time.time()
                            silence_start = None
                            audio_chunks.append(audio_chunk)
                            log.debug(f"Speech detected (rms={rms:.4f} > threshold={threshold:.4f})")
                        else:
                            # Timeout: give up waiting for speech
                            if time.time() - wait_start > MAX_WAIT_SECONDS:
                                log.debug("No speech detected — timeout")
                                self.is_listening = False
                                return None
                    else:
                        # Recording speech
                        audio_chunks.append(audio_chunk)
                        
                        if rms < threshold:
                            # Below threshold — silence
                            if silence_start is None:
                                silence_start = time.time()
                            elif time.time() - silence_start >= SILENCE_DURATION:
                                # Speech ended!
                                log.debug("Speech ended — silence detected")
                                break
                        else:
                            # Still speaking
                            silence_start = None
                        
                        # Safety: max recording length
                        if record_start and (time.time() - record_start) >= MAX_RECORD_SECONDS:
                            log.debug("Max recording length reached")
                            break
                
                self.is_listening = False
            
            if not audio_chunks:
                return None
            
            # Combine all chunks
            full_audio = np.concatenate(audio_chunks)
            
            # Check minimum duration
            duration = len(full_audio) / self.sample_rate
            if duration < MIN_SPEECH_DURATION:
                log.debug(f"Audio too short ({duration:.1f}s) — ignoring")
                return None
            
            log.info(f"Recorded {duration:.1f}s of audio")
            return full_audio
            
        except Exception as e:
            log.error(f"Mic listener error: {e}")
            self.is_listening = False
            return None

    def stop(self):
        """Stop listening."""
        self.is_listening = False
