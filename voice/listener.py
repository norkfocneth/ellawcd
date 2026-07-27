# ──────────────────────────────────────────────
# Project Ella v1.0 — Microphone Listener
# Captures voice input using Silero VAD (Offline, Real-Time)
# ──────────────────────────────────────────────

import numpy as np
import time

from logger import get_logger
from events import event_bus, Event
from config import VAD_THRESHOLD

log = get_logger("voice.listener")

# Audio settings
SAMPLE_RATE = 16000       # 16kHz for Whisper / Silero VAD
CHANNELS = 1              # Mono
CHUNK_DURATION = 0.032    # 32ms chunks (exactly 512 samples at 16kHz)
MIN_SPEECH_DURATION = 0.3 # Min speech to process
MAX_RECORD_SECONDS = 20   # Max recording length
MAX_WAIT_SECONDS = 15     # Max wait for speech to start


class MicListener:
    """
    Ella's microphone listener — captures voice and detects speech.
    
    Uses Silero VAD (Voice Activity Detection) running offline via ONNX
    to determine exactly when user starts and stops speaking.
    """

    def __init__(self):
        self.sample_rate = SAMPLE_RATE
        self.channels = CHANNELS
        self.chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION) # 512
        self.is_listening = False
        self._sd = None
        self.vad = None
        self._load_sounddevice()
        self._load_vad()

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

    def _load_vad(self):
        """Load Silero VAD."""
        try:
            from voice.vad import VoiceActivityDetector
            self.vad = VoiceActivityDetector(sample_rate=self.sample_rate)
        except Exception as e:
            log.error(f"Failed to load VAD in MicListener: {e}")

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
        
        1. Resets VAD state
        2. Stream-reads audio chunks (32ms) from mic
        3. Passes chunks through Silero VAD
        4. Detects speech start -> records -> speech end -> returns audio
        
        Returns None if no speech detected within MAX_WAIT_SECONDS.
        """
        if self._sd is None or self.vad is None:
            log.error("Microphone or VAD not available")
            return None

        # Reset VAD iterator state
        self.vad.reset()

        audio_chunks = []
        is_speaking = False
        record_start = None
        wait_start = time.time()
        
        try:
            with self._sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                blocksize=self.chunk_samples
            ) as stream:
                
                self.is_listening = True
                log.info("VAD listening loop active...")
                
                while self.is_listening:
                    # Read 32ms audio chunk
                    audio_chunk, _ = stream.read(self.chunk_samples)
                    audio_chunk = audio_chunk.flatten()
                    
                    # Run Silero VAD chunk stateful processing
                    vad_event = self.vad.process_chunk(audio_chunk)
                    
                    if not is_speaking:
                        # Waiting for speech to start
                        if vad_event and 'start' in vad_event:
                            is_speaking = True
                            record_start = time.time()
                            audio_chunks.append(audio_chunk)
                            log.info("Speech start detected by Silero VAD.")
                        else:
                            # Timeout check
                            if time.time() - wait_start > MAX_WAIT_SECONDS:
                                log.debug("No speech detected — VAD wait timeout")
                                self.is_listening = False
                                return None
                    else:
                        # User is speaking, record the chunk
                        audio_chunks.append(audio_chunk)
                        
                        # Check for speech end
                        if vad_event and 'end' in vad_event:
                            log.info("Speech end detected by Silero VAD.")
                            break
                        
                        # Safety fallback: max recording limit
                        if record_start and (time.time() - record_start) >= MAX_RECORD_SECONDS:
                            log.warning("Max recording length reached.")
                            break
                
                self.is_listening = False
            
            if not audio_chunks:
                return None
            
            # Combine all chunks
            full_audio = np.concatenate(audio_chunks)
            
            # Check minimum duration
            duration = len(full_audio) / self.sample_rate
            if duration < MIN_SPEECH_DURATION:
                log.debug(f"Audio too short ({duration:.2f}s) — ignoring")
                return None
            
            log.info(f"Recorded {duration:.2f}s of audio")
            return full_audio
            
        except Exception as e:
            log.error(f"Mic listener error: {e}")
            self.is_listening = False
            return None

    def stop(self):
        """Stop listening."""
        self.is_listening = False
