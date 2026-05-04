from states.AgentState import AgentState
from pathlib import Path
from dotenv import load_dotenv
from utils.browser_session_manager import get_browser_manager
import asyncio

load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

from classes.generate_multi.main import GenerateMultiProviderMain

browser_manager = get_browser_manager()


async def open_browser(state: AgentState) -> AgentState:
    print("[open_browser] Starting...")
    try:
        session_id = await browser_manager.create_new_session()
        print(f"[open_browser] Session created: {session_id}")
        return {**state, "browser_session_id": session_id, "logs": state["logs"] + ["browser opened"]}
    except Exception as e:
        error_msg = f"Failed to open browser: {str(e)}"
        print(f"[open_browser] {error_msg}")
        return {**state, "logs": state["logs"] + [error_msg]}


async def open_page(state: AgentState) -> AgentState:
    session_id = state.get("browser_session_id")
    if not session_id:
        return {**state, "logs": state["logs"] + ["open_page: no browser session"]}

    async def _navigate(page):
        await page.goto("https://www.linkedin.com/", wait_until="domcontentloaded")
        return page.url

    try:
        url = await browser_manager.safe_call(session_id, _navigate)
        print(f"[open_page] Navigated to: {url}")
        await asyncio.sleep(2)
        return {**state, "logs": state["logs"] + [f"page opened: {url}"]}
    except Exception as e:
        error_msg = f"Failed to open page: {str(e)}"
        print(f"[open_page] {error_msg}")
        return {**state, "logs": state["logs"] + [error_msg]}


async def wait_for_login(state: AgentState) -> AgentState:
    """
    Чекає поки користувач авторизується в LinkedIn.
    Перевіряє кожні 3 секунди через JS evaluate з таймаутом 2с.
    """
    session_id = state.get("browser_session_id")
    if not session_id:
        return {**state, "logs": state["logs"] + ["wait_for_login: no browser session"]}

    print("[wait_for_login] Waiting for LinkedIn login...")

    while True:
        await asyncio.sleep(3)

        page = browser_manager.get_page(session_id)
        if not page:
            return {**state, "logs": state["logs"] + ["wait_for_login: session lost"]}

        try:
            url = page.url
            print(f"[wait_for_login] Current URL: {url}")
            if "/feed" in url or "/in/" in url or "/mynetwork" in url or "/jobs" in url or "/messaging" in url:
                print("[wait_for_login] Logged in, continuing...")
                return {**state, "logs": state["logs"] + ["linkedin logged in"]}
        except Exception:
            pass


async def check_notifications(state: AgentState) -> AgentState:
    session_id = state.get("browser_session_id")
    if not session_id:
        return {**state, "logs": state["logs"] + ["No browser session"]}

    async def _check(page):
        # TODO: реальна логіка парсингу сповіщень LinkedIn
        return [{"text": "Someone commented on your post", "post_url": "https://example.com/post/1"}]

    try:
        notifications = await browser_manager.safe_call(session_id, _check)
        return {**state, "notifications": notifications, "logs": state["logs"] + ["found notifications"]}
    except Exception as e:
        return {**state, "logs": state["logs"] + [f"Failed to check notifications: {str(e)}"]}


async def open_post(state: AgentState) -> AgentState:
    session_id = state.get("browser_session_id")
    notifications = list(state.get("notifications", []))

    if not session_id or not notifications:
        return {**state, "logs": state["logs"] + ["No session or notifications"]}

    notif = notifications.pop(0)

    async def _open(page):
        # await page.goto(notif["post_url"], wait_until="domcontentloaded")
        await asyncio.sleep(1)
        return True

    try:
        await browser_manager.safe_call(session_id, _open)
        return {
            **state,
            "notifications": notifications,
            "current_comment": {"text": "Nice post!", "post_url": notif.get("post_url")},
            "logs": state["logs"] + ["post opened"],
        }
    except Exception as e:
        return {**state, "logs": state["logs"] + [f"Failed to open post: {str(e)}"]}


async def generate_reply(state: AgentState) -> AgentState:
    current_comment = state.get("current_comment")
    if not current_comment:
        return {**state, "logs": state["logs"] + ["No current comment"]}

    try:
        result = await _llm_generate(state, f"Reply to: {current_comment['text']}")
        return {**state, "reply": result.get("content", ""), "logs": state["logs"] + ["reply generated"]}
    except Exception as e:
        return {**state, "logs": state["logs"] + [f"Failed to generate reply: {str(e)}"]}


async def post_reply(state: AgentState) -> AgentState:
    session_id = state.get("browser_session_id")
    reply = state.get("reply", "")

    if not session_id or not reply:
        return {**state, "logs": state["logs"] + ["Missing session or reply"]}

    async def _post(page):
        # await page.fill("textarea.comment", reply)
        # await page.click("button.submit")
        await asyncio.sleep(1)
        return True

    try:
        await browser_manager.safe_call(session_id, _post)
        return {**state, "logs": state["logs"] + ["reply posted"]}
    except Exception as e:
        return {**state, "logs": state["logs"] + [f"Failed to post reply: {str(e)}"]}


async def close_browser(state: AgentState) -> AgentState:
    session_id = state.get("browser_session_id")
    if not session_id:
        return state

    session = browser_manager.get_session(session_id)
    if session:
        await browser_manager.close_session(session_id)
        print(f"[close_browser] Session {session_id} closed")
        return {**state, "logs": state["logs"] + ["browser closed"]}
    else:
        print(f"[close_browser] Session {session_id} already closed")
        return state


async def _llm_generate(state: AgentState, prompt: str) -> dict:
    full_prompt = f"""
Context:
Plan: {state.get('plan', [])}
Tool result: {state.get('tool_result')}

Task:
{prompt}
"""
    gm = GenerateMultiProviderMain()
    return await gm.generate(prompt=full_prompt, system_prompt="", model="")
