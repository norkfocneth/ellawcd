#!/usr/bin/env python3
# ──────────────────────────────────────────────
# ELLA-WCD v2.0 — Main Entry Point
# Autonomous Self-Learning Browser Agent
# ──────────────────────────────────────────────

import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

from config import APP_NAME, TAGLINE, VERSION, USER_NAME, MODEL_NAME
from logger import get_logger
from events import event_bus, Event

log = get_logger("main")
console = Console()

# ── ASCII Art Logo ─────────────────────────────

ELLA_WCD_LOGO = """
 ███████╗██╗     ██╗      █████╗     ██╗    ██╗ ██████╗██████╗ 
 ██╔════╝██║     ██║     ██╔══██╗    ██║    ██║██╔════╝██╔══██╗
 █████╗  ██║     ██║     ███████║    ██║ █╗ ██║██║     ██║  ██║
 ██╔══╝  ██║     ██║     ██╔══██║    ██║███╗██║██║     ██║  ██║
 ███████╗███████╗███████╗██║  ██║    ╚███╔███╔╝╚██████╗██████╔╝
 ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚══╝╚══╝  ╚═════╝╚═════╝ 
"""


def boot_sequence():
    """
    Diagnostic boot sequence for ELLA-WCD v2.0.
    Checks Ollama Brain, WebCMD Browser daemon, and SQLite memory.
    """
    console.clear()

    # ── Header ─────────────────────────────────
    logo_text = Text(ELLA_WCD_LOGO, style="bold cyan")
    console.print(Align.center(logo_text))

    tagline = Text(f"  {TAGLINE}  ", style="bold white on blue")
    console.print(Align.center(tagline))

    ver_text = Text(f"  v{VERSION} │ Windows CLI Edition  ", style="dim")
    console.print(Align.center(ver_text))
    console.print()

    # ── Diagnostic Checks ──────────────────────
    console.print("  [bold yellow]●[/bold yellow] Checking Ollama Brain...", end="")
    from brain.qwen import QwenBrain
    brain = QwenBrain()

    if brain.is_available():
        console.print(f" [green]✓[/green] [dim]({brain.active_model} online)[/dim]")
    else:
        console.print(f" [red]✗[/red] [dim](Ollama not reachable on :11434)[/dim]")
        console.print(
            Panel(
                "[yellow]Ollama server is not responding.[/yellow]\n\n"
                "To resolve:\n"
                "  1. Start Ollama: [cyan]ollama serve[/cyan]\n"
                f"  2. Verify model: [cyan]ollama run {MODEL_NAME}[/cyan]\n"
                "  3. Restart ELLA: [cyan]python main.py[/cyan]",
                title="[red]Brain Connection Issue[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return None

    console.print("  [bold yellow]●[/bold yellow] Checking WebCMD Browser Engine...", end="")
    from automation.webcmd_bridge import WebcmdBridge
    webcmd = WebcmdBridge()
    doc = webcmd.check_doctor()

    if doc.get("ok"):
        console.print(" [green]✓[/green] [dim](Cloak stealth browser ready)[/dim]")
    else:
        console.print(f" [yellow]![/yellow] [dim]({doc.get('error', 'Status OK')})[/dim]")

    console.print("  [bold yellow]●[/bold yellow] Connecting Memory Store...", end="")
    from memory import Memory
    mem = Memory()
    console.print(f" [green]✓[/green] [dim]({Path(mem.db_path).name})[/dim]")

    console.print("  [bold yellow]●[/bold yellow] Voice Subsystem...", end="")
    console.print(" [dim italic]Disabled (Text/CLI Mode)[/dim italic]")

    # ── Status Panel ───────────────────────────
    console.print()
    console.print(
        Panel(
            f"[bold green]ELLA-WCD System Ready.[/bold green]\n"
            f"[dim]Brain: {brain.active_model}  │  Browser: WebCMD Cloak  │  Vision: Qwen3-VL Fallback  │  Operator: {USER_NAME}[/dim]",
            border_style="green",
            padding=(0, 2),
        )
    )

    log.info(f"Boot complete — model: {brain.active_model}, user: {USER_NAME}")
    return brain


def main():
    """Main entry point for ELLA-WCD."""
    if "--help" in sys.argv or "-h" in sys.argv:
        from conversation import ConversationManager
        from brain.qwen import QwenBrain
        b = QwenBrain()
        cm = ConversationManager(b)
        cm._print_help()
        return 0

    if "--version" in sys.argv or "-v" in sys.argv:
        console.print(f"{APP_NAME} v{VERSION}")
        return 0

    try:
        brain = boot_sequence()
        if brain is None:
            return 1

        from conversation import ConversationManager
        convo = ConversationManager(brain)
        convo.start()
        return 0

    except KeyboardInterrupt:
        console.print("\n\n  [dim]ELLA-WCD session ended.[/dim]\n")
        log.info("ELLA-WCD terminated by user")
        return 0
    except Exception as e:
        log.error(f"Fatal startup error: {e}")
        console.print(f"\n  [red]Fatal Error:[/red] {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
