import logging
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agent.prompts.templates import OBJECTION_DETECTION_PROMPT

logger = logging.getLogger(__name__)

OBJECTION_TYPES = [
    "pricing",
    "timing",
    "trust",
    "competition",
    "need",
    "authority",
    "none",
]

# Cheap keyword pre-filter — catches obvious non-objections (greetings, simple
# answers) and obvious objections (price complaints, "not now", etc.) without
# firing an LLM call.  Only ambiguous messages escalate to the model.
_OBJECTION_KEYWORDS = {
    "pricing": [
        "expensive", "too much", "overpriced", "price", "cost", "budget",
        "can't afford", "out of range", "spend that much",
    ],
    "timing": [
        "not now", "not ready", "not the right time", "later", "need to think",
        "need time", "call me back", "busy", "check back",
    ],
    "trust": [
        "scam", "sketchy", "untrustworthy", "too good to be true",
        "never heard", "is this legit", "can you prove",
    ],
    "competition": [
        "competitor", "alternatives", "other option", "using someone else",
        "already have", "compare", "switch from",
    ],
    "need": [
        "don't need", "not interested", "no value", "not for us",
        "waste of time", "not useful",
    ],
    "authority": [
        "check with", "talk to my", "discuss with", "ask my",
        "manager", "boss", "team", "partner", "wife", "husband",
    ],
}

# Phrases that almost certainly do NOT contain an objection
_SAFE_PHRASES = {
    "hello", "hi ", "hey", "good morning", "good afternoon",
    "thanks", "thank you", "sure", "okay", "ok ", "yes", "no",
    "interested", "tell me more", "help", "please",
}


# Return type: (match_type, objection_type)
# match_type: True = objection found, False = safe, None = ambiguous
_PreFilterResult = tuple[bool | None, str | None]


def _classify_message(message: str) -> _PreFilterResult:
    """Classify a message into objection / safe / ambiguous without an LLM call.

    Returns:
        ``(True, type)``  — keyword matched an objection type.
        ``(False, None)`` — message looks safe (greeting, thanks, etc.).
        ``(None, None)``  — ambiguous; caller should escalate to the LLM.
    """
    msg = message.lower().strip()

    # Safe-list check for common non-objection phrases
    if any(p in msg for p in _SAFE_PHRASES) and len(msg) < 60:
        return False, None

    # Objection keyword check
    for otype, keywords in _OBJECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in msg:
                return True, otype

    # No strong signal either way
    return None, None


@dataclass
class DetectObjectionResult:
    has_objection: bool
    objection_type: str | None
    evidence: str = ""
    source: str = "llm"


async def detect_objection(
    user_message: str, model: ChatGoogleGenerativeAI
) -> DetectObjectionResult:
    if not user_message.strip():
        return DetectObjectionResult(has_objection=False, objection_type=None, source="empty")

    # Keyword pre-filter
    match_type, otype = _classify_message(user_message)
    if match_type is True:
        logger.debug("objection pre-filter matched: type=%s", otype)
        return DetectObjectionResult(
            has_objection=True, objection_type=otype, evidence=user_message[:80], source="keyword",
        )
    if match_type is False:
        # Safe-phrase matched — skip LLM
        logger.debug("objection pre-filter: safe message, skipping LLM")
        return DetectObjectionResult(
            has_objection=False, objection_type=None, source="safe",
        )

    # Ambiguous (match_type is None) — escalate to LLM
    response = await model.ainvoke([
        SystemMessage(
            content=OBJECTION_DETECTION_PROMPT.format(input=user_message)
        ),
        HumanMessage(content=user_message),
    ])
    text = response.content.strip().lower()

    for ot in OBJECTION_TYPES:
        if ot in text:
            if ot == "none":
                return DetectObjectionResult(
                    has_objection=False, objection_type=None, evidence=text, source="llm",
                )
            return DetectObjectionResult(
                has_objection=True, objection_type=ot, evidence=text, source="llm",
            )

    return DetectObjectionResult(
        has_objection=False, objection_type=None, evidence=text, source="llm",
    )
