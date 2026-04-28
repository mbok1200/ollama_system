from helpers.config import Config
from ollama import ChatResponse
from classes.tools import available_functions
class ToolsMain:
    def __init__(self):
        self.config = Config()
        self.ollama = self.config.ollama
        self.ollama_client = self.config.ollama_client
        self.list_available_functions = available_functions.LIST_AVAILABLE_FUNCTIONS
        self.available_functions = available_functions
    async def tools(self, model: str, messages: list, tool_calls: list[dict]):
        while True:
            response: ChatResponse = await self.ollama_client.chat(model=model, messages=messages, tools=tool_calls, think=True,)
            messages.append(response.message)
            if response.message.tool_calls:
                for tc in response.message.tool_calls:
                    if tc.function.name in self.list_available_functions:
                        print(f"Calling {tc.function.name} with arguments {tc.function.arguments}")
                        result = self.list_available_functions[tc.function.name](**tc.function.arguments)
                        print(f"Result: {result}")
                        # add the tool result to the messages
                        messages.append({'role': 'tool', 'tool_name': tc.function.name, 'content': str(result)})
            else:
                # end the loop when there are no more tool calls
                break
       
        return messages
