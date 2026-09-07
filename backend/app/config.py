import secrets as _secrets
import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://winextraflow:changeme@localhost:5432/winextraflow"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth — MUST be overridden via SECRET_KEY env var in production
    secret_key: str = ""
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    # Encryption — separate key for Fernet (exchange API keys encryption)
    encryption_key: str = ""

    # Admin seed (env-only, never hardcoded)
    admin_email: str = ""
    admin_username: str = ""
    admin_password: str = ""

    # Email (SMTP)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    frontend_url: str = "http://localhost:3000"

    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_bot_polling: bool = False      # start getUpdates polling (off when token shared)
    telegram_vip_channel_id: str = ""       # VIP channel chat_id (instant signals)
    telegram_free_channel_id: str = ""      # Free channel chat_id (delayed signals)
    telegram_growth_group_id: str = ""      # AI Growth Club group (marketing posts)
    telegram_free_delay_minutes: int = 120  # Delay for free channel (2 hours)

    # MAX Messenger Bot (Russian national messenger by VK)
    max_bot_token: str = ""
    max_vip_channel_id: str = ""            # MAX VIP channel (instant signals)
    max_free_channel_id: str = ""           # MAX free channel (delayed signals)

    # TradingView
    tradingview_webhook_secret: str = ""

    # Telegram (Telethon for channel parsing)
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_phone: str = ""
    telegram_parse_channels: str = ""  # comma-separated: beststocksru,channel2

    # MTProxy for Telegram (bypass blocking without VPN)
    # Get free servers from: https://t.me/ProxyMTProto or https://mtprotoproxy.app
    mtproxy_host: str = ""       # IP or domain
    mtproxy_port: int = 0        # port number
    mtproxy_secret: str = ""     # hex secret string

    # SOCKS5 Proxy for Telegram (alternative to MTProxy)
    socks5_host: str = ""        # IP or domain
    socks5_port: int = 0         # port number
    socks5_user: str = ""        # login (optional)
    socks5_pass: str = ""        # password (optional)

    # AI Providers (for deep analysis — SWOT, BCG, period review)
    openai_api_key: str = ""
    deepseek_api_key: str = ""

    # Yandex AI (YandexGPT reasoning + SpeechKit + Translate)
    yandex_api_key: str = ""
    yandex_folder_id: str = ""

    # AI Rating
    ai_rating_enabled: bool = True
    signal_expiry_hours: int = 168  # 7 days

    # YooKassa (primary payment system for RU)
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""

    # CryptoCloud (crypto payments — USDT/BTC/ETH for international)
    cryptocloud_api_key: str = ""
    cryptocloud_shop_id: str = ""

    # Prodamus (USD/EUR card payments for international)
    prodamus_secret_key: str = ""
    prodamus_payform_url: str = ""  # e.g. https://winextraflow.payform.ru

    # Marketplace
    marketplace_enabled: bool = True
    revenue_share_author_pct: float = 70.0
    revenue_share_platform_pct: float = 30.0

    # Execution
    execution_enabled: bool = True
    execution_min_confidence: float = 0.6
    execution_daily_loss_limit: float = 500.0  # USD, 0 = no limit

    # Registration
    registration_invite_only: bool = False  # True = referral code required; False = public signup

    # Signal video clips (9:16 stories) — rendered locally with matplotlib + ffmpeg
    signal_clips_enabled: bool = True

    # FRED (St. Louis Fed) — free key for the US economic-release calendar.
    # Without it the US block is omitted rather than filled with guesses.
    # Get one at https://fred.stlouisfed.org/docs/api/api_key.html
    fred_api_key: str = ""

    # MT5 bridge shared secret. Required to bind anything but 127.0.0.1: every
    # `analyze` command spends the OpenRouter key, so an open port is an open wallet.
    # Put the same value in the EA's inputs. Generate: python -c "import secrets;
    # print(secrets.token_urlsafe(32))"
    mt5_bridge_token: str = ""

    # Paid subscriptions. Off until the platform has a measured record of
    # profitable signals — see api/payments.py:require_paid_subscriptions_enabled.
    # Do not flip this on without a run of scripts/wef_validation.py behind it.
    paid_subscriptions_enabled: bool = False

    # Free channel: only tease signals BELOW this WEF score.
    # Strong signals (WEF >= threshold) stay VIP-exclusive — not even a teaser.
    free_teaser_max_wef: int = 70
    # ...and additionally the top (100 - N)% of recent scores. The absolute cut-off
    # alone caught ~6% of signals, because the score's real range is only ~43-71.
    free_teaser_percentile: int = 75

    # Results of signals at or above this score are published to the main channel
    # (owner's rule). The setup stays VIP-only; only the outcome is shown. Filtering
    # by rating is safe because the rating is fixed before the outcome is known —
    # filtering by outcome would be cherry-picking.
    free_result_min_wef: int = 60

    # Where the watchdog sends operational reports (your own chat id, not a channel).
    # Get it by messaging @userinfobot. Empty = report only to the log.
    admin_telegram_chat_id: str = ""

    # LLM (OpenRouter) — fallback parser for freeform/RU signals + MT5 bridge.
    # Must be declared here: code reading os.environ alone never sees .env values.
    openrouter_api_key: str = ""
    llm_model: str = "openai/gpt-oss-20b:free"

    # Referral
    referral_reward_type: str = "premium_days"
    referral_level1_reward: int = 7   # days of Premium for direct referral
    referral_level2_reward: int = 3   # days of Premium for indirect referral
    referral_max_levels: int = 2
    referral_base_url: str = "https://winextraflow.pages.dev/register"

    # Security
    allowed_origins: str = "http://localhost:3000"  # comma-separated in production
    max_token_expire_minutes: int = 1440  # 24h hard cap

    # GoClaw AI Agent Gateway (optional — enables multi-agent Telegram routing)
    # When set, broadcast_signal() tries GoClaw first and falls back to direct Bot API.
    # Leave empty to use direct Bot API only.
    goclaw_url: str = ""    # e.g. https://goclaw.internal/
    goclaw_token: str = ""  # Bearer token issued by GoClaw admin

    # App
    app_env: str = "development"
    app_debug: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        # Railway Postgres plugin provides postgresql:// but asyncpg needs postgresql+asyncpg://
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("access_token_expire_minutes")
    @classmethod
    def cap_token_expiry(cls, v: int) -> int:
        return min(v, 1440)  # max 24 hours

    def _ensure_secret_key(self) -> str:
        """Return secret_key, generating one for dev if empty."""
        if self.secret_key:
            return self.secret_key
        if self.app_env == "development":
            generated = _secrets.token_urlsafe(48)
            _logger.warning(
                "SECRET_KEY not set — generated ephemeral key for development. "
                "Set SECRET_KEY env var for production!"
            )
            return generated
        raise ValueError(
            "SECRET_KEY environment variable is required in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    def _ensure_encryption_key(self) -> str:
        """Return encryption_key, generating one for dev if empty."""
        if self.encryption_key:
            return self.encryption_key
        if self.app_env == "development":
            generated = _secrets.token_urlsafe(32)
            _logger.warning(
                "ENCRYPTION_KEY not set — generated ephemeral key for development. "
                "Set ENCRYPTION_KEY env var for production!"
            )
            return generated
        raise ValueError(
            "ENCRYPTION_KEY environment variable is required in production."
        )


settings = Settings()
# Resolve lazy-init secrets at import time so errors surface early
settings.secret_key = settings._ensure_secret_key()
settings.encryption_key = settings._ensure_encryption_key()
