# ──────────────────────────────────────────────
# Project Ella v1.0 — Voice Activity Detection
# Powered by Silero VAD (100% Offline, State-of-the-Art)
# ──────────────────────────────────────────────

import numpy as np
from logger import get_logger
from config import VAD_THRESHOLD

log = get_logger("voice.vad")


class VoiceActivityDetector:
    """
    Local Voice Activity Detection (VAD) wrapper using Silero VAD.
    Accurately detects when the user starts and stops speaking.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.threshold = VAD_THRESHOLD
        self.model = None
        self.vad_iterator = None
        
        # Lazy-loaded on first use
        self._lazy_load()

    def _lazy_load(self):
        """Load Silero VAD model (ONNX format for maximum speed)."""
        if self.model is not None:
            return
            
        try:
            import torch
            from silero_vad import load_silero_vad, VADIterator
            
            # Load ONNX-backed Silero VAD (runs lightning-fast on CPU/GPU)
            self.model = load_silero_vad(onnx=True)
            
            # Initialize stateful streaming iterator
            # min_silence_duration_ms: waits 700ms of silence before marking speech end
            self.vad_iterator = VADIterator(
                self.model,
                threshold=self.threshold,
                sampling_rate=self.sample_rate,
                min_silence_duration_ms=700
            )
            log.info("Silero VAD loaded successfully.")
        except Exception as e:
            log.error(f"Error loading Silero VAD: {e}")

    def reset(self):
        """Reset VAD iterator state (call before starting a new recording session)."""
        if self.vad_iterator:
            self.vad_iterator.reset_states()

    def process_chunk(self, audio_chunk: np.ndarray) -> dict | None:
        """
        Process a single streaming chunk of audio.
        
        Args:
            audio_chunk: numpy float32 array
            
        Returns:
            dict containing speech start or end trigger events, or None.
            Example: {'start': 16000} or {'end': 32000}
        """
        self._lazy_load()
        if self.model is None or self.vad_iterator is None:
            return None
            
        try:
            import torch
            
            # Convert float32 numpy array to torch tensor
            audio_tensor = torch.from_numpy(audio_chunk.astype(np.float32))
            
            # Get VAD event
            vad_output = self.vad_iterator(audio_tensor)
            return vad_output
        except Exception as e:
            log.warning(f"VAD processing failed ({e})")
            return None

    def get_speech_probability(self, audio_chunk: np.ndarray) -> float:
        """
        Get the direct speech probability (0.0 to 1.0) for a chunk.
        
        Args:
            audio_chunk: numpy float32 array (must be 512, 1024, or 1536 samples)
        """
        self._lazy_load()
        if self.model is None:
            return 0.0
            
        try:
            import torch
            
            # Ensure float32 representation
            if audio_chunk.dtype != np.float32:
                audio_chunk = audio_chunk.astype(np.float32)
                
            # Pad chunk if not exact size (Silero expects 512, 1024, or 1536)
            n_samples = len(audio_chunk)
            if n_samples not in [512, 1024, 1536]:
                target = 512 if n_samples < 512 else (1024 if n_samples < 1024 else 1536)
                padded_chunk = np.pad(audio_chunk, (0, target - n_samples), mode='constant')
            else:
                padded_chunk = audio_chunk
                
            audio_tensor = torch.from_numpy(padded_chunk)
            prob = self.model(audio_tensor, self.sample_rate).item()
            return prob
        except Exception as e:
            log.warning(f"VAD probability check failed ({e})")
            return 0.0
