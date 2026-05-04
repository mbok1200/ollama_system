from playwright.sync_api import sync_playwright, BrowserContext, Page
from typing import Optional, Dict
import threading
import os

os.environ.pop("PWDEBUG", None)
os.environ["PWDEBUG"] = "0"
os.environ["DEBUG"] = ""

class StealthBrowser:
    def __init__(self, proxy: Optional[Dict] = None, headless: bool = False):
        self.proxy = proxy
        self.headless = headless

        self.playwright = None
        self.context: Optional[BrowserContext] = None

        self._lock = threading.Lock()
        self._started = False

        # user data dir (persistent session)
        self.user_data_dir = os.path.abspath("user_data")

    # ---------- START ----------

    def start(self):
        with self._lock:
            if self._started:
                return self

            # вимикаємо debug якщо був
            os.environ["PWDEBUG"] = "0"

            self.playwright = sync_playwright().start()

            launch_args = {
                "headless": self.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled"
                ]
            }

            if self.proxy:
                launch_args["proxy"] = self.proxy

            # 🔥 ВАЖЛИВО: persistent + chrome
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                channel="chrome",
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled"
                ]
            )

            self._started = True
            return self

    # ---------- HEALTH ----------

    def is_alive(self) -> bool:
        try:
            return self.context is not None and len(self.context.pages) >= 0
        except Exception:
            return False

    # ---------- PAGE ----------

    def new_page(self) -> Page:
        if not self._started:
            raise RuntimeError("Browser not started")

        page = self.context.new_page()
        self._apply_stealth(page)

        return page

    # ---------- STEALTH ----------

    def _apply_stealth(self, page: Page):
        page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        window.chrome = { runtime: {} };

        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });

        Object.defineProperty(navigator, 'plugins', {
            get: () => [1,2,3,4,5]
        });
        """)

    # ---------- CLOSE ----------

    def close(self):
        with self._lock:
            try:
                if self.context:
                    self.context.close()
            except Exception:
                pass
            finally:
                try:
                    if self.playwright:
                        self.playwright.stop()
                except Exception:
                    pass

            self.context = None
            self.playwright = None
            self._started = False