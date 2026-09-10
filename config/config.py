from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsValidationError(ValueError):
    def __init__(self, missing):
        self.missing = tuple(missing)
        super().__init__(f"Missing required settings: {', '.join(self.missing)}")


class AppSettings(BaseSettings):
    MONGO_URI: str | None = None
    WHITELISTED_IPS: str | None = None
    WEBHOOK_SECRET: str | None = None
    API_KEY: str | None = None
    API_SECRET: str | None = None
    HYPERLIQUID_WALLET_ADDRESS: str | None = None
    HYPERLIQUID_PRIVATE_KEY: str | None = None
    HYPERLIQUID_SLIPPAGE: float | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_ignore_empty=True,
    )

    def validate_required(self, *fields):
        missing = tuple(
            field for field in fields
            if not getattr(self, field) or not str(getattr(self, field)).strip()
        )
        if missing:
            raise SettingsValidationError(missing)
