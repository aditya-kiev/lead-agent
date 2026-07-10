from fastapi import Header, HTTPException

from app.config.settings import settings


async def verify_api_key(x_api_key: str | None = Header(None)) -> None:
    if settings.api_key:
        if not x_api_key or x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
