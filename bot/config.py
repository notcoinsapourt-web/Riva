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


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()  # type: ignore[call-arg]
