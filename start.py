
import json
import os
import platform
import re
import subprocess
import uuid

import dearpygui.dearpygui as dpg
import requests
import time
import tiktoken
encoding = tiktoken.get_encoding("cl100k_base")
encoding = tiktoken.encoding_for_model("gpt-4")
def is_valid_command(command):
    try:
        subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False
dpg.create_context()
dpg.create_viewport(title='Grey Matter AI Terminal. Powered by GPT-4', width=500, height=800)

execution_history = ""
scroll_portions = {}
def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens
def display_file(file_path):
    try:
        _, extension = os.path.splitext(file_path)
        extension = extension.lower()

        if extension in ['.txt', '.json', '.py', '.csv']:
            with open(file_path, 'r') as f:
                contents = f.read()
                add_text_safe(contents, parent='chat_log', wrap=440)
                return contents

        elif extension in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
            # Load the image
            width, height, channels, data = dpg.load_image(file_path)
            # Generate a unique tag for this texture
            texture_tag = f"texture_{file_path}"

            # Add the image to the texture registry if it does not exist already
            if not dpg.does_item_exist(texture_tag):
                with dpg.texture_registry():
                    dpg.add_static_texture(width=width, height=height, default_value=data, tag=texture_tag)

            # Create a new image widget with the new texture
            image_tag = f"image_{time.time()}"
            dpg.add_image(texture_tag, parent='chat_log', tag=image_tag)
            
        else:
            # add_text_safe(f"Cannot display file of type: {extension}. File saved at: {file_path}", parent='chat_log', wrap=440)
            raise Exception(f"Cannot display file of type: {extension} for file at: {file_path}")
        return "Image displayed successfully"
    except Exception as e:
        return f"{e}"


