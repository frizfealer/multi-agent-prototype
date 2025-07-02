from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost/triage_agent_db"
    google_api_key: str = ""
    app_env: str = "development"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"


settings = Settings()