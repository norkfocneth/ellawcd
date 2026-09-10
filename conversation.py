# ──────────────────────────────────────────────
# ELLA-WCD v2.0 — Conversation Manager
# Autonomous Browser Agent Command Loop (CMD-Only)
# ──────────────────────────────────────────────

import re
import sys
import uuid
import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from brain.qwen import QwenBrain
from automation.webcmd_bridge import WebcmdBridge
from automation.orchestrator import BrowserOrchestrator
from memory import Memory
from session import SessionManager, SessionState
from ui import console, print_ai_response, EllaMarkdown
from config import APP_NAME, VERSION, USER_NAME
from logger import get_logger

log = get_logger("conversation")

BROWSER_INTENT_KEYWORDS = [
    "search", "find", "open", "browse", "paper", "papers", "arxiv", "github",
    "extract", "compare", "lookup", "website", "url", "http", "www", "article",
    "summary", "price", "documentation", "scrape", "google", "brave", "bravesearch",
    "laptop", "laptops", "amazon", "flipkart", "croma", "ecommerce", "buy", "store",
    "deal", "deals", "dhoondo", "khojo", "dekho", "kholo", "batao"
]


class ConversationManager:
    """
    Interactive CMD loop for ELLA-WCD.
    Directs natural language tasks to the Autonomous Browser Orchestrator
    or conversational brain, and processes slash commands.
    """

    def __init__(self, brain: QwenBrain):
        self.brain = brain
        self.webcmd = WebcmdBridge()
        self.orchestrator = BrowserOrchestrator(brain=self.brain, webcmd=self.webcmd)
        self.memory = Memory()
        self.session = SessionManager()
        self.is_active = False
        self.message_count = 0
        self.session_id = str(uuid.uuid4())[:8]

        log.info(f"ConversationManager initialized — {APP_NAME} v{VERSION} ready")

    def _is_browser_task(self, text: str) -> bool:
        """Heuristic to detect if a prompt requires autonomous browser action."""
        lower = text.lower()
        # Explicit URLs or domains
        if "http://" in lower or "https://" in lower or ".com" in lower or ".org" in lower:
            return True
        # Keywords indicating web research or navigation
        return any(kw in lower for kw in BROWSER_INTENT_KEYWORDS)

    def _handle_slash_command(self, cmd: str) -> bool:
        """Handle internal CLI slash commands. Returns True if handled."""
        parts = cmd.strip().split()
        root = parts[0].lower()

        if root in ["/help", "help", "?"]:
            self._print_help()
            return True

        elif root in ["/exit", "/quit", "exit", "quit", "bye", "shutdown"]:
            console.print(f"\n[dim]Shutting down {APP_NAME}. All browser sessions closed. Goodbye {USER_NAME}![/dim]\n")
            self.is_active = False
            return True

        elif root == "/reset" or root == "/clear":
            self.brain.reset()
            self.webcmd.current_session = None
            console.clear()
            console.print(f"[green]✓ Context reset. Starting fresh session.[/green]\n")
            return True

        elif root in ["/doctor", "/webcmd"]:
            console.print("[yellow]Running WebCMD diagnostic...[/yellow]")
            doc = self.webcmd.check_doctor()
            console.print(Panel(
                doc.get("output", "WebCMD doctor passed successfully."),
                title="[bold green]WebCMD Diagnostic[/bold green]",
                border_style="green"
            ))
            return True

        elif root == "/model":
            if len(parts) > 1:
                new_model = parts[1]
                self.brain.preferred_model = new_model
                self.brain.active_model = new_model
                console.print(f"[green]Switched active brain model to: {new_model}[/green]")
            else:
                console.print(f"[cyan]Active Brain Model:[/cyan] [bold]{self.brain.active_model}[/bold]")
            return True

        elif root == "/headless":
            if len(parts) > 1 and parts[1].lower() in ["off", "false", "0"]:
                self.webcmd.headless = False
                console.print("[green]Browser Headless Mode: OFF (Browser will be visible)[/green]")
            else:
                self.webcmd.headless = True
                console.print("[green]Browser Headless Mode: ON (Stealth background execution)[/green]")
            return True

        elif root in ["/memory", "/recipes"]:
            recipes = self.memory.get_all_recipes()
            console.print(f"[cyan]Learned Memory Store: SQLite ({self.memory.db_path})[/cyan]")
            console.print(f"[cyan]Learned Automation Recipes: [bold green]{len(recipes)}[/bold green][/cyan]")
            for r in recipes:
                console.print(f"  • [bold yellow]{r['domain']}[/bold yellow] ({r['task_pattern']}): action=[green]{r['action_type']}[/green], hits=[green]{r['success_count']}x[/green]")
            return True

        return False

    def _print_help(self) -> None:
        """Print CLI commands help panel."""
        console.print(Panel(
            "[bold cyan]Available Commands:[/bold cyan]\n"
            "  [bold green]Just type your task[/bold green] — ELLA plans and runs autonomous browser workflows\n"
            "  [yellow]/help[/yellow]             — Show this help screen\n"
            "  [yellow]/doctor[/yellow]           — Test WebCMD browser connectivity and stealth daemon\n"
            "  [yellow]/model [name][/yellow]    — Show or switch active Ollama brain model\n"
            "  [yellow]/headless [on|off][/yellow] — Toggle visible browser window\n"
            "  [yellow]/recipes[/yellow]          — View cached self-learned browser automation recipes\n"
            "  [yellow]/reset[/yellow]            — Reset conversation context and clear active tabs\n"
            "  [yellow]/exit[/yellow]             — Safely close browser and exit\n\n"
            "[bold cyan]Example Tasks:[/bold cyan]\n"
            "  • [italic]Compare best RTX 3050 laptops under 1 lakh across Amazon, Flipkart, Vijay Sales[/italic]\n"
            "  • [italic]Find 5 recent research papers about AI browser agents from arXiv[/italic]\n"
            "  • [italic]Search GitHub for trending open source web automation agents[/italic]\n"
            "  • [italic]Open python.org and check the latest stable release version[/italic]",
            title="[bold magenta]ELLA-WCD v2.0 Guide[/bold magenta]",
            border_style="magenta",
            padding=(1, 2)
        ))

    def start(self) -> None:
        """Launch the main CMD interaction loop."""
        self.is_active = True
        self.memory.start_session(self.session_id)
        self.session.set_state(SessionState.ACTIVE)

        console.print()
        console.print(f"[dim]Type your task in English or Hinglish. Type '/help' for commands, '/exit' to quit.[/dim]")
        console.print()

        while self.is_active:
            try:
                user_input = console.input("[bold magenta]ELLA > [/bold magenta]").strip()

                if not user_input:
                    continue

                # Check slash / system commands
                if user_input.startswith("/") or user_input.lower() in ["exit", "quit", "bye", "help"]:
                    if self._handle_slash_command(user_input):
                        continue

                self.message_count += 1

                # Route: Browser Task vs General Reasoning
                if self._is_browser_task(user_input):
                    # Autonomous Browser Execution Loop
                    self.orchestrator.execute_task(user_input)
                else:
                    # Conversational / Brain reasoning
                    with console.status("[bold bright_magenta]✦[/bold bright_magenta] [bold bright_cyan]Thinking...[/bold bright_cyan]", spinner="dots"):
                        reply = self.brain.chat(user_input)
                    print_ai_response(reply, model_name=self.brain.active_model)

            except KeyboardInterrupt:
                console.print("\n[dim]Action cancelled.[/dim]\n")
                continue
            except EOFError:
                break
            except Exception as e:
                log.error(f"Error in chat loop: {e}")
                console.print(Panel(
                    f"[bold bright_yellow]Task Notice:[/bold bright_yellow] {e}\n\n"
                    f"[dim]Ella encountered an unexpected condition while processing this request. The browser session was safely reset.[/dim]",
                    title="[bold red]Execution Status[/bold red]",
                    border_style="red",
                    padding=(1, 2)
                ))
