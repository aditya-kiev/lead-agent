import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Boolean, DateTime, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.session import Base


class LeadConversation(Base):
    __tablename__ = "lead_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    lead_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    timeline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    problem_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualification_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    lead_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lead_intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    booking_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    meeting_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    conversation_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    conversation_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_node: Mapped[str | None] = mapped_column(String(50), nullable=True)
    human_escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
