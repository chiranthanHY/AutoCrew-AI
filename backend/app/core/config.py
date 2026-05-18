from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Main application settings loaded from environment variables.
    """
    # Environment
    environment: str = "development"

    # AI Models / APIs
    groq_api_key: str = ""
    tavily_api_key: Optional[str] = None

    # Database
    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/autocrew"

    # LangSmith Observability
    langchain_tracing_v2: str = "false"
    langchain_api_key: Optional[str] = None
    langchain_project: str = "autocrew_ai"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

# Global settings instance
settings = Settings()
