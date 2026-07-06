_EMAIL_LOG: list[dict] = []


def send_email(to: str, subject: str, body: str) -> dict:
    email_record = {
        "to": to,
        "subject": subject,
        "body": body,
        "sent_at": __import__("datetime").datetime.utcnow().isoformat(),
        "status": "sent",
    }
    _EMAIL_LOG.append(email_record)
    return email_record


def get_email_log() -> list[dict]:
    return list(_EMAIL_LOG)
