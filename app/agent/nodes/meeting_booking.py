from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.prompts.templates import MEETING_BOOKING_SYSTEM_PROMPT
from app.agent.state import AgentState
from app.agent.tools.calendar import get_available_slots
from app.config.settings import settings


def create_meeting_booking_node(model: ChatOpenAI):
    async def meeting_booking_node(state: AgentState) -> dict:
        user_message = state["messages"][-1].content if state["messages"] else ""

        slots = get_available_slots(settings.calendar_availability_days)
        slot_labels = "\n".join(s["label"] for s in slots[:9])

        response = await model.ainvoke([
            SystemMessage(content=MEETING_BOOKING_SYSTEM_PROMPT.format(
                lead_name=state.get("lead_name", "there"),
                company_name=state.get("company_name", "your company"),
                lead_status=state.get("lead_status", "new"),
                days=settings.calendar_availability_days,
                available_slots=slot_labels,
                input=user_message,
            )),
            HumanMessage(content=user_message),
        ])

        confirmed = False
        meeting_time = None
        if any(phrase in user_message.lower() for phrase in ["yes", "confirm", "book", "schedule", "sure"]):
            for slot in slots:
                if slot["label"].lower() in user_message.lower() or slot["datetime"][:10] in user_message:
                    confirmed = True
                    meeting_time = slot["datetime"]
                    break

        if not confirmed and any(word in user_message.lower() for word in ["yes", "confirm", "book", "schedule", "sure", "sounds good", "that works"]):
            confirmed = True
            meeting_time = slots[0]["datetime"] if slots else None

        return {
            "messages": [AIMessage(content=response.content)],
            "conversation_history": [{"role": "assistant", "content": response.content}],
            "booking_confirmed": confirmed,
            "meeting_time": meeting_time,
            "current_node": "meeting_booking",
            "next_action": "end" if confirmed else "meeting_booking",
        }

    return meeting_booking_node
