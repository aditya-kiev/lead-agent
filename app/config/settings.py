from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Lead Qualification Agent"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lead_agent"
    redis_url: str | None = None

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.1

    langchain_tracing_v2: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "lead-qualification-agent"

    max_conversation_history: int = 50
    qualification_threshold_hot: float = 0.7
    qualification_threshold_warm: float = 0.4
    human_handoff_confidence: float = 0.3

    calendar_availability_days: int = 14
    meeting_duration_minutes: int = 30


settings = Settings()
