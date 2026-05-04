import sys
from pathlib import Path

# Universal root resolver — works from any working directory or launch method
_workspace_dir = Path(__file__).resolve().parent
_project_root = _workspace_dir.parent.parent
for _p in [str(_workspace_dir), str(_project_root)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langgraph.graph import StateGraph
from states.AgentState import AgentState
from nodes.Agent import open_browser, open_page, wait_for_login, check_notifications, open_post, generate_reply, post_reply, close_browser
from router import has_notifications, loop_router


graph = StateGraph(AgentState)

graph.add_node("open_browser", open_browser)
graph.add_node("open_page", open_page)
graph.add_node("wait_for_login", wait_for_login)
graph.add_node("check_notifications", check_notifications)
graph.add_node("open_post", open_post)
graph.add_node("generate_reply", generate_reply)
graph.add_node("post_reply", post_reply)
graph.add_node("close_browser", close_browser)

graph.set_entry_point("open_browser")

graph.add_edge("open_browser", "open_page")
graph.add_edge("open_page", "wait_for_login")
graph.add_edge("wait_for_login", "check_notifications")

graph.add_conditional_edges(
    "check_notifications",
    has_notifications,
    {
        "process": "open_post",
        "end": "close_browser"
    }
)

graph.add_edge("open_post", "generate_reply")
graph.add_edge("generate_reply", "post_reply")

graph.add_conditional_edges(
    "post_reply",
    loop_router,
    {
        "next": "open_post",
        "end": "close_browser"
    }
)

graph.add_edge("close_browser", "__end__")


app = graph.compile()
initial_state = AgentState(
    input="Start the agent",
    plan=[],
    current_step=0,
    tool_result=None,
    browser_session_id=None,
    notifications=[],
    current_comment=None,
    reply=None,
    logs=[]
)
if __name__ == "__main__":
    import asyncio
    import json
    from datetime import datetime

    async def main():
        final_state = None

        async for step in app.astream(initial_state):
            node_name = list(step.keys())[0]
            state = step[node_name]
            print(f"\n[{node_name}]")
            for log in state.get("logs", []):
                print(f"  {log}")
            final_state = state

        if final_state:
            output = {
                "run_at": datetime.now().isoformat(),
                "logs": final_state.get("logs", []),
                "notifications": final_state.get("notifications", []),
                "replies": final_state.get("reply"),
            }

            out_path = _workspace_dir / "run_results.json"
            existing = []
            if out_path.exists():
                try:
                    existing = json.loads(out_path.read_text(encoding="utf-8"))
                except Exception:
                    existing = []
            existing.append(output)
            out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nSaved to {out_path}")

    asyncio.run(main())