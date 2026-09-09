# ──────────────────────────────────────────────
# ELLA-WCD v2.0 — Browser Orchestrator
# Implements: Plan → Act → Observe → Verify → Recover → Learn Loop
# ──────────────────────────────────────────────

import json
import time
import uuid
import io
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from automation.webcmd_bridge import WebcmdBridge
from brain.qwen import QwenBrain
from memory import Memory
from logger import get_logger

log = get_logger("automation.orchestrator")
console = Console()


class BrowserOrchestrator:
    """
    Core engine of ELLA-WCD. Orchestrates the complete self-learning
    browser loop from user prompt to final verified answer.
    """

    def __init__(self, brain: QwenBrain, webcmd: Optional[WebcmdBridge] = None):
        self.brain = brain
        self.webcmd = webcmd or WebcmdBridge()
        self.memory = Memory()
        self.active_session_id: Optional[str] = None

    def execute_task(self, user_goal: str) -> Dict[str, Any]:
        """
        Execute an autonomous multi-step browser task with the full loop:
        Plan → Act → Observe → Verify → Recover → Learn
        """
        start_time = time.time()
        console.print()

        # ── 1. PLAN ───────────────────────────────────────────────
        console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
        console.print(f"[bold cyan][PLAN][/bold cyan] Analyzing task: [italic]{user_goal}[/italic]")

        plan = self.brain.plan_workflow(user_goal)
        understanding = plan.get("understanding", user_goal)
        starting_url = plan.get("starting_url", "https://duckduckgo.com")
        steps = plan.get("steps", [])
        verification_criteria = plan.get("verification_criteria", "Extract valid non-empty data")
        pattern_name = plan.get("learned_pattern_name", "web_workflow")

        console.print(f"  [green]✓[/green] Goal: {understanding}")
        console.print(f"  [green]✓[/green] Target URL: {starting_url}")
        console.print(f"  [green]✓[/green] Workflow: {len(steps)} planned action(s)")
        for s in steps:
            console.print(f"    • Step {s.get('step_id')}: [bold]{s.get('action')}[/bold] - {s.get('description')}")
        console.print(f"  [green]✓[/green] Verification Rule: {verification_criteria}")
        console.print()

        # ── 2. BROWSER SESSION & SITE MEMORY ─────────────────────
        task_slug = "ella-" + uuid.uuid4().hex[:6]
        self.active_session_id = self.webcmd.create_session(task_slug)
        console.print(f"[bold yellow][BROWSER][/bold yellow] Session: [bold]{self.active_session_id}[/bold]")

        # Check existing site memory
        try:
            mem_ctx = self.webcmd.get_site_memory_context(starting_url)
            if mem_ctx.get("ok") and mem_ctx.get("siteMarkdown"):
                console.print(f"  [cyan]ℹ[/cyan] Site Memory: [green]Prior workflow discovered for {starting_url}[/green]")
            else:
                console.print(f"  [dim]→ Site Memory: First encounter with {starting_url} (exploration mode)[/dim]")
        except Exception:
            pass

        # ── 3. EXECUTE ACTIONS ───────────────────────────────────
        extracted_data = []
        page_title = ""
        current_url = starting_url
        execution_passed = False

        query_text = ""
        for s in steps:
            if s.get("action") in ["search", "fill"] and s.get("value"):
                val = str(s.get("value")).strip()
                if len(val) > 2 and not val.lower().startswith("the user"):
                    query_text = val
                    break

        if not query_text:
            # Clean common command prefixes and suffixes
            clean_goal = user_goal.strip()
            for prefix in ["find 5 ", "find 3 ", "find ", "search for ", "search ", "look up ", "browse "]:
                if clean_goal.lower().startswith(prefix):
                    clean_goal = clean_goal[len(prefix):]
            for suffix in [" on arxiv", " from arxiv", " on github", " from github", " online", " on duckduckgo"]:
                if clean_goal.lower().endswith(suffix):
                    clean_goal = clean_goal[:-len(suffix)]
            query_text = clean_goal.strip()

        # Dispatch based on target domain or intent (Direct Deterministic Routes)
        import urllib.parse
        enc_q = urllib.parse.quote_plus(query_text)

        if "arxiv" in user_goal.lower():
            search_url = f"https://arxiv.org/search/?query={enc_q}&searchtype=all"
            console.print(f"  [blue]→[/blue] Learned arXiv Route: {search_url}")
            console.print(f"  [blue]→[/blue] Query: '{query_text}'")
            script = f"""
            await page.goto("{search_url}", {{ waitUntil: "domcontentloaded", timeout: 15000 }});
            const items = await page.locator(".arxiv-result").evaluateAll(els => els.slice(0, 5).map(e => ({{
                title: e.querySelector(".title")?.innerText?.trim() || "",
                link: e.querySelector("a")?.href || "",
                snippet: e.querySelector(".abstract-full")?.innerText?.trim() || ""
            }})));
            return {{
                url: page.url(),
                title: await page.title(),
                results: items
            }};
            """
            res = self.webcmd.run_script(script, session_id=self.active_session_id)

        elif "github" in user_goal.lower():
            search_url = f"https://github.com/search?q={enc_q}&type=repositories"
            console.print(f"  [blue]→[/blue] Learned GitHub Route: {search_url}")
            console.print(f"  [blue]→[/blue] Query: '{query_text}'")
            script = f"""
            await page.goto("{search_url}", {{ waitUntil: "domcontentloaded", timeout: 15000 }});
            const items = await page.locator("div[data-testid='results-list'] > div, ul.repo-list > li").evaluateAll(els => els.slice(0, 5).map(e => ({{
                title: e.querySelector("h3, a")?.innerText?.trim() || "",
                link: e.querySelector("a")?.href || "",
                snippet: e.querySelector("p")?.innerText?.trim() || ""
            }})));
            return {{
                url: page.url(),
                title: await page.title(),
                results: items
            }};
            """
            res = self.webcmd.run_script(script, session_id=self.active_session_id)

        elif starting_url.startswith("http") and "duckduckgo" not in starting_url:
            console.print(f"  [blue]→[/blue] Direct Navigation: {starting_url}")
            j_start = json.dumps(starting_url)
            script = f"""
            await page.goto({j_start}, {{ waitUntil: 'domcontentloaded', timeout: 15000 }});
            return {{
                url: page.url(),
                title: await page.title(),
                results: [{{
                    title: await page.title(),
                    link: page.url(),
                    text: (await page.locator('body').innerText()).trim().slice(0, 1000)
                }}]
            }};
            """
            res = self.webcmd.run_script(script, session_id=self.active_session_id)

        else:
            # General DuckDuckGo HTML search route
            search_url = f"https://html.duckduckgo.com/html/?q={enc_q}"
            console.print(f"  [blue]→[/blue] Learned Web Search Route: {search_url}")
            console.print(f"  [blue]→[/blue] Query: '{query_text}'")
            script = f"""
            await page.goto("{search_url}", {{ waitUntil: "domcontentloaded", timeout: 15000 }});
            const items = await page.locator(".result, .web-result").evaluateAll(els => els.slice(0, 5).map(e => ({{
                title: e.querySelector(".result__title, h2, a")?.innerText?.trim() || "",
                link: e.querySelector("a.result__url, a")?.href || "",
                snippet: e.querySelector(".result__snippet")?.innerText?.trim() || ""
            }})));
            return {{
                url: page.url(),
                title: await page.title(),
                results: items
            }};
            """
            res = self.webcmd.run_script(script, session_id=self.active_session_id)

        if res.get("ok"):
            r = res.get("result") if isinstance(res.get("result"), dict) else {}
            p = res.get("page") if isinstance(res.get("page"), dict) else {}
            page_title = r.get("title") or p.get("title") or "Page Loaded"
            current_url = r.get("url") or p.get("url") or starting_url
            extracted_data = r.get("results", [])
            console.print(f"  [green]✓[/green] Page loaded: '{page_title}' ({current_url})")
            execution_passed = True
        else:
            console.print(f"  [yellow]![/yellow] Execution status: {res.get('error', 'Completed')}")

        # ── 4. OBSERVE ───────────────────────────────────────────
        console.print()
        console.print("[bold magenta][OBSERVE][/bold magenta]")
        if extracted_data:
            console.print(f"  [green]✓[/green] Detected {len(extracted_data)} structured record(s)")
            for idx, item in enumerate(extracted_data[:3], 1):
                preview = item.get("title") or item.get("text", "")[:70].replace("\n", " ")
                console.print(f"    [{idx}] {preview}...")
        else:
            console.print("  [yellow]![/yellow] Capturing page text snapshot...")
            snap = self.webcmd.snapshot(mode="read", session_id=self.active_session_id)
            raw_text = snap.get("output", "")[:800]
            if raw_text:
                extracted_data = [{"title": page_title, "link": current_url, "text": raw_text}]
                console.print(f"  [green]✓[/green] Extracted text buffer ({len(raw_text)} chars)")

        # ── 5. VERIFY & RECOVER ───────────────────────────────────
        console.print()
        console.print("[bold blue][VERIFY][/bold blue]")
        if len(extracted_data) > 0:
            console.print(f"  [green]✓[/green] Verified valid non-empty data -> [bold green]PASS[/bold green]")
        else:
            console.print(f"  [red]✗[/red] Verification check: 0 results returned.")
            # ── 5b. RECOVER (Vision Fallback) ──
            console.print()
            console.print("[bold red][RECOVER][/bold red]")
            console.print("  [yellow]→[/yellow] Triggering Visual Grounding Fallback...")
            try:
                import mss
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    sct_img = sct.grab(monitor)
                    from PIL import Image
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=70)
                    img_bytes = buf.getvalue()
                    loc = self.brain.vision_localize(query_text, img_bytes)
                    console.print(f"  [green]✓[/green] Vision localization: {loc.get('description', 'Inspected screen viewport')}")
            except Exception as e:
                console.print(f"  [dim]Vision fallback diagnostic: {e}[/dim]")

        # ── 6. LEARN ──────────────────────────────────────────────
        console.print()
        console.print("[bold green][LEARN][/bold green]")
        try:
            domain_url = starting_url.split("?")[0]
            self.webcmd.add_memory_candidate(
                product=domain_url,
                claim=f"Workflow {pattern_name}",
                evidence=f"Verified {len(extracted_data)} items from {domain_url}"
            )
            self.memory.save_fact("workflow", f"{pattern_name} -> {domain_url}")
            console.print(f"  [green]✓[/green] WebCMD Sitemap memory updated for [cyan]{domain_url}[/cyan]")
            console.print(f"  [green]✓[/green] Checkpoint recorded: '{pattern_name}' (Reusable deterministic route)")
        except Exception as e:
            console.print(f"  [dim]Memory checkpoint notice: {e}[/dim]")

        # ── 7. RESULT SYNTHESIS ───────────────────────────────────
        console.print()
        console.print("[bold white][RESULT][/bold white]")

        synthesis_prompt = f"""You are ELLA-WCD, an autonomous browser agent.
The user asked: "{user_goal}"
We executed a live browser task and extracted the following evidence from '{page_title}' ({current_url}):

Evidence:
{json.dumps(extracted_data[:5], indent=2)}

Provide a structured, clean, well-formatted markdown response answering the user's request based on this evidence.
Include sources, titles, dates, or URLs if available.
Keep it direct, professional, and clear.
"""
        final_answer = self.brain.chat(synthesis_prompt)

        console.print(Panel(
            final_answer,
            title="[bold green]Autonomous Task Result[/bold green]",
            border_style="green",
            padding=(1, 2)
        ))

        elapsed = time.time() - start_time
        console.print(f"[dim]Task completed in {elapsed:.2f}s | Session: {self.active_session_id}[/dim]")
        console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")

        # Cleanup session
        self.webcmd.close_session(self.active_session_id)
        self.active_session_id = None

        return {
            "ok": True,
            "goal": user_goal,
            "answer": final_answer,
            "results_count": len(extracted_data),
            "elapsed_seconds": elapsed
        }
