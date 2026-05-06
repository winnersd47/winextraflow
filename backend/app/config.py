from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://winextraflow:changeme@localhost:5432/winextraflow"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    # Email (SMTP)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    frontend_url: str = "http://localhost:3000"

    # TradingView
    tradingview_webhook_secret: str = ""

    # Telegram
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_phone: str = ""

    # AI Rating
    ai_rating_enabled: bool = True
    signal_expiry_hours: int = 168  # 7 days

    # Stripe
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""

    # Marketplace
    marketplace_enabled: bool = True
    revenue_share_author_pct: float = 70.0
    revenue_share_platform_pct: float = 30.0

    # Execution
    execution_enabled: bool = True
    execution_min_confidence: float = 0.6
    execution_daily_loss_limit: float = 500.0  # USD, 0 = no limit

    # Referral
    referral_reward_type: str = "premium_days"
    referral_level1_reward: int = 7   # days of Premium for direct referral
    referral_level2_reward: int = 3   # days of Premium for indirect referral
    referral_max_levels: int = 2
    referral_base_url: str = "http://localhost:3000/register"

    # App
    app_env: str = "development"
    app_debug: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
