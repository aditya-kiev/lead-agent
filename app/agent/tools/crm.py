_CRM_LEADS: dict[str, dict] = {}


def update_crm(session_id: str, lead_data: dict) -> dict:
    _CRM_LEADS[session_id] = {
        **_CRM_LEADS.get(session_id, {}),
        **lead_data,
        "session_id": session_id,
        "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
    }
    return _CRM_LEADS[session_id]


def get_crm_lead(session_id: str) -> dict | None:
    return _CRM_LEADS.get(session_id)
