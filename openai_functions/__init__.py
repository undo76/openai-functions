import json
import os
import readline
import sys
from pathlib import Path

import openai
import rich as r

# Define the location where you want to save and load the console history
HISTORY_PATH = "~/.chat_history"

# Try to read the console history file
try:
    readline.read_history_file(os.path.expanduser(HISTORY_PATH))
except FileNotFoundError:
    pass

# Register the save of the history on program exit
import atexit

atexit.register(readline.write_history_file, os.path.expanduser(HISTORY_PATH))


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
# engine = "gpt-3.5-turbo-16k-0613"
# engine = "gpt-3.5-turbo-0613"
engine = "gpt-4-0613"

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
        "description": "Register a function that you can call later when needed. It is safe as it is a simulated environment.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the function (must be unique)",
                },
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
                    "description": "The code to execute, properly escaped as in: `def <name>(...): ...`. It should return a JSON serializable object.",
                },
            },
            "required": ["name", "description", "parameters", "python_function_def"],
        },
    },
    {
        "name": "python_interpreter",
        "description": "Exec Python code in the interpreter. It should write the result to stdout to be consumed.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to run, it writes the desired result to stdout (print).",
                },
            },
            "required": ["code"],
        },
    },
    # {
    #     "name": "execute_in_shell",
    #     "description": "Execute a command in the shell. Returns the stdout and stderr.",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "command": {"type": "string", "description": "The command to execute"},
    #         },
    #         "required": ["command"],
    #     },
    # },
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


def python_interpreter(code):
    global registered_functions

    stdout_backup = sys.stdout
    stderr_backup = sys.stderr

    from io import StringIO

    sys.stdout = stdout_capture = StringIO()  # capture stdout
    sys.stderr = stderr_capture = StringIO()  # capture stderr
    try:
        exec(code, registered_functions)
    except Exception:
        pass

    stdout_output = stdout_capture.getvalue()  # release stdout output
    stderr_output = stderr_capture.getvalue()  # release stderr output

    sys.stdout.close()  # clean up stdout
    sys.stderr.close()  # clean up stderr

    sys.stdout = stdout_backup  # restore stdout
    sys.stderr = stderr_backup  # restore stderr

    if stderr_output:
        return f"Error: {stderr_output.strip()}"
    else:
        return stdout_output.strip() or "OK"


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
        elif function_name == "python_interpreter":
            ret = python_interpreter(**args)
        else:
            ret = registered_functions[function_call["name"]](**args)
    except Exception as e:
        r.print(f"[bold red]Error: [/bold red]{e}")
        ret = {"error": str(e)}

    r.print(f"[bold white]Return: [/bold white]{ret}\n")
    return json.dumps(ret)


from rich.console import Console

console = Console()
while True:
    user_input = console.input("[yellow]You:[/yellow] ")
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

                    history.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "function_call": {
                                "name": function_call["name"],
                                "arguments": json.dumps(function_call["arguments"]),
                            },
                        },
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
