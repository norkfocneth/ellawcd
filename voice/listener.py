# ──────────────────────────────────────────────
# Project Ella v1.0 — Microphone Listener
# Captures voice input, detects speech end, sends to STT
# ──────────────────────────────────────────────

import numpy as np
import threading
import time
import queue

from logger import get_logger
from events import event_bus, Event

log = get_logger("voice.listener")

# Audio settings
SAMPLE_RATE = 16000       # 16kHz for Whisper
CHANNELS = 1              # Mono
CHUNK_DURATION = 0.5      # 500ms chunks
SILENCE_THRESHOLD = 0.02  # RMS below this = silence
SILENCE_DURATION = 1.5    # Seconds of silence to end recording
MIN_SPEECH_DURATION = 0.5 # Minimum speech to process (ignore noise)
MAX_RECORD_SECONDS = 30   # Max recording length


class MicListener:
    """
    Ella's microphone listener — captures voice and detects speech boundaries.
    
    How it works:
    1. Continuously captures audio from default microphone
    2. Detects when user STARTS speaking (RMS > threshold)
    3. Records until user STOPS speaking (silence > 1.5s)
    4. Returns the recorded audio chunk for STT processing
    
    Usage:
        listener = MicListener()
        audio = listener.listen_once()   # Blocks until speech detected + ended
        # audio is a numpy float32 array ready for Whisper
    """

    def __init__(self):
        self.sample_rate = SAMPLE_RATE
        self.channels = CHANNELS
        self.chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION)
        self.is_listening = False
        self._sd = None
        self._load_sounddevice()

    def _load_sounddevice(self):
        """Import sounddevice (lazy load to avoid errors if no mic)."""
        try:
            import sounddevice as sd
            self._sd = sd
            # Set default parameters
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

    def listen_once(self) -> np.ndarray | None:
        """
        Listen for one complete speech utterance.
        
        Blocks until:
        1. User starts speaking (audio > threshold)
        2. User stops speaking (silence > 1.5 seconds)
        
        Returns:
            numpy float32 array of recorded audio, or None if error/no speech
        """
        if self._sd is None:
            log.error("Microphone not available")
            return None

        audio_chunks = []
        is_speaking = False
        silence_start = None
        record_start = None
        
        try:
            # Show listening indicator
            event_bus.emit(Event(
                name="ListeningStarted",
                source="voice.listener",
                data={"status": "waiting_for_speech"}
            ))
            
            with self._sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                blocksize=self.chunk_samples
            ) as stream:
                
                self.is_listening = True
                
                while self.is_listening:
                    # Read audio chunk
                    audio_chunk, overflowed = stream.read(self.chunk_samples)
                    audio_chunk = audio_chunk.flatten()
                    
                    # Calculate RMS (volume level)
                    rms = np.sqrt(np.mean(audio_chunk ** 2))
                    
                    if not is_speaking:
                        # Waiting for speech to start
                        if rms > SILENCE_THRESHOLD:
                            is_speaking = True
                            record_start = time.time()
                            silence_start = None
                            audio_chunks.append(audio_chunk)
                            log.debug("Speech detected — recording...")
                            
                            event_bus.emit(Event(
                                name="ListeningStarted",
                                source="voice.listener",
                                data={"status": "recording"}
                            ))
                    else:
                        # Currently recording
                        audio_chunks.append(audio_chunk)
                        
                        if rms < SILENCE_THRESHOLD:
                            # Silence detected
                            if silence_start is None:
                                silence_start = time.time()
                            elif time.time() - silence_start >= SILENCE_DURATION:
                                # Enough silence — speech is done
                                log.debug("Speech ended — silence detected")
                                break
                        else:
                            # Still speaking — reset silence timer
                            silence_start = None
                        
                        # Safety: max recording length
                        if record_start and (time.time() - record_start) >= MAX_RECORD_SECONDS:
                            log.debug("Max recording length reached")
                            break
                
                self.is_listening = False
            
            if not audio_chunks:
                return None
            
            # Combine all chunks into single array
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
