from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres@localhost:5432/ta_umkm"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    BACKEND_API_URL: str = "http://localhost:8000"
    DB_STATEMENT_TIMEOUT_MS: int = 5000
    APP_ENV: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()