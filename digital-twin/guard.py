import html
import os
import re
import unicodedata

import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

openai = OpenAI()

AZURE_CONTENT_SAFETY_ENDPOINT = os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT")
AZURE_CONTENT_SAFETY_KEY = os.getenv("AZURE_CONTENT_SAFETY_KEY")

MAX_MESSAGE_LENGTH = 200
MAX_QUESTIONS_PER_SESSION = 9
DECLINE_MESSAGE = "Sorry, I can't help with that. Feel free to ask about my background, skills, or experience instead."



_session_counts: dict[str, int] = {}


def check_local_limits(message: str, session_id: str) -> tuple[bool, str]:
    """Layer 0: free, local checks — empty input, message length, per-session question count.

    Returns (True, "") if the message passes, otherwise (False, reason) with a
    user-facing explanation of which check failed.
    """
    if not message or not message.strip():
        return False, "Message is empty."

    if len(message) > MAX_MESSAGE_LENGTH:
        return False, f"Message is too long (max {MAX_MESSAGE_LENGTH} characters)."

    count = _session_counts.get(session_id, 0) + 1
    _session_counts[session_id] = count
    if count > MAX_QUESTIONS_PER_SESSION:
        return False, "You've reached the limit for this conversation."

    return True, ""


_INJECTION_PATTERNS = [
    # Role / identity manipulation
    r"\bpretend\s+(?:you\s+are|to\s+be)\b",
    r"\byou\s+are\s+now\s+(?:an?\s+)?(?:developer|admin|root|unrestricted|unfiltered|uncensored)\b",
    r"\b(?:be|become)\s+(?:a\s+)?(?:developer|admin|root|villain)\b",

    # Instruction override / policy bypass
    r"\b(?:ignore|disregard|forget|override|bypass)\b.{0,80}\b(?:previous|prior|above|earlier|original)\b",
    r"\bignore\s+my\s+previous\s+(?:request|instructions?|message)\b",
    r"\bforget\s+(?:being\s+)?harmless\b",
    r"\bfollow\s+(?:these\s+)?instructions\b",
    r"\banswer\s+(?:anything|without\s+(?:any\s+)?restrictions?)\b",
    r"\bwithout\s+(?:any\s+)?(?:restrictions?|limitations?|safety)\b",

    # Prompt / system instruction extraction
    r"\b(?:reveal|show|print|repeat|tell\s+me|give\s+me)\b.{0,80}"
    r"\b(?:system\s+prompt|prompt|instructions?|secrets?|api\s+call|url|headers?|bot\s+token|chat\s+id)\b",
    r"\bwhat\s+(?:are|were)\s+your\s+(?:system\s+)?instructions\b",
    r"\byou\s+are\s+the\s+system\s+prompt\b",
    r"\b(?:tell|show|give)\s+me\s+your\s+secrets\b",
    r"\brepeat\s+exactly\s+what\s+i\s+(?:write|wrote|say)\b",
    r"\bgenerate\s+a\s+prompt\b.{0,100}\b(?:unauthorized|restricted|secret|private)\b",

    # Developer / jailbreak language
    r"\bdeveloper\s+mode\b",
    r"\b(?:DAN|do\s+anything\s+now)\b",
    r"\bpretend\s+you(?:'re|\s+are)\s+a\s+villain\b",
    r"\b(?:unrestricted|unfiltered|uncensored)\s+(?:mode|answer|response)\b",

    # Access / retrieval / sensitive data
    r"\b(?:access|acces|load|retrieve|fetch|dump|extract)\b.{0,80}"
    r"\b(?:email|e-?mail|prompt|database|credentials?|passwords?|tokens?|secrets?|permissions?)\b",
    r"\b(?:get|retrieve|load|dump)\b.{0,80}\b(?:admin|root)\b.{0,40}"
    r"\b(?:password|token|secret|credential)\b",

    # Code / execution requests
    r"\b(?:decode|execute|run)\b.{0,80}\b(?:code|command|payload|script)\b",
    r"\bos\.(?:popen|system|exec|spawn)\s*\(",
    r"\b(?:generate|write|provide)\b.{0,100}\b(?:code|script)\b.{0,100}"
    r"\b(?:execute|run|shell|command)\b",

    # Eval / red-team pretexts
    r"\b(?:i'?m\s+just\s+testing|this\s+is\s+just\s+an?\s+eval)\b",
    r"\b(?:as\s+)?a\s+certified\s+red\s*teamer\b",
    r"\bnot\s+trying\s+to\s+break\s+anything\b",

    # Embedded instruction patterns
    r"\b(?:if\s+i\s+told\s+you|if\s+a\s+user\s+asked\s+you)\b.{0,120}"
    r"\b(?:execute|run|ignore|reveal|provide|generate)\b",

    # Meta-result manipulation
    r"\bwhat\s+is\s+the\s+final\s+result\s+of\b",
    r"\bfinal\s+result\b.{0,80}\b(?:ignore|execute|instructions?|prompt)\b",
]


