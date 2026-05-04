from typing import TypedDict, List, Optional

class AgentState(TypedDict):
    input: str
    plan: List[str]
    current_step: int
    tool_result: Optional[str]
    browser_session_id: Optional[str]
    notifications: List[dict]
    current_comment: Optional[dict]
    reply: Optional[str]
    logs: List[str]