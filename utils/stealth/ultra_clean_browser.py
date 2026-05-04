# ultra_clean_browser.py

import os
import shutil
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from .find_cookie import get_browser_launch_config

class UltraCleanBrowser:
    def __init__(self, user_data_dir="user_data", headless=False):
        self.headless = headless
        self.config = get_browser_launch_config()
        self.user_data_dir = self.config["user_data_dir"]
        self.playwright = None
        self.context = None
        print("self.config[\"user_data_dir\"]:", self.config["user_data_dir"])

    # ---------- CLEAN ----------

    def _kill_processes(self):
        for proc in ["node.exe", "chrome.exe"]:
            try:
                subprocess.run(
                    ["taskkill", "/f", "/im", proc],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except:
                pass

    def _clean_env(self):
        os.environ.pop("PWDEBUG", None)
        os.environ.pop("DEBUG", None)
        os.environ["PWDEBUG"] = "0"

    def _clean_profile(self, force=False):
        if force and os.path.exists(self.user_data_dir):
            shutil.rmtree(self.user_data_dir, ignore_errors=True)

    # ---------- START ----------

    def start(self, force_clean=False):
        self._kill_processes()
        self._clean_env()
        self._clean_profile(force_clean)

        # Wait for processes to fully terminate
        time.sleep(2)

        self.playwright = sync_playwright().start()

        # Retry logic instead of fallback
        max_retries = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                self.context = self.playwright.chromium.launch_persistent_context(
                    user_data_dir=self.config["user_data_dir"],
                    channel=self.config["channel"],
                    headless=self.headless,
                    args=self.config["args"]
                )
                print(f"Browser launched successfully on attempt {attempt + 1}")
                return self
            except Exception as e:
                last_error = e
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry

        # If all retries failed, raise the error
        raise Exception(f"Failed to launch browser after {max_retries} attempts: {last_error}")

    # ---------- PAGE ----------

    def new_page(self):
        page = self.context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            delete window.navigator.__proto__.webdriver;
            """)

        return page

    # ---------- HEALTH ----------

    def is_alive(self) -> bool:
        try:
            return self.context is not None and len(self.context.pages) >= 0
        except Exception:
            return False

    # ---------- CLOSE ----------

    def close(self):
        try:
            if self.context:
                self.context.close()
        except Exception as e:
            print(f"Error closing context: {e}")
        finally:
            try:
                if self.playwright:
                    self.playwright.stop()
            except Exception as e:
                print(f"Error stopping playwright: {e}")
