# find_cookie.py

from pathlib import Path
import shutil
import os
import random


def find_browser_profiles():
    candidates = []

    local = os.getenv("LOCALAPPDATA")
    if local:
        local = Path(local)

        candidates += [
            ("chrome", local / "Google/Chrome/User Data"),
            ("edge", local / "Microsoft/Edge/User Data"),
            ("brave", local / "BraveSoftware/Brave-Browser/User Data"),
        ]

    valid = []

    for name, path in candidates:
        if not path.exists():
            continue

        # 🔥 перевіряємо що є профілі
        has_profiles = (
            (path / "Default").exists() or
            any(path.glob("Profile*"))
        )

        if has_profiles:
            valid.append((name, path))

    if not valid:
        return None, None

    # 🔥 ПРІОРИТЕТ
    priority = ["chrome", "edge", "brave"]

    for p in priority:
        for name, path in valid:
            if name == p:
                return name, path

    return valid[0]

def find_profile_dir(user_data_path: Path):
    if (user_data_path / "Default").exists():
        return "Default"

    profiles = sorted(user_data_path.glob("Profile*"))
    if profiles:
        return profiles[0].name

    raise Exception("No profile found")

def create_safe_copy(user_data_path: Path, profile: str):
    """
    Копіюємо тільки потрібний профіль (НЕ весь User Data)
    щоб уникнути lock і corruption
    """

    base_tmp = Path("browser_profiles")
    base_tmp.mkdir(exist_ok=True)

    # унікальна папка
    target = base_tmp / f"profile_{profile}_{random.randint(1000,9999)}"

    src = user_data_path / profile

    if not src.exists():
        raise Exception("Profile not found")

    shutil.copytree(src, target, dirs_exist_ok=True)

    return str(target)


def get_browser_launch_config():
    browser, user_data = find_browser_profiles()

    if not browser:
        return {
            "user_data_dir": "user_data",
            "channel": "chrome",
            "args": ["--disable-blink-features=AutomationControlled"]
        }

    profile = find_profile_dir(user_data)

    channel_map = {
        "chrome": "chrome",
        "edge": "msedge",
        "brave": "chrome"
    }

    return {
        "user_data_dir": str(user_data),  # 🔥 РЕАЛЬНИЙ профіль
        "channel": channel_map[browser],
        "args": [
            f"--profile-directory={profile}",
            "--disable-blink-features=AutomationControlled"
        ]
    }