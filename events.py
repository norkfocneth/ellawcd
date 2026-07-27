# ──────────────────────────────────────────────
# Project Ella v1.0 — Event Bus
# Central pub/sub system for inter-module communication
# All modules emit and listen to events through this bus
# ──────────────────────────────────────────────

import time
from typing import Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict

from logger import get_logger

log = get_logger("events")


@dataclass
class Event:
    """
    Represents a single event in the system.
    
    Attributes:
        name:      Event identifier (e.g., "ToolFinished", "IntentParsed")
        source:    Module that emitted the event (e.g., "executor", "brain.gemma")
        data:      Arbitrary payload dict
        timestamp: Unix timestamp when event was created
    """
    name: str
    source: str
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return f"Event({self.name} from {self.source})"


class EventBus:
    """
    Central event bus for Project Ella.
    
    All modules communicate through this bus instead of directly
    calling each other. This ensures loose coupling and makes
    debugging trivial — every event is logged.
    
    Usage:
        bus = EventBus()
        
        # Subscribe to events
        bus.subscribe("ToolFinished", my_callback)
        
        # Emit an event
        bus.emit(Event(
            name="ToolFinished",
            source="executor",
            data={"tool": "chrome", "success": True}
        ))
        
        # Unsubscribe
        bus.unsubscribe("ToolFinished", my_callback)
    
    Core Events (defined in ARCHITECTURE.md):
        SpeechReceived      — voice/listener.py
        WakeWordDetected    — voice/listener.py  
        TranscriptionReady  — voice/stt.py
        BrainResponseReady  — brain/gemma.py
        IntentParsed        — brain/intent_parser.py
        TaskCreated         — planner.py
        TaskQueued          — task_queue.py
        PermissionChecked   — permissions.py
        ToolStarted         — executor.py
        ToolFinished        — executor.py
        VerificationDone    — verifier.py
        MemoryUpdated       — memory.py
        VoiceReply          — voice/tts.py
        SessionStateChanged — session.py
        ContextUpdated      — context.py
        ErrorOccurred       — any module
    """

    def __init__(self):
        # event_name -> list of callback functions
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        # Event history for debugging (last N events)
        self._history: list[Event] = []
        self._max_history = 100
        log.info("EventBus initialized")

    def subscribe(self, event_name: str, callback: Callable) -> None:
        """
        Subscribe a callback to an event.
        
        Args:
            event_name: Name of the event to listen for
            callback:   Function to call when event fires. 
                        Signature: callback(event: Event) -> None
        """
        if callback not in self._subscribers[event_name]:
            self._subscribers[event_name].append(callback)
            log.debug(f"Subscribed {callback.__name__} to {event_name}")

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """Remove a callback from an event's subscriber list."""
        if callback in self._subscribers[event_name]:
            self._subscribers[event_name].remove(callback)
            log.debug(f"Unsubscribed {callback.__name__} from {event_name}")

    def emit(self, event: Event) -> None:
        """
        Emit an event to all subscribers.
        
        Each subscriber callback is called synchronously in order.
        All events are logged and stored in history.
        
        Args:
            event: The Event object to emit
        """
        # Log the event
        log.info(f"{event.name} ← {event.source} | {event.data}")
        
        # Store in history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        # Notify all subscribers
        subscribers = self._subscribers.get(event.name, [])
        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                log.error(f"Error in subscriber {callback.__name__} for {event.name}: {e}")
                # Emit an error event (but prevent infinite recursion)
                if event.name != "ErrorOccurred":
                    self.emit(Event(
                        name="ErrorOccurred",
                        source="events",
                        data={
                            "module": f"subscriber.{callback.__name__}",
                            "error": str(e),
                            "original_event": event.name,
                        }
                    ))

    def get_history(self, event_name: str = None, limit: int = 20) -> list[Event]:
        """
        Get recent event history.
        
        Args:
            event_name: Filter by event name (None = all events)
            limit:      Max number of events to return
            
        Returns:
            List of recent Event objects, newest first
        """
        history = self._history
        if event_name:
            history = [e for e in history if e.name == event_name]
        return list(reversed(history[-limit:]))

    def get_subscriber_count(self, event_name: str = None) -> int:
        """Get total number of subscribers, optionally filtered by event name."""
        if event_name:
            return len(self._subscribers.get(event_name, []))
        return sum(len(subs) for subs in self._subscribers.values())

    def clear(self) -> None:
        """Clear all subscribers and history. Used for testing/reset."""
        self._subscribers.clear()
        self._history.clear()
        log.info("EventBus cleared")


# ── Global Event Bus Instance ──────────────────
# All modules import and use this single instance
event_bus = EventBus()
