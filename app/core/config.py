from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres@localhost:5432/ta_umkm"
    AI_EXECUTOR_DATABASE_URL: str = (
        "postgresql+asyncpg://readonly_ai_executor:ai_executor_ro@localhost:5432/ta_umkm"
    )
    DB_STATEMENT_TIMEOUT_MS: int = 5000

    # LLM API Keys
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # LLM
    LLM_MODELS: str = "llama-3.3-70b,qwen3.8-27b,gpt-oss-120b"
    LLM_TIMEOUT_S: float = 30.0
    DEFAULT_PROMPT_STRATEGY: str = "few_shot"

    # Study area
    STUDY_AREA_NAME: str = "Kota Depok, Jawa Barat"
    STUDY_AREA_REGENCY_ID: int = 3276
    DEFAULT_CENTER_LAT: float = -6.36043
    DEFAULT_CENTER_LON: float = 106.83178
    DEFAULT_RADIUS_M: int = 500

    # API
    API_KEY: str = ""
    RATE_LIMIT_PER_MINUTE: int = 30
    EXPERIMENT_LOG_PATH: str = ""
    BACKEND_API_URL: str = "http://localhost:8000"
    APP_ENV: str = "development"

    @property
    def enabled_models(self) -> list[str]:
        return [m.strip() for m in self.LLM_MODELS.split(",") if m.strip()]


settings = Settings()
