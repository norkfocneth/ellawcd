# ──────────────────────────────────────────────
# Project Ella v1.0 — Silence / Inactivity Detector
# Auto-sleep when user is silent for too long
# ──────────────────────────────────────────────

import time
from logger import get_logger

log = get_logger("voice.silence")


class SilenceDetector:
    """
    Detects user inactivity for auto-sleep.
    
    Works with text input (Phase 3) — tracks time since
    last user message. Later phases can add mic-level
    silence detection.
    
    Usage:
        detector = SilenceDetector(timeout=120)
        detector.mark_activity()     # on user input
        detector.is_silent()         # True if idle > timeout
        detector.idle_seconds()      # seconds since last activity
    """

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self.last_activity = time.time()
        log.info(f"SilenceDetector initialized — timeout: {timeout}s")

    def mark_activity(self) -> None:
        """Mark that user interaction happened right now."""
        self.last_activity = time.time()

    def is_silent(self) -> bool:
        """Check if user has been inactive beyond timeout."""
        return self.idle_seconds() >= self.timeout

    def idle_seconds(self) -> float:
        """Get seconds since last user activity."""
        return time.time() - self.last_activity

    def reset(self) -> None:
        """Reset the detector (same as mark_activity)."""
        self.mark_activity()