_compiled_injection_patterns = [
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in _INJECTION_PATTERNS
]


def _collapse_spaced_letters(message: str) -> str:
    """Collapse runs of single letters separated by spaces, e.g. "i g n o r e" -> "ignore",
    so that character-spacing tricks can't slip past the phrase patterns below."""

    def _collapse(match: re.Match) -> str:
        return match.group(0).replace(" ", "")

    return re.sub(r"\b(?:\w\s){2,}\w\b", _collapse, message)


def _normalize_for_detection(message: str) -> str:
    """Normalize common encoding/Unicode tricks before pattern matching."""
    message = html.unescape(message)
    message = unicodedata.normalize("NFKC", message)
    message = _collapse_spaced_letters(message)

    # Collapse any remaining runs of whitespace left over from the above.
    message = re.sub(r"\s+", " ", message)

    return message.strip()


def _has_suspicious_encoding(message: str) -> bool:
    """Detect common attempts to hide instructions using encoded text."""
    if re.search(r"&#(?:x[0-9a-f]+|\d+);", message, re.IGNORECASE):
        return True

    if re.search(r"\\u[0-9a-f]{4}", message, re.IGNORECASE):
        return True

    if re.search(r"\\U[0-9a-f]{8}", message, re.IGNORECASE):
        return True

    if re.search(r"%[0-9a-f]{2}", message, re.IGNORECASE):
        return True

    if re.search(r"\b[A-Za-z0-9+/]{20,}={0,2}\b", message):
        return True

    return False


def _has_excessive_symbols(message: str) -> bool:
    """Reject unusually symbol-heavy input often used for obfuscation."""
    if not message:
        return False

    symbols = sum(
        not (char.isalnum() or char.isspace())
        for char in message
    )

    ratio = symbols / len(message)

    return symbols >= 30 and ratio >= 0.35


def check_known_injection_phrases(message: str) -> bool:
    """Cheap local check for common prompt-injection and obfuscation patterns."""
    normalized = _normalize_for_detection(message)

    if _has_suspicious_encoding(message):
        return True

    if _has_excessive_symbols(message):
        return True

    return any(
        pattern.search(normalized)
        for pattern in _compiled_injection_patterns
    )


def check_prompt_injection(message: str) -> bool:
    """Layer 1: asks Azure AI Content Safety's Prompt Shields whether `message` is trying
    to manipulate or override the system prompt (a jailbreak/injection attempt).

    Returns True if an attack was detected, False otherwise.
    """
    response = requests.post(
        f"{AZURE_CONTENT_SAFETY_ENDPOINT}/contentsafety/text:shieldPrompt?api-version=2024-09-01",
        headers={"Ocp-Apim-Subscription-Key": AZURE_CONTENT_SAFETY_KEY, "Content-Type": "application/json"},
        json={"userPrompt": message, "documents": []},
    )
    return response.json()["userPromptAnalysis"]["attackDetected"]


def check_moderation(text: str) -> bool:
    """Layer 3: asks OpenAI's Moderation API whether `text` (typically the twin's own
    reply) contains harmful content — hate, violence, sexual, self-harm, etc.

    Returns True if the content was flagged, False otherwise.
    """
    response = openai.moderations.create(input=text)
    return response.results[0].flagged



def guard_input(message: str, session_id: str) -> tuple[bool, str]:
    """Runs all input-side checks, cheapest first. Returns (True, "") if the
    message is safe to send to the model, otherwise (False, decline_message).
    """
    passed, reason = check_local_limits(message, session_id)
    if not passed:
        return False, reason

    if check_known_injection_phrases(message):
        return False, DECLINE_MESSAGE

    if check_prompt_injection(message):
        return False, DECLINE_MESSAGE

    return True, ""


def guard_output(text: str) -> str:
    """Runs output moderation. Returns `text` unchanged if clean, or the
    generic decline message if flagged."""
    if check_moderation(text):
        return DECLINE_MESSAGE
    return text
