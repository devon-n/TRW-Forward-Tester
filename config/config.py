from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvNames:
    MONGO_URI = "MONGO_URI"
    WHITELISTED_IPS = "WHITELISTED_IPS"
    WEBHOOK_SECRET = "WEBHOOK_SECRET"
    API_KEY = "API_KEY"
    API_SECRET = "API_SECRET"
    HYPERLIQUID_WALLET_ADDRESS = "HYPERLIQUID_WALLET_ADDRESS"
    HYPERLIQUID_PRIVATE_KEY = "HYPERLIQUID_PRIVATE_KEY"
    HYPERLIQUID_SLIPPAGE = "HYPERLIQUID_SLIPPAGE"


SETTINGS_CONFIG = SettingsConfigDict(
    env_file=".env",
    extra="ignore",
    env_ignore_empty=True,
)


def missing_field_names(error: ValidationError):
    return tuple(str(detail["loc"][0]) for detail in error.errors())


class DatabaseSettings(BaseSettings):
    MONGO_URI: str = Field(validation_alias=EnvNames.MONGO_URI)

    model_config = SETTINGS_CONFIG


class ApiCredentialSettings(BaseSettings):
    API_KEY: str = Field(validation_alias=EnvNames.API_KEY)
    API_SECRET: str = Field(validation_alias=EnvNames.API_SECRET)

    model_config = SETTINGS_CONFIG


class HyperliquidPublicSettings(BaseSettings):
    HYPERLIQUID_WALLET_ADDRESS: str = Field(
        validation_alias=EnvNames.HYPERLIQUID_WALLET_ADDRESS
    )

    model_config = SETTINGS_CONFIG


class HyperliquidRealSettings(BaseSettings):
    HYPERLIQUID_WALLET_ADDRESS: str = Field(
        validation_alias=EnvNames.HYPERLIQUID_WALLET_ADDRESS
    )
    HYPERLIQUID_PRIVATE_KEY: str = Field(
        validation_alias=EnvNames.HYPERLIQUID_PRIVATE_KEY
    )

    model_config = SETTINGS_CONFIG


class AppSettings(BaseSettings):
    MONGO_URI: str | None = Field(default=None, validation_alias=EnvNames.MONGO_URI)
    WHITELISTED_IPS: str | None = Field(default=None, validation_alias=EnvNames.WHITELISTED_IPS)
    WEBHOOK_SECRET: str | None = Field(default=None, validation_alias=EnvNames.WEBHOOK_SECRET)
    HYPERLIQUID_SLIPPAGE: float | None = Field(
        default=None,
        validation_alias=EnvNames.HYPERLIQUID_SLIPPAGE,
    )

    model_config = SETTINGS_CONFIG

    @property
    def database(self):
        return DatabaseSettings()

    @property
    def binance(self):
        return ApiCredentialSettings()

    @property
    def bybit(self):
        return ApiCredentialSettings()

    @property
    def hyperliquid_public(self):
        return HyperliquidPublicSettings()

    @property
    def hyperliquid_real(self):
        return HyperliquidRealSettings()

    def validate_startup(self):
        self.database
        if not self.WHITELISTED_IPS or not self.WHITELISTED_IPS.strip():
            raise ValueError(f"Missing required settings: {EnvNames.WHITELISTED_IPS}")
