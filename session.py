# ──────────────────────────────────────────────
# Project Ella v1.0 — Session State Machine
# Smart lifecycle: BOOT → ACTIVE → SLEEPING → EXIT
# ──────────────────────────────────────────────

import time
import threading
from enum import Enum

from config import SLEEP_TIMEOUT, USER_NAME
from logger import get_logger
from events import event_bus, Event

log = get_logger("session")


class SessionState(Enum):
    """Ella's session states."""
    BOOT = "boot"
    ACTIVE = "active"
    SLEEPING = "sleeping"
    EXIT = "exit"


class SessionManager:
    """
    Manages Ella's lifecycle states.
    
    State Transitions:
        BOOT → ACTIVE           (boot complete, ready for chat)
        ACTIVE → SLEEPING       (inactivity timeout, user gone silent)
        SLEEPING → ACTIVE       (user types or says "Ella")
        ACTIVE → EXIT           (user says bye/exit/stop)
        SLEEPING → EXIT         (user says bye/exit/stop)
    
    The inactivity timer runs in background. When user is silent for
    SLEEP_TIMEOUT seconds (default 120s), Ella auto-sleeps.
    Every user interaction resets the timer.
    
    Usage:
        session = SessionManager()
        session.set_state(SessionState.ACTIVE)
        session.reset_inactivity()   # call on every user message
        session.on_sleep(callback)   # register sleep callback
        session.on_wake(callback)    # register wake callback
    """

    def __init__(self, sleep_timeout: int = None):
        self.state = SessionState.BOOT
        self.sleep_timeout = sleep_timeout or SLEEP_TIMEOUT
        self.last_activity_time = time.time()
        
        # Callbacks
        self._on_sleep_callbacks = []
        self._on_wake_callbacks = []
        
        # Inactivity timer thread
        self._timer_thread = None
        self._timer_running = False
        
        log.info(f"SessionManager initialized — timeout: {self.sleep_timeout}s")

    # ═══════════════════════════════════════════
    # STATE MANAGEMENT
    # ═══════════════════════════════════════════

    def set_state(self, new_state: SessionState) -> None:
        """Transition to a new state."""
        old_state = self.state
        
        if old_state == new_state:
            return
        
        self.state = new_state
        
        log.info(f"State: {old_state.value} → {new_state.value}")
        
        event_bus.emit(Event(
            name="SessionStateChanged",
            source="session",
            data={"old_state": old_state.value, "new_state": new_state.value}
        ))

    def is_active(self) -> bool:
        """Check if Ella is in ACTIVE state."""
        return self.state == SessionState.ACTIVE

    def is_sleeping(self) -> bool:
        """Check if Ella is in SLEEPING state."""
        return self.state == SessionState.SLEEPING

    # ═══════════════════════════════════════════
    # INACTIVITY TIMER
    # ═══════════════════════════════════════════

    def reset_inactivity(self) -> None:
        """Reset the inactivity timer. Call on every user interaction."""
        self.last_activity_time = time.time()
        
        # If Ella was sleeping, wake her up
        if self.state == SessionState.SLEEPING:
            self.wake()

    def start_inactivity_timer(self) -> None:
        """Start background thread that monitors inactivity."""
        if self._timer_running:
            return
        
        self._timer_running = True
        self._timer_thread = threading.Thread(
            target=self._inactivity_monitor,
            daemon=True,
            name="InactivityTimer"
        )
        self._timer_thread.start()
        log.debug("Inactivity timer started")

    def stop_inactivity_timer(self) -> None:
        """Stop the inactivity monitor thread."""
        self._timer_running = False
        log.debug("Inactivity timer stopped")

    def _inactivity_monitor(self) -> None:
        """Background thread: check for inactivity every 5 seconds."""
        while self._timer_running:
            time.sleep(5)  # Check every 5 seconds
            
            if not self._timer_running:
                break
            
            if self.state != SessionState.ACTIVE:
                continue
            
            elapsed = time.time() - self.last_activity_time
            
            if elapsed >= self.sleep_timeout:
                log.info(f"Inactivity detected ({elapsed:.0f}s) — going to sleep")
                self.sleep()

    # ═══════════════════════════════════════════
    # SLEEP / WAKE
    # ═══════════════════════════════════════════

    def sleep(self) -> None:
        """Transition to SLEEPING state."""
        if self.state == SessionState.SLEEPING:
            return
        
        self.set_state(SessionState.SLEEPING)
        
        # Fire sleep callbacks
        for callback in self._on_sleep_callbacks:
            try:
                callback()
            except Exception as e:
                log.error(f"Sleep callback error: {e}")

    def wake(self) -> None:
        """Transition from SLEEPING to ACTIVE state."""
        if self.state != SessionState.SLEEPING:
            return
        
        self.last_activity_time = time.time()
        self.set_state(SessionState.ACTIVE)
        
        # Fire wake callbacks
        for callback in self._on_wake_callbacks:
            try:
                callback()
            except Exception as e:
                log.error(f"Wake callback error: {e}")

    # ═══════════════════════════════════════════
    # CALLBACK REGISTRATION
    # ═══════════════════════════════════════════

    def on_sleep(self, callback) -> None:
        """Register a callback for when Ella goes to sleep."""
        self._on_sleep_callbacks.append(callback)

    def on_wake(self, callback) -> None:
        """Register a callback for when Ella wakes up."""
        self._on_wake_callbacks.append(callback)

    def get_idle_seconds(self) -> float:
        """Get seconds since last user interaction."""
        return time.time() - self.last_activity_time

    def shutdown(self) -> None:
        """Clean shutdown — stop timer, set EXIT state."""
        self.stop_inactivity_timer()
        self.set_state(SessionState.EXIT)
        log.info("Session shutdown complete")
