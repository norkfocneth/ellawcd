# ──────────────────────────────────────────────
# Project Ella v1.0 — Conversation Manager
# Text + Voice input → Brain → Memory → Voice output
# Fully Hands-Free capable!
# ──────────────────────────────────────────────

import re
import uuid
import time
import threading

from brain.gemma import GemmaBrain
from brain.prompts import SYSTEM_PROMPT, get_greeting, MSG_GOODBYE, MSG_SLEEPING, MSG_WAKING
from memory import Memory
from voice.tts import TextToSpeech
from voice.stt import WhisperSTT
from voice.listener import MicListener
from session import SessionManager, SessionState
from logger import get_logger
from events import event_bus, Event

log = get_logger("conversation")


class ConversationManager:
    """
    Manages the chat loop between user and Ella.
    
    Supports TWO input modes:
        TEXT MODE  → User types in terminal, Ella replies text + voice
        VOICE MODE → User speaks into mic, Ella listens + replies voice
    
    Toggle: Type "voice" to switch to voice mode, "text" to switch back.
    In voice mode, Ella continuously listens to mic for hands-free chat.
    """

    def __init__(self, brain: GemmaBrain):
        self.brain = brain
        self.memory = Memory()
        self.tts = TextToSpeech()
        self.session = SessionManager()
        self.is_active = False
        self.message_count = 0
        self.session_id = str(uuid.uuid4())[:8]
        
        # Voice input modules (lazy-loaded)
        self.stt = None
        self.listener = None
        self.voice_mode = False
        
        # Register sleep/wake callbacks
        self.session.on_sleep(self._handle_sleep)
        self.session.on_wake(self._handle_wake)
        
        # Build system prompt with memory context
        self._build_full_system_prompt()
        log.info("ConversationManager initialized — text + voice ready")

    def _init_voice_input(self):
        """Initialize STT and Mic listener (called once when voice mode activated)."""
        from rich.console import Console
        console = Console()
        
        if self.stt is None:
            console.print("\n  [bold yellow]●[/bold yellow] Loading Whisper STT model...", end="")
            self.stt = WhisperSTT()
            if self.stt.is_available():
                console.print(" [green]✓[/green]")
            else:
                console.print(" [red]✗[/red]")
                return False
        
        if self.listener is None:
            console.print("  [bold yellow]●[/bold yellow] Connecting microphone...", end="")
            self.listener = MicListener()
            if self.listener.is_available():
                console.print(" [green]✓[/green]")
            else:
                console.print(" [red]✗[/red]")
                return False
        
        return True

    def _build_full_system_prompt(self):
        """Build full system prompt from base + memory context."""
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
        """Start the interactive conversation loop."""
        self.is_active = True
        
        self.memory.start_session(self.session_id)
        self.session.set_state(SessionState.ACTIVE)
        self.session.start_inactivity_timer()
        
        # Greet the user
        greeting = get_greeting()
        self._display_ella(greeting)
        self.tts.speak(greeting, block=False)
        
        # Show mode hint
        from rich.console import Console
        console = Console()
        console.print("  [dim]Type 'voice' for hands-free mode │ 'text' to switch back │ 'bye' to exit[/dim]")
        
        log.info("Conversation started — text + voice mode")
        
        while self.is_active:
            try:
                if self.voice_mode:
                    user_input = self._get_voice_input()
                else:
                    user_input = self._get_text_input()
                
                if user_input is None:
                    break
                
                if not user_input.strip():
                    continue
                
                # Smart Wake Logic
                if self.session.is_sleeping():
                    if self.voice_mode:
                        # In voice mode, REQUIRE wake word to wake up
                        lower_input = user_input.lower()
                        wake_phrases = ["ella", "hey ella", "wake up", "rise ella"]
                        if not any(phrase in lower_input for phrase in wake_phrases):
                            log.debug("Ignored background speech while sleeping.")
                            continue
                        
                        # Wake word detected
                        self.session.wake()
                        user_input = re.sub(r'^(hey\s+)?ella[,.!?]?\s*', '', user_input, flags=re.IGNORECASE).strip()
                        user_input = re.sub(r'^(wake\s+up|rise)\s*', '', user_input, flags=re.IGNORECASE).strip()
                        
                        if not user_input:
                            self._display_ella(MSG_WAKING)
                            self.tts.speak(MSG_WAKING, block=True)
                            continue
                    else:
                        # In text mode, any typing wakes her up
                        self.session.wake()
                else:
                    # Already active, just reset the timer
                    self.session.reset_inactivity()
                
                # Handle mode switching commands
                cmd = user_input.strip().lower()
                
                if cmd == "voice":
                    self._switch_to_voice_mode()
                    continue
                
                if cmd == "text":
                    self._switch_to_text_mode()
                    continue
                
                if cmd == "reset":
                    self.brain.reset_conversation()
                    self._display_ella("Conversation memory cleared. Starting fresh!")
                    self.tts.speak("Memory cleared. Starting fresh.", block=False)
                    continue
                
                if self._is_exit_command(cmd):
                    self._display_ella(MSG_GOODBYE)
                    self.tts.speak(MSG_GOODBYE, block=True)
                    break
                
                # Check for sleep commands
                if self._is_sleep_command(cmd):
                    self.session.set_state(SessionState.SLEEPING)
                    self._handle_sleep()
                    continue
                
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
    # INPUT MODES
    # ═══════════════════════════════════════════

    def _get_text_input(self) -> str | None:
        """Get text input from terminal."""
        try:
            from rich.console import Console
            console = Console()
            
            if self.session.is_sleeping():
                user_input = console.input("\n  [dim]zzz...[/dim] [bold cyan]You[/bold cyan]   ")
            else:
                user_input = console.input("\n  [bold cyan]You[/bold cyan]   ")
            return user_input
        except EOFError:
            return None

    def _get_voice_input(self) -> str | None:
        """Get voice input from microphone → STT transcription."""
        from rich.console import Console
        console = Console()
        
        if self.listener is None or self.stt is None:
            self._switch_to_text_mode()
            return self._get_text_input()
        
        # Wait for TTS to finish speaking before opening mic
        # This prevents Ella from hearing herself
        time.sleep(0.6)
        
        # Show listening indicator
        console.print("\n  [bold green]Listening...[/bold green] [dim](speak now)[/dim]", end="")
        
        # Capture audio from mic (blocks until speech detected + ended)
        audio = self.listener.listen_once()
        
        if audio is None:
            console.print("\r  [dim]...waiting for voice...[/dim]                              ", end="\r")
            return ""
        
        # Show that we're processing
        duration = len(audio) / self.listener.sample_rate
        console.print(f"\r  [bold yellow]Processing {duration:.1f}s audio...[/bold yellow]                    ", end="")
        
        # Transcribe audio to text
        text = self.stt.transcribe(audio)
        
        if text:
            console.print(f"\r  [bold cyan]You[/bold cyan]   {text}                                        ")
            return text
        else:
            console.print("\r  [dim]...[/dim]                                                               ", end="\r")
            return ""

    def _switch_to_voice_mode(self):
        """Switch to voice input mode (hands-free)."""
        from rich.console import Console
        console = Console()
        
        console.print("\n  [bold green]Switching to Voice Mode...[/bold green]")
        
        success = self._init_voice_input()
        
        if success:
            self.voice_mode = True
            msg = "Voice mode activated. I'm listening. Go ahead!"
            self._display_ella(msg)
            self.tts.speak(msg, block=True)  # Wait for speech to finish before mic opens!
            console.print("  [dim]Say 'text mode' to switch back │ 'bye' to exit[/dim]")
        else:
            msg = "Sorry, could not start voice mode. Microphone or STT model failed to load."
            self._display_ella(msg)
            self.tts.speak(msg, block=True)
            self.voice_mode = False

    def _switch_to_text_mode(self):
        """Switch back to text input mode."""
        from rich.console import Console
        console = Console()
        
        self.voice_mode = False
        if self.listener:
            self.listener.stop()
        
        msg = "Switched to text mode. Go ahead and type!"
        self._display_ella(msg)
        self.tts.speak(msg, block=False)

    # ═══════════════════════════════════════════
    # MESSAGE PROCESSING
    # ═══════════════════════════════════════════

    def _process_message(self, user_input: str) -> str:
        """Process user message: stream → clean → save → speak."""
        self.message_count += 1
        
        log.info(f"User: {user_input[:80]}")
        
        event_bus.emit(Event(
            name="TranscriptionReady",
            source="conversation",
            data={"text": user_input, "source": "voice" if self.voice_mode else "text", "confidence": 1.0}
        ))
        
        # Check if user said "text mode" via voice
        if self.voice_mode and user_input.strip().lower() in {"text mode", "text", "type mode"}:
            self._switch_to_text_mode()
            return ""
        
        raw_response = self._get_streamed_response(user_input)
        clean_response = self._strip_code_blocks(raw_response)
        
        # Post-generation hallucination guard
        clean_response = self._filter_response_hallucinations(clean_response)
        
        # If response was empty after stripping, set friendly fallback
        if not clean_response:
            clean_response = "Sorry, I didn't catch that. Could you say that again?"
            from rich.console import Console
            Console().print(clean_response)
        
        self.memory.save_conversation(
            user_input, clean_response, session_id=self.session_id
        )
        
        self.brain.trim_conversation(keep_last=30)
        self.tts.speak(clean_response, block=self.voice_mode)  # block in voice mode so mic doesn't hear Ella
        
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

    def _filter_response_hallucinations(self, text: str) -> str:
        """Filter out known LLM hallucination patterns from responses."""
        if not text:
            return ""
        
        # Catch .Clear.Clear.Clear repetition loops
        if ".clear" in text.lower() and text.lower().count("clear") > 2:
            log.warning(f"Filtered hallucinated response: '{text[:50]}'")
            return ""
        
        # Catch any word/phrase repeated more than 5 times
        words = text.split()
        if len(words) >= 5:
            from collections import Counter
            counts = Counter(words)
            most_common_word, most_common_count = counts.most_common(1)[0]
            if most_common_count > 5 and most_common_count / len(words) > 0.5:
                log.warning(f"Filtered repetitive response: '{text[:50]}'")
                return ""
        
        return text

    # ═══════════════════════════════════════════
    # SLEEP / WAKE HANDLERS
    # ═══════════════════════════════════════════

    def _handle_sleep(self):
        self._display_ella(MSG_SLEEPING)
        self.tts.speak(MSG_SLEEPING, block=False)

    def _handle_wake(self):
        self._display_ella(MSG_WAKING)
        self.tts.speak(MSG_WAKING, block=False)

    # ═══════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════

    def _strip_code_blocks(self, text: str) -> str:
        cleaned = re.sub(r'```(?:ella_memory|json)?\s*\n.*?\n```', '', text, flags=re.DOTALL)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _display_ella(self, text: str):
        from rich.console import Console
        Console().print(f"\n  [bold magenta]Ella[/bold magenta]  {text}")

    def _is_exit_command(self, text: str) -> bool:
        exit_commands = {
            "exit", "quit", "bye", "bye ella", "stop", "stop ella",
            "goodbye", "close", "close ella", "shutdown", "shutdown ella",
            "band karo", "chal bye", "nikal",
        }
        return text.strip().lower() in exit_commands

    def _is_sleep_command(self, text: str) -> bool:
        """Check if user wants Ella to go to sleep (stop listening until wake word)."""
        sleep_commands = {
            "sleep", "go to sleep", "sleep ella", "ella sleep",
            "so jao", "chup", "shh", "quiet", "mute",
        }
        return text.strip().lower() in sleep_commands

    def send_message(self, message: str) -> str:
        self.message_count += 1
        return self.brain.chat(message)
