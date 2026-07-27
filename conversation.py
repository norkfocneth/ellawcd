# ──────────────────────────────────────────────
# Project Ella v1.0 — Conversation Manager
# Text input + Brain + Memory + Voice + Session
# ──────────────────────────────────────────────

import re
import uuid

from brain.gemma import GemmaBrain
from brain.prompts import SYSTEM_PROMPT, get_greeting, MSG_GOODBYE, MSG_SLEEPING, MSG_WAKING
from memory import Memory
from voice.tts import TextToSpeech
from session import SessionManager, SessionState
from logger import get_logger
from events import event_bus, Event

log = get_logger("conversation")


class ConversationManager:
    """
    Manages the chat loop between user and Ella.
    
    Phase 3: Text Input + Brain + Memory + Voice + Session Lifecycle
    
    Session States:
        ACTIVE   → Normal chat mode (text + voice)
        SLEEPING → Auto-sleeps after 2 min inactivity
        EXIT     → Clean shutdown on bye/exit
    """

    def __init__(self, brain: GemmaBrain):
        self.brain = brain
        self.memory = Memory()
        self.tts = TextToSpeech()
        self.session = SessionManager()
        self.is_active = False
        self.message_count = 0
        self.session_id = str(uuid.uuid4())[:8]
        
        # Register sleep/wake callbacks
        self.session.on_sleep(self._handle_sleep)
        self.session.on_wake(self._handle_wake)
        
        # Build system prompt with memory context
        self._build_full_system_prompt()
        log.info("ConversationManager initialized — Phase 3 ready")

    def _build_full_system_prompt(self):
        """Build full system prompt from base + memory context (no duplication)."""
        try:
            full_prompt = SYSTEM_PROMPT
            
            mem_context = self.memory.build_memory_context()
            if mem_context:
                full_prompt += f"\n\n{mem_context}"
            
            self.brain.system_prompt = full_prompt
            self.brain._init_conversation()
            log.info("System prompt rebuilt with latest memory context")
        except Exception as e:
            log.error(f"Error building system prompt: {e}")

    # ═══════════════════════════════════════════
    # MAIN CHAT LOOP
    # ═══════════════════════════════════════════

    def start(self) -> None:
        """Start the interactive conversation loop with session lifecycle."""
        self.is_active = True
        
        # Track session in memory DB
        self.memory.start_session(self.session_id)
        
        # Set session to ACTIVE
        self.session.set_state(SessionState.ACTIVE)
        
        # Start inactivity timer (auto-sleep after 2 min)
        self.session.start_inactivity_timer()
        
        # Greet the user
        greeting = get_greeting()
        self._display_ella(greeting)
        self.tts.speak(greeting, block=False)
        
        log.info("Conversation started — text + voice + session mode")
        
        # Main chat loop
        while self.is_active:
            try:
                user_input = self._get_user_input()
                
                if user_input is None:
                    break
                
                if not user_input.strip():
                    continue
                
                # Reset inactivity timer on any input
                self.session.reset_inactivity()
                
                # If Ella was sleeping, wake message was already shown by callback
                # Just continue to process the message
                
                # Check for exit commands
                if self._is_exit_command(user_input):
                    self._display_ella(MSG_GOODBYE)
                    self.tts.speak(MSG_GOODBYE, block=True)
                    break
                
                # Process the message
                self._process_message(user_input)
                
            except KeyboardInterrupt:
                print()
                self._display_ella(MSG_GOODBYE)
                break
        
        # Clean shutdown
        self.is_active = False
        self.session.shutdown()
        self.memory.end_session(self.session_id, message_count=self.message_count)
        self.memory.close()
        
        log.info(f"Conversation ended — {self.message_count} messages")

    # ═══════════════════════════════════════════
    # MESSAGE PROCESSING
    # ═══════════════════════════════════════════

    def _process_message(self, user_input: str) -> str:
        """Process user message: stream → clean → save → speak."""
        self.message_count += 1
        
        log.info(f"User: {user_input[:80]}")
        
        # Emit user message event
        event_bus.emit(Event(
            name="TranscriptionReady",
            source="conversation",
            data={"text": user_input, "source": "text", "confidence": 1.0}
        ))
        
        # Stream response from brain
        raw_response = self._get_streamed_response(user_input)
        
        # Strip any stray code/json blocks
        clean_response = self._strip_code_blocks(raw_response)
        
        # Save to memory DB
        self.memory.save_conversation(
            user_input, clean_response,
            session_id=self.session_id
        )
        
        # Trim conversation history to prevent context overflow
        self.brain.trim_conversation(keep_last=30)
        
        # Speak out loud (non-blocking)
        self.tts.speak(clean_response, block=False)
        
        return clean_response

    def _get_streamed_response(self, user_input: str) -> str:
        """Stream response from brain with real-time display."""
        from rich.console import Console
        console = Console()
        
        full_response = ""
        in_code_block = False
        
        console.print("\n  [bold magenta]Ella[/bold magenta]  ", end="")
        
        for chunk in self.brain.chat_stream(user_input):
            full_response += chunk
            
            # Suppress hidden code blocks from terminal display
            if "```" in chunk:
                if in_code_block:
                    in_code_block = False
                    continue
                remaining = full_response[full_response.rfind("```"):]
                if any(tag in remaining.lower() for tag in ["ella_memory", "json"]):
                    in_code_block = True
                    continue
            
            if in_code_block:
                continue
            
            console.print(chunk, end="", highlight=False)
        
        console.print()
        return full_response

    # ═══════════════════════════════════════════
    # SLEEP / WAKE HANDLERS
    # ═══════════════════════════════════════════

    def _handle_sleep(self) -> None:
        """Called when session transitions to SLEEPING."""
        self._display_ella(MSG_SLEEPING)
        self.tts.speak(MSG_SLEEPING, block=False)
        log.info("Ella going to sleep — waiting for user input to wake")

    def _handle_wake(self) -> None:
        """Called when session transitions from SLEEPING to ACTIVE."""
        self._display_ella(MSG_WAKING)
        self.tts.speak(MSG_WAKING, block=False)
        log.info("Ella woke up — back to active mode")

    # ═══════════════════════════════════════════
    # UI HELPERS
    # ═══════════════════════════════════════════

    def _strip_code_blocks(self, text: str) -> str:
        """Remove all code blocks from response text."""
        cleaned = re.sub(r'```(?:ella_memory|json)?\s*\n.*?\n```', '', text, flags=re.DOTALL)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _display_ella(self, text: str) -> None:
        """Display Ella's message in terminal."""
        from rich.console import Console
        console = Console()
        console.print(f"\n  [bold magenta]Ella[/bold magenta]  {text}")

    def _get_user_input(self) -> str | None:
        """Get text input from the user."""
        try:
            from rich.console import Console
            console = Console()
            
            # Show sleeping indicator if Ella is asleep
            if self.session.is_sleeping():
                user_input = console.input("\n  [dim]zzz...[/dim] [bold cyan]You[/bold cyan]   ")
            else:
                user_input = console.input("\n  [bold cyan]You[/bold cyan]   ")
            return user_input
        except EOFError:
            return None

    def _is_exit_command(self, text: str) -> bool:
        """Check if the user wants to exit."""
        exit_commands = {
            "exit", "quit", "bye", "bye ella", "stop", "stop ella",
            "band karo", "goodbye", "chal bye", "nikal", "close",
        }
        return text.strip().lower() in exit_commands

    def send_message(self, message: str) -> str:
        """Send a message programmatically."""
        self.message_count += 1
        response = self.brain.chat(message)
        return response
