import os


class Config:
    """Dynamic access to environment-backed application configuration."""

    @staticmethod
    def get_optional(name, default=None):
        return os.getenv(name, default)

    @classmethod
    def require(cls, *names):
        values = {}
        missing = []
        for name in names:
            value = cls.get_optional(name)
            if value is None or not str(value).strip():
                missing.append(name)
            else:
                values[name] = value
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )
        return values[names[0]] if len(names) == 1 else tuple(values[name] for name in names)

    @classmethod
    def validate_required(cls, *names):
        return cls.require(*names)

    @classmethod
    def validate_app_startup(cls):
        return cls.validate_required("MONGO_URI", "WHITELISTED_IPS")

    @classmethod
    def validate_dashboard_startup(cls):
        return cls.validate_required("MONGO_URI")

    @classmethod
    def validate_binance_real(cls):
        return cls.validate_required("API_KEY", "API_SECRET")

    @classmethod
    def validate_bybit_real(cls):
        return cls.validate_required("API_KEY", "API_SECRET")

    @classmethod
    def validate_hyperliquid_public(cls):
        return cls.validate_required("HYPERLIQUID_WALLET_ADDRESS")

    @classmethod
    def validate_hyperliquid_real(cls):
        return cls.validate_required("HYPERLIQUID_WALLET_ADDRESS", "HYPERLIQUID_PRIVATE_KEY")
