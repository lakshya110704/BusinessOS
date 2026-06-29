"""Central configuration. All env vars are loaded and validated here."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Meta WhatsApp Cloud API
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # Upstash Redis
    UPSTASH_REDIS_URL: str = ""
    UPSTASH_REDIS_TOKEN: str = ""

    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    PORT: int = 8000

    # Feature flags
    CONFIRM_ALL_ACTIONS: bool = True
    DAILY_SUMMARY_ENABLED: bool = True
    PAYMENT_REMINDERS_ENABLED: bool = True


settings = Settings()

# TODO(robustness): in ENVIRONMENT=production, assert required secrets
# (WHATSAPP_*, OPENAI_API_KEY, SUPABASE_*) are non-empty so a misconfigured
# deploy fails loudly at startup instead of silently 403-ing every webhook.
