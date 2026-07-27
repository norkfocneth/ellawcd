# ──────────────────────────────────────────────
# Project Ella v1.0 — Browser Automation
# Powered by Playwright (100% Offline-Friendly)
# ──────────────────────────────────────────────

import os
from logger import get_logger

log = get_logger("automation.browser")


class BrowserManager:
    """
    Ella's browser automation controller using Playwright.
    Allows navigated sessions, web scraping, and UI action simulation.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _lazy_init(self):
        """Initialize Playwright instance lazy-loaded."""
        if self.playwright is not None:
            return
            
        try:
            from playwright.sync_api import sync_playwright
            log.info("Starting Playwright browser...")
            self.playwright = sync_playwright().start()
            
            # Start chromium browser
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()
            log.info(f"Browser launched (headless={self.headless})")
        except Exception as e:
            log.error(f"Error launching browser: {e}")

    def navigate(self, url: str) -> str:
        """
        Navigate to a webpage and return its title.
        """
        self._lazy_init()
        if self.page is None:
            return "Browser not ready"
            
        try:
            log.info(f"Navigating to {url}")
            self.page.goto(url, wait_until="domcontentloaded")
            title = self.page.title()
            log.info(f"Loaded page: '{title}'")
            return title
        except Exception as e:
            log.error(f"Navigation failed: {e}")
            return f"Failed to load page: {e}"

    def get_content(self) -> str:
        """
        Extract visible text/markdown representation of the current page.
        """
        self._lazy_init()
        if self.page is None:
            return ""
            
        try:
            # Extract plain text content of the body
            content = self.page.locator("body").inner_text()
            return content
        except Exception as e:
            log.error(f"Failed to get page content: {e}")
            return ""

    def click(self, selector: str) -> bool:
        """
        Click a button or element matched by CSS selector or text description.
        """
        self._lazy_init()
        if self.page is None:
            return False
            
        try:
            log.info(f"Clicking element matching: {selector}")
            self.page.click(selector, timeout=5000)
            return True
        except Exception as e:
            log.error(f"Click action failed: {e}")
            return False

    def fill(self, selector: str, text: str) -> bool:
        """
        Type text into an input box matched by CSS selector.
        """
        self._lazy_init()
        if self.page is None:
            return False
            
        try:
            log.info(f"Filling text in {selector}")
            self.page.fill(selector, text, timeout=5000)
            return True
        except Exception as e:
            log.error(f"Fill action failed: {e}")
            return False

    def close(self):
        """Close browser resources cleanly."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
                
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
            log.info("Browser session closed.")
        except Exception as e:
            log.error(f"Error closing browser resources: {e}")


if __name__ == "__main__":
    # Test Browser manager
    import logging
    logging.basicConfig(level=logging.INFO)
    bm = BrowserManager(headless=True)
    title = bm.navigate("https://www.example.com")
    print("Page title:", title)
    content = bm.get_content()
    print("Content preview:", content[:100])
    bm.close()
