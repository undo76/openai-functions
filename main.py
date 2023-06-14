import json
from pathlib import Path

import openai
import rich as r


def read_openai_key() -> str:
    """Read the OpenAI API key from a file"""
    if not (Path.home() / ".openai_api_key").exists():
        r.print(
            "[bold red]Error: [/bold red]You need to create a file called [bold]~/.openai_api_key[/bold] with your OpenAI API key in it."
        )
        exit(1)

    with open(Path.home() / ".openai_api_key", "r") as f:
        return f.read().strip()


openai.api_key = read_openai_key()
engine = "gpt-3.5-turbo-16k-0613"

system_prompt = """
You are an AI assistant that helps people with their daily tasks. 
The assistant is helpful, creative, clever, and very friendly.
"""

history = [
    {"role": "system", "content": system_prompt},
]

functions = [
    {
        "name": "register_function",
        "description": "Register a function to be called later",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the function"},
                "description": {
                    "type": "string",
                    "description": "The description of the function",
                },
                "parameters": {
                    "type": "string",
                    "description": "The parameters of the function as a JSON schema. type: 'object'",
                },
                "python_code": {
                    "type": "string",
                    "description": "Python definition of the function as a string. Parameters are passed as keyword arguments. It should return a JSON serializable object.",
                },
            },
            "required": ["name", "description", "parameters", "python_code"],
        },
    },
    {
        "name": "show_functions",
        "description": "Show all registered functions",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]

registered_functions = {}


def define_function_from_string(string, namespace):
    exec(string, namespace)


def register_function(name: str, description: str, parameters: str, python_code: str):
    global functions
    global registered_functions

    # print(f"Registering function {name}...")
    functions.append(
        {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": json.loads(parameters),
            },
        }
    ),
    define_function_from_string(python_code, registered_functions)


def show_functions():
    import json

    global functions
    return json.dumps(functions)


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
        functions=functions,
        function_call="auto",
    )

    while True:
        message = response["choices"][0]["message"]
        # r.print("Response: ", response)
        history.append(message)

        if message.get("function_call"):
            function_call = message["function_call"]
            args = json.loads(function_call["arguments"])
            r.print(f"\n[white]{function_call['name']}({function_call['arguments']})\n")

            try:
                if function_call["name"] == "register_function":
                    register_function(**args)
                    ret = "Function registered"
                elif function_call["name"] == "show_functions":
                    ret = show_functions()
                else:
                    ret = json.dumps(
                        registered_functions[function_call["name"]](**args)
                    )
            except Exception as e:
                ret = f"Error: {e}"

            history.append(
                {
                    "role": "function",
                    "name": function_call["name"],
                    "content": ret,
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
