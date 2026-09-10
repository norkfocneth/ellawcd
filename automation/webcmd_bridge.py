# ──────────────────────────────────────────────
# ELLA-WCD v2.0 — WebCMD Bridge
# High-speed deterministic browser automation bridge
# Powered by @agentrhq/webcmd
# ──────────────────────────────────────────────

import os
import sys
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from logger import get_logger

log = get_logger("automation.webcmd")

# Ensure Brave Browser executable is explicitly configured for Cloak/WebCMD
BRAVE_DEFAULT_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
if os.path.exists(BRAVE_DEFAULT_PATH):
    os.environ["CLOAKBROWSER_BINARY_PATH"] = BRAVE_DEFAULT_PATH
    os.environ["WEBCMD_BROWSER_EXECUTABLE_PATH"] = BRAVE_DEFAULT_PATH


class WebcmdBridge:
    """
    Python bridge to @agentrhq/webcmd CLI.
    Manages browser sessions, Playwright script execution, snapshots,
    and site memory learning.
    """

    def __init__(self, profile: str = "default", headless: bool = True):
        self.profile = profile
        self.headless = headless
        self.current_session: Optional[str] = None
        self.webcmd_bin = self._find_webcmd()
        self._ensure_profile()

    def _find_webcmd(self) -> List[str]:
        """Locate the webcmd executable or fall back to npx."""
        # 1. Check direct binary in PATH
        cmd_path = shutil.which("webcmd.cmd") or shutil.which("webcmd")
        if cmd_path:
            log.info(f"Found webcmd binary: {cmd_path}")
            return [cmd_path]

        # 2. Check npm roaming directory
        npm_roaming = Path(os.environ.get("APPDATA", "")) / "npm" / "webcmd.cmd"
        if npm_roaming.exists():
            log.info(f"Found webcmd in APPDATA/npm: {npm_roaming}")
            return [str(npm_roaming)]

        # 3. Fallback to npx
        log.warning("webcmd binary not found on PATH, falling back to 'npx -y @agentrhq/webcmd'")
        return ["npx", "-y", "@agentrhq/webcmd"]

    def _run_cmd(self, args: List[str], input_str: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Execute a webcmd command and return parsed JSON or status dict."""
        cmd = self.webcmd_bin + args
        try:
            log.debug(f"Running WebCMD command: {' '.join(cmd)}")
            res = subprocess.run(
                cmd,
                input=input_str,
                text=True,
                capture_output=True,
                timeout=timeout,
                shell=(sys.platform == "win32")
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()

            # Try parsing JSON output
            if stdout:
                # Find first JSON object if mixed with logs
                json_start = stdout.find("{")
                if json_start != -1:
                    try:
                        return json.loads(stdout[json_start:])
                    except json.JSONDecodeError:
                        pass

            if res.returncode != 0:
                if "Candidate capture requires a valid product manifest" in (stderr or stdout):
                    log.debug(f"WebCMD candidate capture note: {stderr or stdout}")
                else:
                    log.debug(f"WebCMD command info (code {res.returncode}): {stderr or stdout}")
                return {"ok": False, "error": stderr or stdout, "code": res.returncode}

            return {"ok": True, "output": stdout}

        except subprocess.TimeoutExpired:
            log.error(f"WebCMD command timed out after {timeout}s")
            return {"ok": False, "error": f"Timeout after {timeout}s"}
        except Exception as e:
            log.error(f"WebCMD execution error: {e}")
            return {"ok": False, "error": str(e)}

    def check_doctor(self) -> Dict[str, Any]:
        """Run webcmd doctor check."""
        return self._run_cmd(["doctor"], timeout=20)

    def _ensure_profile(self) -> None:
        """Ensure the target profile exists."""
        res = self._run_cmd(["profile", "create", self.profile])
        if res.get("ok") or "already exists" in str(res.get("output", "")).lower():
            log.info(f"WebCMD profile '{self.profile}' ready.")
        else:
            log.debug(f"Profile check: {res}")

    def create_session(self, name: str = "ella-task") -> Optional[str]:
        """Create a new explicit browser session within the profile."""
        res = self._run_cmd(["--profile", self.profile, "session", "create", name, "-f", "json"], timeout=20)
        if isinstance(res, dict) and res.get("id"):
            self.current_session = res["id"]
            log.info(f"WebCMD session created: {self.current_session}")
            return self.current_session
        
        # If error was profile not found, recreate profile and retry once
        if isinstance(res, dict) and res.get("error", {}).get("code") == "PROFILE_NOT_FOUND":
            self._ensure_profile()
            res = self._run_cmd(["--profile", self.profile, "session", "create", name, "-f", "json"], timeout=20)
            if isinstance(res, dict) and res.get("id"):
                self.current_session = res["id"]
                return self.current_session

        log.error(f"Failed to create session: {res}")
        return None

    def close_session(self, session_id: Optional[str] = None) -> bool:
        """Close an explicit browser session."""
        sid = session_id or self.current_session
        if not sid:
            return True
        res = self._run_cmd(["session", "close", sid], timeout=15)
        if sid == self.current_session:
            self.current_session = None
        log.info(f"WebCMD session {sid} closed.")
        return res.get("ok", True)

    def run_script(self, script: str, session_id: Optional[str] = None, timeout: int = 35) -> Dict[str, Any]:
        """
        Execute a Playwright-style JavaScript script in the active browser session.
        Script runs via stdin and receives `page` in scope.
        """
        sid = session_id or self.current_session
        if not sid:
            sid = self.create_session("ella-auto")
            if not sid:
                return {"ok": False, "error": "Unable to initialize browser session"}

        args = ["--profile", self.profile, "--session", sid, "browser", "run", "--stdin", "-f", "json"]
        res = self._run_cmd(args, input_str=script, timeout=timeout)
        return res

    def navigate(self, url: str, session_id: Optional[str] = None, wait_for: str = "domcontentloaded") -> Dict[str, Any]:
        """Navigate to a URL and return page title and URL."""
        script = f"""
        await page.goto('{url}', {{ waitUntil: '{wait_for}', timeout: 20000 }});
        return {{
            url: page.url(),
            title: await page.title()
        }};
        """
        return self.run_script(script, session_id=session_id)

    def snapshot(self, mode: str = "read", session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Take a snapshot of the current page.
        Modes:
          - 'act': List interactive clickable/fillable controls
          - 'read': Extract clean readable text/markdown
          - 'tree': DOM hierarchy
        """
        sid = session_id or self.current_session
        if not sid:
            return {"ok": False, "error": "No active session"}

        args = ["--profile", self.profile, "--session", sid, "browser", "snapshot", "--snapshot-mode", mode, "-f", "json"]
        return self._run_cmd(args, timeout=20)

    def search_and_extract(
        self,
        url: str,
        search_input_selector: str,
        query: str,
        submit_selector: Optional[str] = None,
        result_items_selector: Optional[str] = None,
        limit: int = 5,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        High-level batched action: navigate, search, wait, and extract results in one shot!
        Minimizes agent round-trips. Uses json.dumps for 100% safe JavaScript string interpolation.
        """
        j_url = json.dumps(url)
        j_sel = json.dumps(search_input_selector)
        j_query = json.dumps(query)
        
        if submit_selector:
            j_sub = json.dumps(submit_selector)
            submit_code = f"try {{ await page.locator({j_sub}).first().click(); }} catch(e) {{ await page.locator({j_sel}).first().press('Enter'); }}"
        else:
            submit_code = f"await page.locator({j_sel}).first().press('Enter');"

        extraction_code = ""
        if result_items_selector:
            j_items = json.dumps(result_items_selector)
            extraction_code = f"""
            let items = [];
            try {{
                items = await page.locator({j_items}).evaluateAll((elements, max) => {{
                    return elements.slice(0, max).map(el => ({{
                        text: el.innerText ? el.innerText.trim() : '',
                        title: el.querySelector('h1, h2, h3, h4, a')?.innerText?.trim() || '',
                        link: el.querySelector('a')?.href || '',
                        snippet: el.querySelector('p, .abstract, .snippet')?.innerText?.trim() || ''
                    }}));
                }}, {limit});
            }} catch(e) {{
                items = [];
            }}
            """
        else:
            extraction_code = "const items = [];"

        script = f"""
        await page.goto({j_url}, {{ waitUntil: 'domcontentloaded', timeout: 15000 }});
        await page.locator({j_sel}).first().fill({j_query});
        {submit_code}
        try {{
            await page.waitForTimeout(2500);
        }} catch(e) {{
            // Continue if timeout error
        }}
        {extraction_code}
        return {{
            url: page.url(),
            title: await page.title(),
            results: items
        }};
        """
        return self.run_script(script, session_id=session_id)

    # ── Site Memory Loop ───────────────────────────

    def get_site_memory_context(self, url: str) -> Dict[str, Any]:
        """Fetch learned sitemap context for a given URL."""
        args = ["site", "memory", "context", url, "--task-id", f"ella-{int(time.time())}", "-f", "json"]
        return self._run_cmd(args, timeout=15)

    def add_memory_candidate(
        self,
        product: str,
        claim: str,
        evidence: str,
        kind: str = "better_path",
        consequence: str = "Faster autonomous lookup"
    ) -> Dict[str, Any]:
        """Record an observed workflow pattern into WebCMD candidate memory."""
        # Clean product hostname (e.g. 'arxiv.org' or 'example.com')
        host = product.replace("https://", "").replace("http://", "").split("/")[0]
        args = [
            "site", "memory", "candidate", "add", host,
            "--kind", kind,
            "--claim", claim,
            "--evidence", evidence,
            "--consequence", consequence,
            "-f", "json"
        ]
        return self._run_cmd(args, timeout=15)
