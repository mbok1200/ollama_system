def has_notifications(state):
    if state["notifications"]:
        return "process"
    return "end"


def loop_router(state):
    if state["notifications"]:
        return "next"
    return "end"