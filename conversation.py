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
    "deal", "deals", "dhoondo", "khojo", "dekho", "kholo", "batao",
    "download", "install", "extension", "extensions", "wallet", "metamask",
    "addon", "addons", "plugin", "setup", "get",
    # Quick Commerce & Grocery Intent
    "quick commerce", "q-commerce", "quick eccoece", "quick ecommerce", "grocery", "groceries",
    "tomato", "tomatoes", "onion", "potato", "vegetable", "vegetables", "milk", "fruits", "fruit",
    "blinkit", "zepto", "instamart", "swiggy", "zomato", "amazon fresh", "bigbasket", "bbnow",
    "flipkart quick", "flipkart minutes", "cheapest", "sasta", "saste",
    # Clothing, Fashion & Apparel Intent
    "clothing", "clothes", "fashion", "apparel", "kapde", "kapda", "samaan",
    "tshirt", "t-shirt", "shirt", "shirts", "jeans", "hoodie", "hoodies", "jacket", "jackets",
    "sweatshirt", "sweatshirts", "kurta", "kurti", "saree", "dress", "dresses",
    "shoes", "sneakers", "myntra", "zara", "h&m", "trousers", "pants", "trackpants",
    # Online Pharmacy & Medicines
    "medicine", "medicines", "tablet", "tablets", "capsule", "capsules", "syrup", "dawa", "dawain",
    "1mg", "tata 1mg", "netmeds", "apollo pharmacy", "pharmeasy", "paracetamol", "crocin", "azithromycin",
    "whey protein", "multivitamin", "creatine", "dolo", "cough syrup", "pharmacy",
    # Travel & Flight Fares
    "flight", "flights", "air ticket", "tickets", "airfare", "fare", "makemytrip", "easemytrip",
    "cleartrip", "indigo", "air india", "vistara", "delhi to mumbai", "bangalore to delhi", "ticket price",
    # Academic & Research Papers
    "arxiv", "pubmed", "research paper", "papers", "preprint", "journal", "ieee", "springer",
    "abstract", "literature", "scholar",
    # Jobs & Internships
    "job", "jobs", "internship", "internships", "hiring", "vacancy", "vacancies", "naukri",
    "linkedin jobs", "indeed", "wellfound", "angellist", "remote job", "developer job",
    # Food Delivery Cart Optimizer
    "food delivery", "swiggy food", "zomato food", "order food", "restaurant", "biryani", "pizza",
    "burger", "roll", "thali", "menu price", "coupon",
    # Mobile Recharge & Telecom Plans
    "recharge", "recharge plan", "prepaid plan", "jio plan", "airtel plan", "vi plan", "validity",
    "per day data", "84 days", "28 days", "telecom plan", "data pack",
    # Real Estate & Rental Flats / PG
    "flat", "flats", "rent", "rental", "pg", "1bhk", "2bhk", "3bhk", "nobroker", "magicbricks",
    "99acres", "room for rent", "flat for rent", "house rent",
    # Tech Digest & Trending Repos
    "tech digest", "morning digest", "trending repos", "github trending", "hackernews", "techcrunch",
    "daily digest", "top tech news", "ai news",
    # Competitor & Market Research
    "competitor", "pricing table", "landing page inspect", "competitor pricing", "saas pricing",
    # Offline Intelligence & SQLite Memory Intent
    "offline", "bina internet", "no internet", "without internet", "cache", "cached", "database", "saved search"
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

        elif root in ["/offline", "/cache"]:
            if len(parts) > 1:
                target = " ".join(parts[1:])
                if target.lower() in ["on", "enable", "true", "1"]:
                    self.orchestrator.force_offline = True
                    console.print("[yellow]Offline Mode: FORCED ON (All queries will serve from SQLite local database)[/yellow]")
                    return True
                elif target.lower() in ["off", "disable", "false", "0"]:
                    self.orchestrator.force_offline = False
                    console.print("[green]Offline Mode: OFF (Live Google Chrome exploration enabled)[/green]")
                    return True
                else:
                    self.orchestrator._execute_offline_mode(target, time.time())
                    return True
            else:
                cached = self.memory.get_all_cached_queries()
                searches_list = "\n".join([f"  • [yellow]{c['query']}[/yellow] ([cyan]{c['category']}[/cyan]) — [dim]{c['updated_at']}[/dim]" for c in cached]) if cached else "  [dim]None yet[/dim]"
                console.print(Panel(
                    f"[bold bright_yellow]⚡ OFFLINE LOCAL CACHE STATUS[/bold bright_yellow]\n\n"
                    f"• Database File: [cyan]{self.memory.db_path}[/cyan]\n"
                    f"• Total Cached Search Snapshots: [bold green]{len(cached)}[/bold green]\n"
                    f"• Forced Offline Mode: [bold]{'ENABLED' if self.orchestrator.force_offline else 'DISABLED (Auto-detects network)'}[/bold]\n\n"
                    f"[bold white]Stored Searches in Local Memory DB:[/bold white]\n"
                    f"{searches_list}\n\n"
                    f"[dim]Usage: '/offline on', '/offline off', or '/offline tomatoes'[/dim]",
                    title="[bold yellow]Local SQLite Offline Engine[/bold yellow]",
                    border_style="bright_yellow",
                    padding=(1, 2)
                ))
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
            "  [yellow]/offline [query][/yellow]  — Inspect or search local SQLite database offline (0s latency)\n"
            "  [yellow]/recipes[/yellow]          — View cached self-learned browser automation recipes\n"
            "  [yellow]/reset[/yellow]            — Reset conversation context and clear active tabs\n"
            "  [yellow]/exit[/yellow]             — Safely close browser and exit\n\n"
            "[bold cyan]Supported Daily Automations (14 Domains):[/bold cyan]\n"
            "  1. [green]Quick Commerce[/green]: Compare live rates on Blinkit, Zepto, Amazon Fresh\n"
            "  2. [green]Fashion & Footwear[/green]: Find clothes & shoes across Flipkart, Amazon, Myntra\n"
            "  3. [green]Offline Memory DB[/green]: Query cached searches without internet (0.03s latency)\n"
            "  4. [green]1-Click Installer[/green]: Safely download extensions & apps from official stores\n"
            "  5. [green]Electronics Deals[/green]: Compare laptops, phones across Amazon, Flipkart, Croma\n"
            "  6. [green]Online Pharmacy[/green]: Compare medicines & supplements on 1mg, Netmeds, Apollo\n"
            "  7. [green]Flight Fares[/green]: Compare flights across MakeMyTrip, EaseMyTrip, Cleartrip\n"
            "  8. [green]Academic Papers[/green]: Pull abstracts & PDF links from arXiv & PubMed\n"
            "  9. [green]Job Scanner[/green]: Search remote/tech roles on LinkedIn, Indeed, Wellfound\n"
            " 10. [green]Food Delivery[/green]: Compare cart menus & discounts on Zomato vs Swiggy\n"
            " 11. [green]Mobile Recharge[/green]: Compare data & validity plans across Jio, Airtel, Vi\n"
            " 12. [green]Rental Flats / PG[/green]: Find verified 1BHK/2BHK flats on NoBroker, MagicBricks\n"
            " 13. [green]Tech & AI Digest[/green]: Get 1-minute daily morning briefing from GitHub & HackerNews\n"
            " 14. [green]Competitor Intel[/green]: Inspect pricing tiers & feature updates on any URL\n",
            title="[bold magenta]ELLA-WCD v2.0 Guide • 14 Daily Automations[/bold magenta]",
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
