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


@dataclass
class DetectObjectionResult:
    has_objection: bool
    objection_type: str | None
    evidence: str = ""


async def detect_objection(
    user_message: str, model: ChatGoogleGenerativeAI
) -> DetectObjectionResult:
    if not user_message.strip():
        return DetectObjectionResult(has_objection=False, objection_type=None)

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
                return DetectObjectionResult(has_objection=False, objection_type=None, evidence=text)
            return DetectObjectionResult(has_objection=True, objection_type=ot, evidence=text)

    return DetectObjectionResult(has_objection=False, objection_type=None, evidence=text)
