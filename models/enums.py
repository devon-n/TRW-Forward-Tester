from enum import StrEnum


class OrderType(StrEnum):
    PAPER = "PAPER"
    REAL = "REAL"


class Exchange(StrEnum):
    BINANCE = "BINANCE"
    BYBIT = "BYBIT"
    HYPERLIQUID = "HYPERLIQUID"


class OrderAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
