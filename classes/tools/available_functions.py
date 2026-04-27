LIST_AVAILABLE_FUNCTIONS = {
    "get_info": lambda: get_info()
}


def get_info():
    """Returns the information about the available functions tool."""
    return {
        "name": "Available Functions",
        "description": "Get a list of available functions that can be called by the model.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }