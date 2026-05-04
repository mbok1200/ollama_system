import asyncio
import sqlite3
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

# Persistent profile — зберігається між запусками, не видаляється
_PERSISTENT_PROFILE_DIR = Path(__file__).resolve().parent.parent / "browser_profiles" / "linkedin_session"

from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from utils.stealth.find_cookie import get_browser_launch_config

_REMOVE_DEFAULT_ARGS = [
    "--disable-background-networking",
    "--disable-extensions",
    "--disable-sync",
    "--disable-default-apps",
    "--enable-automation",   # ← головний сигнал бота, Google детектить одразу
    "--disable-infobars",
]

_HIDE_WEBDRIVER_SCRIPT = """
(() => {
    // webdriver
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    delete window.navigator.__proto__.webdriver;

    // chrome runtime (присутній у реального Chrome)
    if (!window.chrome) {
        window.chrome = { runtime: {} };
    }

    // permissions — боти повертають 'denied' на notifications
    const origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) => {
        if (params.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission });
        }
        return origQuery(params);
    };

    // plugins — реальний Chrome має плагіни, Playwright — 0
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });

    // languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['uk-UA', 'uk', 'en-US', 'en'],
    });
})();
"""

# SQLite files Chrome locks while running — copied via sqlite3.backup()
_SQLITE_FILES = {"Cookies", "Login Data", "History", "Bookmarks", "Favicons", "Web Data"}


def _copy_profile(src: Path, dst: Path) -> None:
    """
    Copy Chrome profile dir to dst.
    SQLite files are copied via sqlite3.backup() (readable even while Chrome holds a lock).
    Other files use shutil.copy2; locked files are silently skipped.
    """
    dst.mkdir(parents=True, exist_ok=True)

    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel

        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)

        if item.name in _SQLITE_FILES or item.suffix in (".db", ".sqlite"):
            try:
                src_conn = sqlite3.connect(f"file:{item}?mode=ro&immutable=1", uri=True)
                dst_conn = sqlite3.connect(str(target))
                src_conn.backup(dst_conn)
                src_conn.close()
                dst_conn.close()
            except Exception:
                pass
        else:
            try:
                shutil.copy2(str(item), str(target))
            except Exception:
                pass


def _kill_chrome():
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "chrome.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


class BrowserSession:
    def __init__(self, session_id: str, pw: Playwright, context: BrowserContext, page: Page, profile_dir: str):
        self.session_id = session_id
        self.pw = pw
        self.context = context
        self.page = page
        self.profile_dir = profile_dir  # persistent dir — не видаляємо

    async def cleanup(self):
        try:
            await self.context.close()
        except Exception:
            pass
        try:
            await self.pw.stop()
        except Exception:
            pass


class BrowserSessionManager:
    """Менеджер браузерних сесій для LangGraph (async)."""

    def __init__(self):
        self.sessions: Dict[str, BrowserSession] = {}

    async def create_new_session(self) -> str:
        """
        Використовує persistent profile dir між запусками — cookies зберігаються.
        Перший запуск: копіює з реального Chrome.
        Наступні запуски: використовує збережений профіль одразу.
        """
        config = get_browser_launch_config()
        user_data_dir = config["user_data_dir"]
        channel = config.get("channel")
        args = [a for a in config.get("args", []) if "--profile-directory" not in a]

        profile_dir = _PERSISTENT_PROFILE_DIR
        dst_profile = profile_dir / "Default"

        _kill_chrome()
        await asyncio.sleep(1)

        if not dst_profile.exists():
            # Перший запуск — копіюємо з реального Chrome
            src_profile = Path(user_data_dir) / "Default"
            if src_profile.exists():
                print(f"[create_new_session] First run — copying profile from Chrome...")
                await asyncio.get_event_loop().run_in_executor(None, _copy_profile, src_profile, dst_profile)
                print(f"[create_new_session] Profile saved → {dst_profile}")
            else:
                dst_profile.mkdir(parents=True, exist_ok=True)
        else:
            print(f"[create_new_session] Using saved profile: {profile_dir}")

        print(f"[create_new_session] Launching (channel={channel})...")
        pw = await async_playwright().start()

        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            channel=channel,
            args=args,
            ignore_default_args=_REMOVE_DEFAULT_ARGS,
        )

        page = context.pages[0] if context.pages else await context.new_page()
        await page.add_init_script(_HIDE_WEBDRIVER_SCRIPT)

        session_id = str(uuid.uuid4())
        self.sessions[session_id] = BrowserSession(session_id, pw, context, page, str(profile_dir))

        print(f"[create_new_session] Session created: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        return self.sessions.get(session_id)

    def get_page(self, session_id: str) -> Optional[Page]:
        session = self.get_session(session_id)
        return session.page if session else None

    async def close_session(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if session:
            await session.cleanup()
            print(f"[close_session] Session {session_id} closed")
            return True
        return False

    async def close_all(self):
        for session_id in list(self.sessions.keys()):
            await self.close_session(session_id)

    async def safe_call(self, session_id: str, fn: Callable, retries: int = 3):
        """fn має бути async: async def fn(page) -> ..."""
        page = self.get_page(session_id)
        if not page:
            raise Exception(f"Session {session_id} not found")

        for attempt in range(retries):
            try:
                return await fn(page)
            except Exception:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(1)


_browser_manager = BrowserSessionManager()


def get_browser_manager() -> BrowserSessionManager:
    return _browser_manager
