# ──────────────────────────────────────────────
# Project Ella v1.0 — Noise Reduction (DSP)
# Powered by noisereduce (Local, Spectral Gating)
# ──────────────────────────────────────────────

import numpy as np
from logger import get_logger
from config import NOISE_REDUCE_ENABLED, NOISE_REDUCE_PROP

log = get_logger("voice.noise")


class NoiseReducer:
    """
    Local noise reduction wrapper using spectral gating (noisereduce).
    Reduces static microphone noise and keyboard clicks.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.enabled = NOISE_REDUCE_ENABLED
        self.prop = NOISE_REDUCE_PROP
        
        if self.enabled:
            log.info(f"NoiseReducer initialized (Spectral Gating — reduction: {self.prop * 100}%)")
        else:
            log.info("NoiseReducer disabled.")

    def reduce_noise(self, audio: np.ndarray) -> np.ndarray:
        """
        Denoise audio array in-memory.
        
        Args:
            audio: numpy float32 array
        Returns:
            denoised numpy float32 array
        """
        if not self.enabled or len(audio) == 0:
            return audio
            
        try:
            import noisereduce as nr
            
            # Ensure float32 representation
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
                
            # Perform non-stationary/stationary spectral gating noise reduction
            denoised = nr.reduce_noise(
                y=audio,
                sr=self.sample_rate,
                stationary=True,
                prop_decrease=self.prop
            )
            return denoised
        except Exception as e:
            log.warning(f"Noise reduction failed ({e}), returning raw audio.")
            return audio
