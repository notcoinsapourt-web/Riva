from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime configuration loaded only from environment variables."""

    bot_token: SecretStr
    admin_ids: tuple[int, ...] = Field(default_factory=tuple)
    database_url: str = "sqlite+aiosqlite:///./data/persian_shop.db"
    shop_name: str = "Persian Shop"
    support_username: str = ""
    default_language: str = "fa"
    timezone: str = "Asia/Tehran"
    log_level: str = "INFO"

    order_report_channel_id: str = ""
    order_report_button_emoji_id: str = ""
    order_report_reconcile_interval_seconds: int = 30
    order_report_reconcile_hours: int = 2

    # Isolated private-channel delivery test. It never creates orders or wallet
    # transactions and never changes ORDER_REPORT_CHANNEL_ID.
    report_test_campaign_enabled: bool = False
    report_test_campaign_channel_id: str = ""
    report_test_campaign_start: str = ""
    report_test_campaign_days: int = 14
    report_test_campaign_daily_count: int = 20
    report_test_campaign_min_price: int = 300_000
    report_test_campaign_seed: str = "report-test"
    report_test_campaign_poll_seconds: int = 20

    payments_enabled: bool = False
    payment_integration_confirmed: bool = False
    payment_callback_base_url: str = ""
    zarinpal_merchant_id: SecretStr | None = None
    idpay_api_key: SecretStr | None = None
    idpay_sandbox: bool = True
    usdt_trc20_address: str = ""
    usdt_bep20_address: str = ""

    health_server_enabled: bool = True
    port: int = 10000
    rate_limit_requests: int = 12
    rate_limit_window_seconds: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> object:
        if value is None or value == "":
            return ()
        if isinstance(value, str):
            return tuple(int(item.strip()) for item in value.split(",") if item.strip())
        if isinstance(value, int):
            return (value,)
        return value

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://") and "+asyncpg" not in value:
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def payments_live(self) -> bool:
        """Two explicit switches prevent accidentally activating real payments."""

        return self.payments_enabled and self.payment_integration_confirmed

    @staticmethod
    def _chat_target(value: str) -> str | int | None:
        """Return a Bot API compatible target without guessing private chat IDs."""

        target = value.strip()
        if not target:
            return None
        if target.lstrip("-").isdigit():
            return int(target)
        if target.startswith("https://t.me/"):
            target = target.removeprefix("https://t.me/").strip("/")
        if target.startswith("t.me/"):
            target = target.removeprefix("t.me/").strip("/")
        # Private +invite links are intentionally not converted: the Bot API
        # cannot address a private channel by invite hash. The channel is bound
        # from a Telegram update after the bot is made an administrator.
        if target.startswith("+") or target.startswith("joinchat/"):
            return None
        return target if target.startswith("@") else f"@{target}"

    @property
    def order_report_target(self) -> str | int | None:
        return self._chat_target(self.order_report_channel_id)

    @property
    def report_test_campaign_target(self) -> str | int | None:
        return self._chat_target(self.report_test_campaign_channel_id)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()  # type: ignore[call-arg]
