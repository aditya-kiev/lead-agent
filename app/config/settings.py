from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Lead Qualification Agent"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lead_agent"
    redis_url: str | None = None

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.1
    gemini_timeout: float = 30.0
    gemini_rpm_limit: int = 10

    langchain_tracing_v2: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "lead-qualification-agent"

    max_conversation_history: int = 50
    qualification_threshold_hot: float = 0.7
    qualification_threshold_warm: float = 0.4
    human_handoff_confidence: float = 0.3

    api_key: str = ""
    allowed_origins: list[str] = []

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    sms_enabled: bool = False

    calendly_api_key: str = ""
    calendly_event_type_uri: str = ""
    calendly_user_uri: str = ""
    calendly_enabled: bool = False

    calendar_availability_days: int = 14
    meeting_duration_minutes: int = 30


settings = Settings()
