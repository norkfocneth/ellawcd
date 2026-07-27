#!/usr/bin/env python3
# ──────────────────────────────────────────────
# Project Ella v1.0 — Main Entry Point
# Boot sequence + launch conversation
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

ELLA_LOGO = """
 ███████╗██╗     ██╗      █████╗ 
 ██╔════╝██║     ██║     ██╔══██╗
 █████╗  ██║     ██║     ███████║
 ██╔══╝  ██║     ██║     ██╔══██║
 ███████╗███████╗███████╗██║  ██║
 ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝
"""


def boot_sequence():
    """
    Display the animated boot sequence.
    
    Shows:
        Loading Ella...
        Loading Brain...
        Loading Memory...
        Loading Voice...
        Loading Vision...
        Ready.
    """
    console.clear()
    
    # ── Logo ───────────────────────────────────
    logo_text = Text(ELLA_LOGO, style="bold magenta")
    console.print(Align.center(logo_text))
    
    tagline = Text(f"  {TAGLINE}  ", style="dim italic")
    console.print(Align.center(tagline))
    
    version_text = Text(f"  v{VERSION}  ", style="dim")
    console.print(Align.center(version_text))
    console.print()
    
    # ── Loading Steps ──────────────────────────
    steps = [
        ("Loading Ella", "bold white", 0.3),
        ("Loading Brain", "bold yellow", 0.5),
        ("Loading Memory", "bold cyan", 0.3),
        ("Loading Voice", "bold green", 0.2),
        ("Loading Vision", "bold blue", 0.2),
    ]
    
    for step_name, style, delay in steps:
        # Show loading with dots animation
        console.print(f"  [{style}]●[/{style}] {step_name}...", end="")
        time.sleep(delay)
        console.print(f" [green]✓[/green]")
    
    console.print()
    
    # ── Check Ollama / Brain ───────────────────
    console.print("  [bold yellow]●[/bold yellow] Connecting to Brain...", end="")
    
    from brain.gemma import GemmaBrain
    brain = GemmaBrain()
    
    if brain.is_available():
        console.print(f" [green]✓[/green] [dim]({MODEL_NAME} connected)[/dim]")
        console.print("  [bold yellow]●[/bold yellow] Warming up GPU VRAM...", end="")
        brain.warmup()
        console.print(f" [green]✓[/green] [dim](Pinned to RTX 5060 GPU VRAM)[/dim]")
        brain_ready = True

    else:
        console.print(f" [red]✗[/red] [dim](Ollama not available)[/dim]")
        console.print()
        console.print(
            Panel(
                "[yellow]Ollama server nahi chal raha.[/yellow]\n\n"
                "Fix karne ke liye:\n"
                "  1. Ollama install karo: [cyan]https://ollama.com[/cyan]\n"
                f"  2. Model pull karo: [cyan]ollama pull {MODEL_NAME}[/cyan]\n"
                "  3. Server start karo: [cyan]ollama serve[/cyan]\n"
                "  4. Fir Ella chalao: [cyan]python main.py[/cyan]",
                title="[red]Brain Connection Failed[/red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        return None
    
    # ── Ready ──────────────────────────────────
    console.print()
    console.print(
        Panel(
            f"[bold green]Ready.[/bold green]\n"
            f"[dim]Model: {MODEL_NAME} │ Mode: Text │ User: {USER_NAME}[/dim]",
            border_style="green",
            padding=(0, 2),
        )
    )
    console.print()
    
    log.info(f"Boot complete — model: {MODEL_NAME}, user: {USER_NAME}")
    
    # Emit boot event
    event_bus.emit(Event(
        name="SessionStateChanged",
        source="main",
        data={"old_state": "boot", "new_state": "active"}
    ))
    
    return brain


def print_help():
    """Display help information."""
    console.print()
    console.print(
        Panel(
            "[bold]Commands:[/bold]\n"
            "  [cyan]Just type naturally[/cyan] — Chat with Ella\n"
            "  [cyan]exit / bye / quit[/cyan]  — Exit Ella\n"
            "  [cyan]stop ella[/cyan]          — Shutdown Ella\n"
            "\n"
            "[bold]Examples:[/bold]\n"
            '  "Good morning"\n'
            '  "Explain Python decorators"\n'
            '  "Motivate me"\n'
            '  "Translate this to Hindi"\n',
            title="[magenta]Ella Help[/magenta]",
            border_style="magenta",
            padding=(1, 2),
        )
    )


def main():
    """Main entry point for Project Ella."""
    
    # ── Handle CLI Arguments ───────────────────
    if "--help" in sys.argv or "-h" in sys.argv:
        print_help()
        return 0
    
    if "--test" in sys.argv:
        console.print("[yellow]Running self-check...[/yellow]")
        import setup
        return setup.main()
    
    if "--version" in sys.argv:
        console.print(f"Ella v{VERSION}")
        return 0
    
    # ── Boot Sequence ──────────────────────────
    try:
        brain = boot_sequence()
        
        if brain is None:
            return 1
        
        # ── Start Conversation ─────────────────
        from conversation import ConversationManager
        convo = ConversationManager(brain)
        convo.start()
        
        return 0
        
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Ella shut down.[/dim]")
        log.info("Ella shut down via Ctrl+C")
        return 0
        
    except Exception as e:
        log.error(f"Fatal error: {e}")
        console.print(f"\n  [red]Fatal Error:[/red] {e}")
        console.print("  [dim]Check logs in data/logs/ for details.[/dim]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