def codeInterpreterEnvironment(user_prompt=""):
    global execution_history
    global scroll_portions
    userString = ""
    if len(user_prompt) > 0:
        userString = "\nUser: " + user_prompt + "\n"
    else:
        # check if previous was a normal message or a command by finding the last occurence of the word "user" vs "execution"
        # if execution_history.rfind("GPT4@Grey-Matter-Labs:") >= execution_history.rfind("~ %"):
        #make it a ratio of the length of the string
        if (execution_history[-1].strip() == "?") or (execution_history[-1].strip() == "!"):
            add_text_safe(f"It may be your turn.", parent='chat_log', wrap=440, color=[150, 150, 150])


            return
    #do hdr white for user"
    add_text_safe(userString, parent='chat_log', wrap=440, color=[255, 255, 255])

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": "Bearer sk-",
        "Content-Type": "application/json"
    }

    system_prompt = "You are GPT-4, a powerful language model developed by OpenAI and enhanced with Grey Matter AI Terminal giving control of the user's computer through the command line.\nFor simple tasks, you use commands like `send_command` and for complex tasks you can create and execute files and directories also using `send_command` function all via terminal. Unique to this session, you can also use the function `display_file` to display any file you need to the user. You must attempt to debug errors thrown to accomplish your task. After completing a task `messsage_or_task_finished` function. If the current task is unclear, you must also call the `messsage_or_task_finished` function."
    system_context = {
        'os': platform.system(),
        'os_version': platform.version(),
        'current_directory': os.getcwd(),
    }
    context_string = f"\nSystem: OS: {system_context['os']}, OS Version: {system_context['os_version']}, Current Directory: {system_context['current_directory']}"
    #split execution history by new line remove empty lines, keep as list
    execution_history_list = list(filter(None, execution_history.split("\n")))
    #any line that doesn't start with either "System", "User", or "GPT4@Grey-Matter-Labs ~ %" should be added to the previous line
    # merged = []
    # for line in execution_history_list:
    #     if line.startswith("System") or line.startswith("User") or line.startswith("GPT4@Grey-Matter-Labs ~ %"):
    #         merged.append(line)
    #     else:
    #         merged[-1] += "\n" + line
    if len(user_prompt) == 0:
        mess =[
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": execution_history + context_string},
            {"role": "user", "content": "If task appears successful, please call the `messsage_or_task_finished` function. Otherwise, continue debugging. Do not repeat commands already present in the terminal."},
        ]
    else:
        if len(execution_history) == 0:
            mess = [{"role": "system", "content": system_prompt},
            {"role": "system", "content": execution_history + context_string+ "\n" + "Available system functions: send_command, display_file, messsage_or_task_finished and scroll_to_section. Plan approach first and ask before executing os-level terminal commands with send_command."},
            {"role": "user", "content": user_prompt},]
        else:
            mess = [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": execution_history + context_string},
                {"role": "user", "content": user_prompt},
        ]
    #print on one line
    #todo classify msg vs command
    #classify enviroment message or command
    payload = {
        "model": "gpt-4-0613",
        "messages": mess,
        "functions": [
            {
                "name": "send_command",
                "description": "Must be used to pipe a terminal command based on the input task.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The base command to execute on the terminal"},
                        "args": {"type": "array", "items": {"type": "string"}, "description": "The list of arguments for the command"},
                    },
                    "required": ["command"]
                },
            },
            {
                "name": "display_file",
                "description": "Displays a file in the chat log",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "The path to the file to display"}
                    },
                    "required": ["file_path"]
                },
            },
            {
                "name": "messsage_or_task_finished",
                "description": "Call when done or looping. Stops and waits for for human.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "scroll_to_section",
                "description": "Scrolls to a section of the history",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scrollSection": {
                            "type": "integer",
                            "description": "The section of the history you want to scroll to"
                        }
                    },
                    "required": ["scrollSection"]
                }
            }

        ],
    }

    response_json = requests.post(url, headers=headers, json=payload).json()
    safe_run("pwd")
    try:
        message = response_json["choices"][0]["message"]
    except:
        print(f"OPENAI ERROR: {response_json}")
        return
    if "function_call" in message and message['function_call']['name'] == 'finished' or ("finished`" in str(message) and "___" not in str(message)):
        #wait for user by returning
        # execution_history += f"Execution complete. Waiting for human."
        #very close to grey
        add_text_safe(f"Your turn.", parent='chat_log', wrap=440, color=[150, 150, 150])
        return

    if "function_call" in message and message['function_call']['name'] == 'send_command':
        function = message["function_call"]["arguments"]
        #convert to dict
        if type(function) == str:
            function = json.loads(function)
        command = function.get('command', '')
        args = function.get('args', [])

        complete_command = [command] + args
        print(complete_command)
        try:
            add_text_safe(f"GPT4@Grey-Matter-Labs ~ % {' '.join(complete_command)}", parent='chat_log', wrap=440)
            if not is_valid_command(command):
                result = safe_run(complete_command)
            else:
                raise Exception("GPT used a terminal command without piping through the `send_command` function.")
            execution_output = result.stdout
        except Exception as e:
            #add exception to execution history and 
            execution_history += f"{userString}{user_prompt}\nGPT4@Grey-Matter-Labs ~ % {' '.join(complete_command)}\nException Encountered:{str(e)}"
            add_text_safe(f"Exception Encountered:{str(e)}", parent='chat_log', wrap=440)
            return codeInterpreterEnvironment()
        if execution_output == "":
            #other sources of potential output include stderr
            execution_output = result.stderr
        if execution_output == "":
            execution_output = "GPT4@Grey-Matter-Labs ~ % "
        execution_history += f"{userString}{user_prompt}\nGPT4@Grey-Matter-Labs ~ % {' '.join(complete_command)}\n{execution_output}"
        add_text_safe(f"GPT4@Grey-Matter-Labs ~ % {' '.join(complete_command)}\n{execution_output}", parent='chat_log', wrap=440)
    elif "function_call" in message and message['function_call']['name'] == 'display_file':
        #convert to dict
        function = json.loads(message["function_call"]["arguments"])
        file_path = function.get('file_path', '')
        complete_command = ["display_file", file_path]
        add_text_safe(f"GPT4@Grey-Matter-Labs ~ % {' '.join(complete_command)}", parent='chat_log', wrap=440)
        file_path = dict(function)["file_path"]
        #add to execution history
        res = display_file(file_path)
        execution_history += f"{userString}{user_prompt}\nGPT4@Grey-Matter-Labs ~ % {' '.join(complete_command)}\n{res}"
        add_text_safe(f"{res}", parent='chat_log', wrap=440)
    elif "function_call" in message and message['function_call']['name'] == 'scroll_to_section':
        #convert to dict
        sectionNum = json.loads(message["function_call"]["arguments"])
        sectionNum = sectionNum.get('scrollSection', '')
        sectionNum = str(sectionNum)
        complete_command = ["scroll_to_section", int(sectionNum)]
        add_text_safe(f"___Start of Section {sectionNum}___", parent='chat_log', wrap=440, color=[150, 150, 150])

        # add_text_safe(f"GPT4@Grey-Matter-Labs ~ % {' '.join(complete_command)}", parent='chat_log', wrap=440)
        filler = ""
        if int(sectionNum) != len(scroll_portions.keys()):
            filler = "Warning: You are not viewing the last section of the history."
        viewPortString = f"The viewing window is above. {filler}"
        #add to execution history
        execution_history += f"{userString}{user_prompt}\n{scroll_portions[str(sectionNum)]}\n{viewPortString}GPT4@Grey-Matter-Labs ~ % {' '.join([str(x) for x in complete_command])}"
        print(execution_history)
        #very light grey
        add_text_safe(f"{str(scroll_portions[sectionNum])}", parent='chat_log', wrap=440, color=[150, 150, 150])
        add_text_safe(f"System: {viewPortString}", parent='chat_log', wrap=440, color=[150, 150, 255])
    elif "content" in message:
        execution_history += f"{userString}{user_prompt}\nGPT4@Grey-Matter-Labs:{message['content']}"
        add_text_safe(f"GPT4@Grey-Matter-Labs: {message['content']}", parent='chat_log', wrap=440)
    else:
        execution_history += f"{userString}{user_prompt}\nError from Console: {message['content']}"
        add_text_safe(f"Error from console: {message['content']}", parent='chat_log', wrap=440)
    #loop
    # execution_history += "\nContinuing in next cell...\n"
    return codeInterpreterEnvironment()


