from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_ignore_empty=True,
    )


class RuntimeSettings(BaseAppSettings):
    MONGO_URI: str | None = None


class DatabaseSettings(RuntimeSettings):
    MONGO_URI: str


class AppSettings(DatabaseSettings):
    WHITELISTED_IPS: str
    WEBHOOK_SECRET: str | None = None


class ExchangeSettings(BaseAppSettings):
    API_KEY: str | None = None
    API_SECRET: str | None = None
    HYPERLIQUID_WALLET_ADDRESS: str | None = None
    HYPERLIQUID_PRIVATE_KEY: str | None = None
    HYPERLIQUID_SLIPPAGE: float | None = None
