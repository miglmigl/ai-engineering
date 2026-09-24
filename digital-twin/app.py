from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr

from context import system_prompt
from tools import tools, handle_tool_calls
from db import create_tables, log_conversation
from guard import guard_input, guard_output


load_dotenv(override=True)
openai = OpenAI()


def chat(message, history, request: gr.Request):
    user_message = message
    session_id = request.session_hash

    passed, reason = guard_input(user_message, session_id)
    if not passed:
        return reason

    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]
    response = openai.chat.completions.create(model="gpt-5.4-mini", messages=messages, tools=tools)
    while response.choices[0].finish_reason == "tool_calls":
        message = response.choices[0].message
        tool_calls = message.tool_calls
        results = handle_tool_calls(tool_calls, session_id)
        messages.append(message)
        messages.extend(results)
        response = openai.chat.completions.create(model="gpt-5.4-mini", messages=messages, tools=tools)
    final_reply = response.choices[0].message.content

    final_reply = guard_output(final_reply)

    log_conversation(session_id, user_message, final_reply)
    return final_reply


if __name__ == "__main__":
    create_tables()
    gr.ChatInterface(chat).launch(inbrowser=True)