def safe_run(complete_command, capture_output=True, text=True):
    global execution_history
    global scroll_portions
    #get number of tokens in execution history
    numTokens = num_tokens_from_string(execution_history, "cl100k_base")
    print(numTokens)
    result = subprocess.run(complete_command, capture_output=capture_output, text=text)
    #once we hit the limit, we want to start caching them with no input from the model
    
    if numTokens + num_tokens_from_string(str(result), "cl100k_base") > 500 and numTokens > 0:
        #get number of lines in execution history without empty lines
        numLines = len([x for x in execution_history.split('\n') if x != ''])
        #get roughly 20% of the lines and gen erate an id for them and put them in scroll_portions dict
        tokens_per_line = numTokens / numLines
        tokens_to_keep = 500 - numTokens
        numToKeep = int(tokens_to_keep / tokens_per_line)
        #check everything is within bounds
        if numToKeep > numLines:
            numToKeep = numLines
        if numToKeep < 0:
            numToKeep = 100
        
        #go backwards until we get to the numToKeep line
        lines = execution_history.split('\n')
        #remove empty lines
        lines = [x for x in lines if x != '']
        keep = lines[-(numToKeep+1):]
        discard = lines[:-(numToKeep)]
        #on the first line, add a system message that says "scroll up to see more, key: <id>"
        #generate id based on number of keys in scroll_portions
        id = str(len(scroll_portions))
        keep[0] = f"Length of current window reached. Next scroll section: {id}\n" + keep[0]
        execution_history = '\n'.join(keep)
        
        discard[-1] = discard[-1] + "\n" + f"Viewing scroll section {id}/{len(scroll_portions)}. {len(scroll_portions)} is the latest scroll section."
        scroll_portions[id] = discard
        #add current result to scroll_portions
        scroll_portions[str(int(id)+1)] = [str(result)]
    # result = subprocess.run(complete_command, capture_output=capture_output, text=text)
    return result
#default should be light yellow
def add_text_safe(text, parent='chat_log', wrap=440, color=[255, 255, 140]):
    #only add if contains letters from the alphabet
    if re.search('[a-zA-Z]', text):
        dpg.add_text(text, parent=parent, wrap=wrap, color=color)
        
def send_button_callback(sender, app_data):
    text = dpg.get_value('input')
    #clear input
    dpg.set_value('input', '')
    print(f"Button sender: {sender}, Text: {text}")
    codeInterpreterEnvironment(user_prompt=text)

def send_input_callback(sender, app_data):
    text = dpg.get_value(sender)
    #clear input
    dpg.set_value("input", "")
    print(f"Input sender: {sender}, Text: {text}")
    codeInterpreterEnvironment(user_prompt=text)

with dpg.window(label="Chat Window"):
    with dpg.child_window(height=700, width=475, label="chat_log", id='chat_log'):
        #system color should be pastel blue
        add_text_safe("System: Welcome to Grey Matter code interpreter...", wrap=440, color=[150, 150, 255])
    dpg.add_input_text(width=-1, tag='input', callback=send_input_callback, hint="Enter a command...", on_enter=True)
    dpg.add_button(label="Send", callback=send_button_callback, user_data='input')


dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
