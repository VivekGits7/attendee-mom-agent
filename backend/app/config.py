from typing import List, Literal
from urllib.parse import quote

from pydantic import EmailStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # SERVER
    APP_NAME: str = Field(default="MOM Generator", description="App name")
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8010, description="Server port")
    ENVIRONMENT: str = Field(default="development", description="Environment")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    INTERNAL_API_KEY: str = Field(
        default="", description="Key callers send in the X-API-Key header"
    )
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000"], description="Allowed origins in production"
    )

    # DATABASE
    POSTGRES_DB_HOST: str = Field(default="localhost", description="DB host")
    POSTGRES_DB_PORT: int = Field(default=5432, description="DB port")
    POSTGRES_DB_NAME: str = Field(default="mom_generator", description="DB name")
    POSTGRES_DB_USER: str = Field(default="postgres", description="DB user")
    POSTGRES_DB_PASSWORD: str = Field(default="", description="DB password")

    # ATTENDEE
    ATTENDEE_BASE_URL: str = Field(
        default="http://localhost:8000", description="Attendee service base URL"
    )
    ATTENDEE_API_KEY: str = Field(default="", description="Attendee API key")
    ATTENDEE_WEBHOOK_SECRET: str = Field(
        default="", description="Base64 webhook secret from the Attendee UI"
    )
    ATTENDEE_WEBHOOK_URL: str = Field(
        default="", description="Public ngrok URL of our webhook endpoint"
    )
    ATTENDEE_BOT_NAME: str = Field(
        default="TCG Notetaker", description="Name shown in the meeting"
    )
    ATTENDEE_TIMEOUT_SECONDS: int = Field(
        default=30, description="HTTP timeout for Attendee calls"
    )
    TRANSCRIPTION_PROVIDER: Literal["closed_captions", "deepgram", "openai"] = Field(
        default="closed_captions", description="Transcript source"
    )
    OPENAI_TRANSCRIPTION_MODEL: Literal[
        "gpt-4o-transcribe", "gpt-4o-mini-transcribe", "gpt-4o-transcribe-diarize"
    ] = Field(default="gpt-4o-transcribe", description="OpenAI speech-to-text model")
    DEEPGRAM_MODEL: str = Field(
        default="nova-3", description="Deepgram model when provider is deepgram"
    )
    DEEPGRAM_LANGUAGE: str = Field(
        default="multi", description="Deepgram language when provider is deepgram"
    )
    WEBHOOK_RATE_LIMIT: str = Field(
        default="1200/minute", description="Rate limit for the Attendee webhook"
    )

    # BOT AUTO LEAVE
    BOT_ONLY_PARTICIPANT_TIMEOUT_SECONDS: int = Field(
        default=30, description="Leave this long after everyone else left"
    )
    BOT_WAIT_FOR_HOST_TIMEOUT_SECONDS: int = Field(
        default=900, description="Leave if the meeting never starts"
    )
    BOT_WAITING_ROOM_TIMEOUT_SECONDS: int = Field(
        default=600, description="Leave if nobody admits the bot"
    )
    BOT_SILENCE_TIMEOUT_SECONDS: int = Field(
        default=900, description="Leave after this much silence"
    )
    BOT_SILENCE_ACTIVATE_AFTER_SECONDS: int = Field(
        default=1200, description="Silence check starts after this"
    )
    BOT_MAX_UPTIME_SECONDS: int = Field(
        default=14400, description="Hard cap on bot runtime"
    )
    BOT_KEYWORDS: List[str] = Field(
        default=["bot", "notetaker", "otter", "fireflies", "fathom", "read.ai"],
        description="Participants with these words are treated as bots",
    )
    TRANSCRIPT_READY_MAX_WAIT_SECONDS: int = Field(
        default=300, description="Max wait for the final transcript"
    )
    TRANSCRIPT_READY_POLL_SECONDS: int = Field(
        default=10, description="Poll interval for the final transcript"
    )

    # OPENAI
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    OPENAI_MOM_MODEL: str = Field(
        default="gpt-5.4", description="Model used for minutes"
    )
    OPENAI_MOM_REASONING_EFFORT: Literal["minimal", "low", "medium", "high"] = Field(
        default="low", description="Reasoning effort for minutes"
    )
    OPENAI_MOM_MAX_OUTPUT_TOKENS: int = Field(
        default=16000, description="Output cap for minutes, reasoning included"
    )

    # EMAIL
    SMTP_HOST: str = Field(default="smtp.office365.com", description="SMTP host")
    SMTP_PORT: int = Field(default=587, description="SMTP port")
    SMTP_USERNAME: str = Field(default="", description="SMTP username")
    SMTP_PASSWORD: str = Field(default="", description="SMTP password")
    SMTP_START_TLS: bool = Field(default=True, description="Use STARTTLS on port 587")
    SMTP_USE_SSL: bool = Field(
        default=False, description="Use implicit TLS on port 465"
    )
    SMTP_TIMEOUT_SECONDS: int = Field(default=30, description="SMTP timeout")
    SMTP_FROM_EMAIL: EmailStr = Field(
        default="mom@tcg.com", description="Verified sender address"
    )
    SMTP_FROM_NAME: str = Field(
        default="TCG Meeting Notes", description="Sender display name"
    )
    ALLOWED_EMAIL_DOMAINS: List[str] = Field(
        default=["tcg.com"], description="Domains allowed to receive minutes"
    )
    DEFAULT_MOM_EMAIL: EmailStr = Field(
        default="meetings@tcg.com", description="Fallback recipient for minutes"
    )

    @model_validator(mode="after")
    def validate_email_domains(self) -> "Settings":
        allowed = {d.lower().lstrip("@") for d in self.ALLOWED_EMAIL_DOMAINS}
        sender_domain = self.SMTP_FROM_EMAIL.rsplit("@", 1)[-1].lower()
        if sender_domain not in allowed:
            raise ValueError(f"SMTP_FROM_EMAIL must be on one of {sorted(allowed)}")
        self.ALLOWED_EMAIL_DOMAINS = sorted(allowed)
        return self

    @property
    def database_url(self) -> str:
        user = quote(self.POSTGRES_DB_USER, safe="")
        password = quote(self.POSTGRES_DB_PASSWORD, safe="")
        database = quote(self.POSTGRES_DB_NAME, safe="")
        return f"postgresql://{user}:{password}@{self.POSTGRES_DB_HOST}:{self.POSTGRES_DB_PORT}/{database}"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()
