# ──────────────────────────────────────────────
# Project Ella v1.0 — Conversation Manager
# Text input + Brain + Memory + Voice TTS output
# ──────────────────────────────────────────────

import re
import uuid

from brain.gemma import GemmaBrain
from brain.prompts import SYSTEM_PROMPT, get_greeting, MSG_GOODBYE
from memory import Memory
from voice.tts import TextToSpeech
from logger import get_logger
from events import event_bus, Event

log = get_logger("conversation")


class ConversationManager:
    """
    Manages the chat loop between user and Ella.
    
    Phase 2: Text Input → Brain + Persistent Memory DB + Neural TTS Voice Output
    """

    def __init__(self, brain: GemmaBrain):
        self.brain = brain
        self.memory = Memory()
        self.tts = TextToSpeech()
        self.is_active = False
        self.message_count = 0
        self.session_id = str(uuid.uuid4())[:8]
        
        # Build system prompt with memory context (once, cleanly)
        self._build_full_system_prompt()
        log.info("ConversationManager initialized with Memory & TTS Voice")

    def _build_full_system_prompt(self):
        """
        Build the full system prompt from base prompt + memory context.
        Does NOT keep appending — rebuilds from scratch each time.
        """
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

    def start(self) -> None:
        """Start the interactive text conversation loop."""
        self.is_active = True
        
        # Track session
        self.memory.start_session(self.session_id)
        
        # Emit session start event
        event_bus.emit(Event(
            name="SessionStateChanged",
            source="conversation",
            data={"old_state": "boot", "new_state": "active"}
        ))
        
        # Display and speak greeting
        greeting = get_greeting()
        self._display_ella_response(greeting)
        self.tts.speak(greeting, block=False)
        
        log.info("Conversation started — text + voice mode")
        
        # Main chat loop
        while self.is_active:
            try:
                user_input = self._get_user_input()
                
                if user_input is None:
                    break
                
                if not user_input.strip():
                    continue
                
                # Check for exit commands
                if self._is_exit_command(user_input):
                    self._display_ella_response(MSG_GOODBYE)
                    self.tts.speak(MSG_GOODBYE, block=True)
                    break
                
                # Process the message
                self._process_message(user_input)
                
            except KeyboardInterrupt:
                print()
                self._display_ella_response(MSG_GOODBYE)
                break
        
        self.is_active = False
        
        # End session tracking
        self.memory.end_session(
            self.session_id,
            message_count=self.message_count
        )
        
        # Close memory DB cleanly
        self.memory.close()
        
        # Emit session end event
        event_bus.emit(Event(
            name="SessionStateChanged",
            source="conversation",
            data={"old_state": "active", "new_state": "exit"}
        ))
        
        log.info(f"Conversation ended — {self.message_count} messages exchanged")

    def _process_message(self, user_input: str) -> str:
        """Process user message: stream response, save to memory, speak out loud."""
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
        
        # Strip any stray code/json blocks from response
        clean_response = self._strip_code_blocks(raw_response)
        
        # Save to permanent memory DB
        self.memory.save_conversation(
            user_input, clean_response,
            session_id=self.session_id
        )
        
        # Trim conversation history to prevent context window overflow
        self.brain.trim_conversation(keep_last=30)
        
        # Speak Ella's reply out loud (non-blocking so user can type next)
        self.tts.speak(clean_response, block=False)
        
        return clean_response

    def _get_streamed_response(self, user_input: str) -> str:
        """Stream response from brain and display tokens in real-time."""
        from rich.console import Console
        console = Console()
        
        full_response = ""
        in_code_block = False
        
        console.print("\n  [bold magenta]Ella[/bold magenta]  ", end="")
        
        for chunk in self.brain.chat_stream(user_input):
            full_response += chunk
            
            # Track code block state to suppress printing hidden blocks
            if "```" in chunk:
                if in_code_block:
                    in_code_block = False
                    continue
                # Check if this is a ella_memory or json block
                remaining = full_response[full_response.rfind("```"):]
                if any(tag in remaining.lower() for tag in ["ella_memory", "json"]):
                    in_code_block = True
                    continue
            
            if in_code_block:
                continue
            
            console.print(chunk, end="", highlight=False)
        
        console.print()
        return full_response

    def _strip_code_blocks(self, text: str) -> str:
        """Remove all code blocks (```...```) from response text."""
        cleaned = re.sub(r'```(?:ella_memory|json)?\s*\n.*?\n```', '', text, flags=re.DOTALL)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _display_ella_response(self, text: str) -> None:
        """Display a pre-formatted Ella response (not from brain)."""
        from rich.console import Console
        console = Console()
        console.print(f"\n  [bold magenta]Ella[/bold magenta]  {text}")

    def _get_user_input(self) -> str | None:
        """Get text input from the user."""
        try:
            from rich.console import Console
            console = Console()
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
        """Send a message programmatically (not from user input loop)."""
        self.message_count += 1
        response = self.brain.chat(message)
        return response
