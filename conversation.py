# ──────────────────────────────────────────────
# Project Ella v1.0 — Conversation Manager
# Text chat loop with message history
# ──────────────────────────────────────────────

from brain.gemma import GemmaBrain
from brain.prompts import get_greeting, MSG_GOODBYE
from logger import get_logger
from events import event_bus, Event

log = get_logger("conversation")


class ConversationManager:
    """
    Manages the chat loop between user and Ella.
    
    Phase 1: Text-only input/output via terminal.
    Phase 2+: Will integrate with voice (STT/TTS).
    
    Usage:
        brain = GemmaBrain()
        convo = ConversationManager(brain)
        convo.start()
    """

    def __init__(self, brain: GemmaBrain):
        """
        Initialize conversation manager.
        
        Args:
            brain: GemmaBrain instance for generating responses
        """
        self.brain = brain
        self.is_active = False
        self.message_count = 0
        log.info("ConversationManager initialized")

    def start(self) -> None:
        """
        Start the interactive text conversation loop.
        
        Runs until user types 'exit', 'quit', 'bye', or 'stop ella'.
        """
        self.is_active = True
        
        # Emit session start event
        event_bus.emit(Event(
            name="SessionStateChanged",
            source="conversation",
            data={"old_state": "boot", "new_state": "active"}
        ))
        
        # Display greeting
        greeting = get_greeting()
        self._display_ella_response(greeting)
        
        log.info("Conversation started — text mode")
        
        # Main chat loop
        while self.is_active:
            try:
                # Get user input
                user_input = self._get_user_input()
                
                if user_input is None:
                    # User pressed Ctrl+C or EOF
                    break
                
                if not user_input.strip():
                    continue
                
                # Check for exit commands
                if self._is_exit_command(user_input):
                    self._display_ella_response(MSG_GOODBYE)
                    break
                
                # Process the message
                self._process_message(user_input)
                
            except KeyboardInterrupt:
                print()  # New line after ^C
                self._display_ella_response(MSG_GOODBYE)
                break
        
        self.is_active = False
        
        # Emit session end event
        event_bus.emit(Event(
            name="SessionStateChanged",
            source="conversation",
            data={"old_state": "active", "new_state": "exit"}
        ))
        
        log.info(f"Conversation ended — {self.message_count} messages exchanged")

    def _process_message(self, user_input: str) -> str:
        """
        Process a single user message and get response.
        
        Args:
            user_input: The user's text
            
        Returns:
            Ella's response text
        """
        self.message_count += 1
        
        log.info(f"User: {user_input[:80]}{'...' if len(user_input) > 80 else ''}")
        
        # Emit user message event
        event_bus.emit(Event(
            name="TranscriptionReady",
            source="conversation",
            data={"text": user_input, "source": "text", "confidence": 1.0}
        ))
        
        # Get response from brain (streamed for real-time display)
        response = self._get_streamed_response(user_input)
        
        return response

    def _get_streamed_response(self, user_input: str) -> str:
        """
        Get and display a streamed response from the brain.
        
        Shows each token as it arrives for a real-time feel.
        """
        from rich.console import Console
        console = Console()
        
        full_response = ""
        
        # Print Ella's name prefix
        console.print("\n  [bold magenta]Ella[/bold magenta]  ", end="")
        
        # Stream tokens
        for chunk in self.brain.chat_stream(user_input):
            console.print(chunk, end="", highlight=False)
            full_response += chunk
        
        # Final newline
        console.print()
        
        log.info(f"Ella: {full_response[:80]}{'...' if len(full_response) > 80 else ''}")
        
        return full_response

    def _display_ella_response(self, text: str) -> None:
        """Display a pre-formatted Ella response (not from brain)."""
        from rich.console import Console
        from rich.panel import Panel
        
        console = Console()
        console.print(f"\n  [bold magenta]Ella[/bold magenta]  {text}")

    def _get_user_input(self) -> str | None:
        """
        Get text input from the user.
        
        Returns:
            User's input string, or None if EOF/interrupt
        """
        try:
            from rich.console import Console
            console = Console()
            
            # User prompt with styling
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
        """
        Send a message programmatically (not from user input loop).
        Useful for other modules that need to query the brain.
        
        Args:
            message: Text to send to the brain
            
        Returns:
            Brain's response
        """
        self.message_count += 1
        response = self.brain.chat(message)
        return response
