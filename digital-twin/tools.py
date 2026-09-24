import json

from sqlalchemy.orm import Session

from db import Lead, UnknownQuestion, engine
from notifier import notify


MAX_LEADS_PER_SESSION = 3
_lead_counts: dict[str, int] = {}


def record_user_details(email, name="Name not provided", notes="not provided", session_id=None):
    count = _lead_counts.get(session_id, 0) + 1
    if count > MAX_LEADS_PER_SESSION:
        return "Already recorded contact details for this conversation — no need to submit more."
    _lead_counts[session_id] = count

    with Session(engine) as session:
        session.add(Lead(email=email, name=name, notes=notes))
        session.commit()
    notify(f"New lead: {name} <{email}> — {notes}")
    return "OK"


def record_unknown_question(question, session_id=None):
    with Session(engine) as session:
        session.add(UnknownQuestion(question=question))
        session.commit()
    notify(f"Unanswered: {question}")
    return "OK"


record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The email address of this user"},
            "name": {"type": "string", "description": "The user's name, if they provided it"},
            "notes": {"type": "string", "description": "Any additional info about the conversation that's worth recording to give context"}
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question that couldn't be answered"},
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{"type": "function", "function": record_user_details_json},
         {"type": "function", "function": record_unknown_question_json}]


def handle_tool_calls(tool_calls, session_id):
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        print(f"Tool called: {tool_name}", flush=True)
        tool = globals().get(tool_name)
        result = tool(**arguments, session_id=session_id) if tool else "No tool found"
        results.append({"role": "tool", "content": json.dumps(result), "tool_call_id": tool_call.id})
    return results
