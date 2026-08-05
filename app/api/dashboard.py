import csv
import html
import io
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Header, Response
from fastapi.responses import HTMLResponse, StreamingResponse

from app.config.settings import settings
from app.database.crud import get_conversation
from app.database.models import LeadConversation
from app.database.session import async_session_factory

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])


async def require_dashboard_auth(
    authorization: str | None = Header(None),
) -> None:
    if not settings.dashboard_username or not settings.dashboard_password:
        raise HTTPException(status_code=401, detail="Dashboard not configured")
    if not authorization or not authorization.startswith("Basic "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        import base64
        decoded = base64.b64decode(authorization[len("Basic "):]).decode()
        username, _, password = decoded.partition(":")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not (
        secrets.compare_digest(username, settings.dashboard_username)
        and secrets.compare_digest(password, settings.dashboard_password)
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(_auth: None = Depends(require_dashboard_auth)) -> HTMLResponse:
    leads: list[LeadConversation] = []
    try:
        async with async_session_factory() as db_session:
            from sqlalchemy import select
            result = await db_session.execute(
                select(LeadConversation)
                .order_by(
                    LeadConversation.qualification_score.desc().nullslast(),
                    LeadConversation.updated_at.desc(),
                )
            )
            leads = list(result.scalars().all())
    except Exception as e:
        logger.exception("dashboard: failed to load leads: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load leads")

    rows_html = ""
    for lead in leads:
        score = f"{lead.qualification_score:.0%}" if lead.qualification_score is not None else "—"
        lead_name_safe = html.escape(lead.lead_name) if lead.lead_name else "—"
        status_safe = html.escape(lead.lead_status) if lead.lead_status else "—"
        stage_safe = html.escape(lead.conversation_stage) if lead.conversation_stage else "—"
        meeting = lead.meeting_time.isoformat() if lead.meeting_time else "—"
        transcript = ""
        if lead.conversation_history:
            for msg in lead.conversation_history:
                role = html.escape(msg.get("role", "unknown"))
                content = html.escape(msg.get("content", ""))
                transcript += f"<strong>{role}:</strong> {content}<br>"
        else:
            transcript = "<em>No conversation history</em>"
        budget = f"${lead.budget:,.0f}" if lead.budget else "—"

        rows_html += f"""
        <tr>
            <td>{lead_name_safe}</td>
            <td>{budget}</td>
            <td>{status_safe}</td>
            <td>{score}</td>
            <td>{stage_safe}</td>
            <td>{meeting}</td>
            <td><details><summary>Transcript</summary><div class="transcript">{transcript}</div></details></td>
        </tr>"""

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard — {settings.business_name}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #1a1a2e; padding: 24px; }}
  h1 {{ font-size: 24px; margin-bottom: 8px; }}
  .subtitle {{ color: #666; margin-bottom: 24px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  th, td {{ text-align: left; padding: 10px 14px; border-bottom: 1px solid #e8ecf0; font-size: 13px; }}
  th {{ background: #f0f2f5; font-weight: 600; color: #555; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }}
  tr:hover td {{ background: #f8f9fb; }}
  details {{ cursor: pointer; }}
  .transcript {{ margin-top: 6px; padding: 10px; background: #f8f9fb; border-radius: 6px; font-size: 12px; line-height: 1.6; max-height: 300px; overflow-y: auto; }}
  .transcript strong {{ color: #2b5797; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
  .badge-hot {{ background: #fee2e2; color: #dc2626; }}
  .badge-warm {{ background: #fef3c7; color: #d97706; }}
  .badge-cold {{ background: #dbeafe; color: #2563eb; }}
  .nav {{ margin-bottom: 20px; display: flex; gap: 16px; align-items: center; }}
  .nav a {{ color: #2b5797; text-decoration: none; font-size: 14px; }}
  .nav a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="nav">
  <h1>{settings.business_name}</h1>
  <a href="/leads/export.csv">Export CSV</a>
</div>
<div class="subtitle">{len(leads)} lead(s)</div>
<table>
<thead><tr>
  <th>Name</th><th>Budget</th><th>Status</th><th>Score</th><th>Stage</th><th>Meeting</th><th>Transcript</th>
</tr></thead>
<tbody>
{rows_html}
</tbody>
</table>
</body>
</html>"""
    return HTMLResponse(content=page_html)


@router.get("/leads/export.csv", response_class=StreamingResponse)
async def export_csv(_auth: None = Depends(require_dashboard_auth)) -> StreamingResponse:
    leads: list[LeadConversation] = []
    try:
        async with async_session_factory() as db_session:
            from sqlalchemy import select
            result = await db_session.execute(
                select(LeadConversation).order_by(LeadConversation.updated_at.desc())
            )
            leads = list(result.scalars().all())
    except Exception as e:
        logger.exception("export_csv: failed to load leads: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load leads")

    f = io.StringIO()
    writer = csv.writer(f)
    writer.writerow([
        "session_id", "lead_name", "company_name", "industry", "budget",
        "timeline", "problem_statement", "qualification_score", "lead_status",
        "lead_intent", "lead_type", "booking_confirmed", "meeting_time",
        "conversation_stage", "human_escalated",
    ])
    for lead in leads:
        writer.writerow([
            lead.session_id,
            lead.lead_name or "",
            lead.company_name or "",
            lead.industry or "",
            lead.budget or "",
            lead.timeline or "",
            lead.problem_statement or "",
            lead.qualification_score or "",
            lead.lead_status or "",
            lead.lead_intent or "",
            lead.lead_type or "",
            "Yes" if lead.booking_confirmed else "No",
            lead.meeting_time.isoformat() if lead.meeting_time else "",
            lead.conversation_stage or "",
            "Yes" if lead.human_escalated else "No",
        ])

    f.seek(0)
    return StreamingResponse(
        iter([f.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )
