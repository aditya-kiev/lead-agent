from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LeadStatus(str, Enum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    UNQUALIFIED = "unqualified"


class IntentType(str, Enum):
    PURCHASE = "purchase"
    INFORMATION = "information"
    SUPPORT = "support"
    PARTNERSHIP = "partnership"
    UNKNOWN = "unknown"


class MessageIn(BaseModel):
    session_id: str = Field(..., description="Unique session identifier")
    message: str = Field(..., description="Message content from the lead")
    channel: str = Field("web", description="Source channel: web, whatsapp, email, chat")


class StartConversationIn(BaseModel):
    session_id: str = Field(default="", description="Optional existing session ID")
    channel: str = Field("web", description="Source channel")


class StartConversationOut(BaseModel):
    session_id: str
    message: str
    lead_status: str | None = None


class MessageOut(BaseModel):
    session_id: str
    reply: str
    lead_status: str | None = None
    booking_confirmed: bool = False
    meeting_time: str | None = None
    human_escalated: bool = False
    next_action: str | None = None


class ConversationHistoryOut(BaseModel):
    session_id: str
    lead_name: str | None = None
    company_name: str | None = None
    industry: str | None = None
    budget: float | None = None
    timeline: str | None = None
    problem_statement: str | None = None
    qualification_score: float | None = None
    lead_status: str | None = None
    booking_confirmed: bool = False
    meeting_time: datetime | None = None
    human_escalated: bool = False
    conversation_history: list[dict[str, Any]] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HealthOut(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


class LeadScoreIn(BaseModel):
    budget: float | None = None
    timeline: str | None = None
    industry: str | None = None
    problem_statement: str | None = None
    intent: IntentType = IntentType.UNKNOWN


class LeadScoreOut(BaseModel):
    score: float
    status: LeadStatus
    reasoning: str


class MeetingBookIn(BaseModel):
    session_id: str
    proposed_time: datetime
    timezone: str = "UTC"


class MeetingBookOut(BaseModel):
    confirmed: bool
    meeting_time: datetime | None = None
    message: str
