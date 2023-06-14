from pathlib import Path

import openai
import rich as r


def read_openai_key() -> str:
    """Read the OpenAI API key from a file"""
    with open(Path.home() / ".openai_api_key", "r") as f:
        return f.read().strip()


openai.api_key = read_openai_key()
engine = "gpt-3.5-turbo-0613"

system_prompt = """
You are an AI assistant that helps people with their daily tasks. 
The assistant is helpful, creative, clever, and very friendly.
"""

history = [
    {"role": "system", "content": system_prompt},
]

functions = [
    {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                },
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["location"],
        },
    }
]

while True:
    r.print("[yellow]You:[/yellow] ", end="")
    user_input = input("")
    if user_input == "exit":
        break

    history.append(
        {
            "role": "user",
            "content": user_input,
        },
    )

    response = openai.ChatCompletion.create(
        model=engine,
        messages=history,
        functions=[
            {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            }
        ],
        function_call="auto",
    )

    while True:
        message = response["choices"][0]["message"]
        # r.print("Response: ", response)
        history.append(message)

        if message.get("function_call"):
            function_call = message["function_call"]

            r.print(f"\n[white]{function_call['name']}({function_call['arguments']})\n")
            history.append(
                {
                    "role": "function",
                    "name": function_call["name"],
                    "content": "30 degrees celsius",
                }
            )

            response = openai.ChatCompletion.create(
                model=engine,
                messages=history,
                functions=functions,
                function_call="auto",
            )
        else:
            r.print(f"[yellow]AI:[/yellow] {message['content']}")
            break
