# ──────────────────────────────────────────────
# Project Ella v1.0 — Desktop Automation
# Powered by pywinauto and PyAutoGUI (100% Local)
# ──────────────────────────────────────────────

import time
from logger import get_logger

log = get_logger("automation.desktop")


class DesktopManager:
    """
    Ella's desktop automation controller.
    Leverages pywinauto for native Windows accessibility control,
    with PyAutoGUI fallback for low-level mouse and keyboard actions.
    """

    def __init__(self):
        self.pywinauto_app = None
        self._load_libraries()

    def _load_libraries(self):
        """Import pywinauto and pyautogui."""
        try:
            import pywinauto
            import pyautogui
            self.pywinauto = pywinauto
            self.pyautogui = pyautogui
            # Fail-safe option to stop execution if mouse is moved to top-left corner
            pyautogui.FAILSAFE = True
            log.info("Desktop automation libraries loaded successfully.")
        except Exception as e:
            log.error(f"Error loading automation libraries: {e}")

    def get_visible_windows(self) -> list:
        """Get a list of all visible desktop window titles."""
        try:
            from pywinauto import Desktop
            windows = Desktop(backend="uia").windows()
            titles = [w.window_text() for w in windows if w.window_text().strip()]
            return titles
        except Exception as e:
            log.error(f"Failed to get window list: {e}")
            return []

    def focus_window(self, title_query: str) -> bool:
        """Find and bring a window to the foreground."""
        try:
            from pywinauto import Desktop
            windows = Desktop(backend="uia").windows()
            
            for w in windows:
                title = w.window_text()
                if title_query.lower() in title.lower():
                    log.info(f"Focusing window: '{title}'")
                    w.set_focus()
                    return True
            log.warning(f"No window found matching: '{title_query}'")
            return False
        except Exception as e:
            log.error(f"Failed to focus window '{title_query}': {e}")
            return False

    def click_native_element(self, window_title: str, control_name: str) -> bool:
        """
        Click a native GUI button or element inside a window using pywinauto UIA.
        """
        try:
            from pywinauto import Application
            # Connect to window
            app = Application(backend="uia").connect(title_re=f".*{window_title}.*")
            window = app.window(title_re=f".*{window_title}.*")
            
            # Find and click element
            element = window.child_window(title=control_name, control_type="Button")
            element.click()
            log.info(f"Clicked native element '{control_name}' inside '{window_title}'")
            return True
        except Exception as e:
            log.warning(f"Native pywinauto click failed ({e}). Falling back to visual click...")
            return False

    def click_at(self, x: int, y: int):
        """Simulate mouse click at absolute coordinates (x, y) via PyAutoGUI."""
        try:
            log.info(f"Clicking at screen coordinates ({x}, {y})")
            self.pyautogui.click(x, y)
        except Exception as e:
            log.error(f"PyAutoGUI click failed: {e}")

    def type_text(self, text: str, delay: float = 0.05):
        """Simulate typing text using PyAutoGUI."""
        try:
            log.info(f"Typing text: '{text[:30]}...'")
            self.pyautogui.write(text, interval=delay)
        except Exception as e:
            log.error(f"PyAutoGUI typing failed: {e}")

    def press_key_combination(self, keys: list):
        """
        Press hotkey combinations (e.g. ['ctrl', 'c'] or ['alt', 'f4']).
        """
        try:
            log.info(f"Pressing hotkeys: {keys}")
            self.pyautogui.hotkey(*keys)
        except Exception as e:
            log.error(f"Hotkey press failed: {e}")


if __name__ == "__main__":
    # Test Desktop manager
    import logging
    logging.basicConfig(level=logging.INFO)
    dm = DesktopManager()
    windows = dm.get_visible_windows()
    print("Visible windows:", windows[:5])
