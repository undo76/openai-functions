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
# engine = "gpt-3.5-turbo-0613"
# engine = "gpt-4-0613"

system_prompt = """
You are an AI assistant that helps people with their daily tasks.
You are a very careful and experienced Python programmer too.
"""

history = [
    {"role": "system", "content": system_prompt},
]

functions = [
    {
        "name": "register_function",
        "description": "Register a function to be called later with the same name",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the function"},
                "description": {
                    "type": "string",
                    "description": "The description of the function",
                },
                "parameters": {
                    "type": "object",
                    "description": "The parameters of the function as JSON schema. Use `type: object` always, even if there are no parameters.",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "The type of the parameter",
                            "const": "object",
                        },
                        "properties": {
                            "type": "object",
                            "description": "The properties of the parameters as JSON schema.",
                            "properties": {},
                            "additionalProperties": True,
                        },
                    },
                    "required": ["type", "properties"],
                },
                "python_function_def": {
                    "type": "string",
                    "description": "def <name>(...). It should return a JSON serializable object.",
                },
            },
            "required": ["name", "description", "parameters", "python_function_def"],
        },
    },
    {
        "name": "unregister_function",
        "description": "Unregister a function",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the function"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_functions",
        "description": "Get all the available functions",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_history",
        "description": "Show the conversation history",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]

registered_functions = {}


def define_function_from_string(code: str, namespace):
    return exec(code, namespace)


def register_function(
    name: str, description: str, parameters: dict, python_function_def: str
):
    global functions
    global registered_functions

    # print(f"Registering function {name}...")
    new_function = {
        "name": name,
        "description": description,
        "parameters": parameters,
    }
    functions.append(new_function)
    define_function_from_string(python_function_def, registered_functions)
    return True


def unregister_function(name: str):
    global functions
    global registered_functions

    # print(f"Unregistering function {name}...")
    functions = [f for f in functions if f["name"] != name]
    del registered_functions[name]
    return True


def get_functions():
    global functions
    return functions


def get_history():
    global history
    return history


def call_function(function_name: str, args: dict):
    global registered_functions
    try:
        if function_name == "register_function":
            ret = register_function(**args)
        elif function_name == "unregister_function":
            ret = unregister_function(**args)
        elif function_name == "get_functions":
            ret = get_functions()
        elif function_name == "get_history":
            ret = get_history()
        else:
            ret = registered_functions[function_call["name"]](**args)
    except Exception as e:
        r.print(f"[bold red]Error: [/bold red]{e}")
        ret = {"error": str(e)}

    # r.print(f"[bold white]Return: [/bold white]{ret}\n")
    return json.dumps(ret)


while True:
    r.print("[yellow]You:[/yellow] ", end="")
    user_input = input("")
    if user_input == "exit":
        exit(0)

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
        stream=True,
    )

    r.print("[yellow]Assistant: [/yellow]", end="")
    stop = False
    while stop is False:
        collected_messages = []
        collected_function_call = []

        try:
            for chunk in response:
                # r.print(chunk["choices"][0])
                chunk_message = chunk["choices"][0]["delta"]

                if chunk_message.get("content") is not None:
                    r.print(f"{chunk_message['content']}", end="")
                    collected_messages.append(chunk_message)

                if chunk["choices"][0]["finish_reason"] == "stop":
                    stop = True
                    history.append(
                        {
                            "role": "assistant",
                            "content": "".join(
                                [m.get("content", "") for m in collected_messages]
                            ),
                        },
                    )
                    break

                if chunk["choices"][0]["finish_reason"] == "function_call":
                    r.print(f")\n")
                    function_call = {"name": None, "collected_arguments": []}
                    for fm in collected_function_call:
                        if fm["function_call"].get("name") is not None:
                            function_call["name"] = fm["function_call"]["name"]
                        if fm["function_call"].get("arguments") is not None:
                            function_call["collected_arguments"].append(
                                fm["function_call"]["arguments"]
                            )

                    function_call["arguments"] = json.loads(
                        "".join(function_call["collected_arguments"])
                    )

                    ret = call_function(
                        function_call["name"], function_call["arguments"]
                    )
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
                        stream=True,
                    )
                    break

                if chunk_message.get("function_call"):
                    if chunk_message["function_call"].get("name") is not None:
                        r.print(
                            f"\n[bold blue]{chunk_message['function_call']['name']}[/bold blue](",
                            end="",
                        )
                    if chunk_message["function_call"].get("arguments") is not None:
                        r.print(
                            f"[white]{chunk_message['function_call']['arguments']}",
                            end="",
                        )

                    collected_function_call.append(chunk_message)
                    continue

        except Exception as e:
            r.print(f"[bold red]Error: [/bold red]{e}")
            break
    print("")
