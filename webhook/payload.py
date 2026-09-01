import copy
import math
from dataclasses import dataclass
from typing import Any

from errors import (
    InvalidFieldTypeError,
    InvalidFiniteNumericTypeError,
    InvalidFiniteNumericValueError,
    InvalidOrderActionError,
    InvalidOrderTypeError,
    InvalidPositiveQuantityError,
    MissingRequiredFieldError,
    UnsupportedExchangeError,
)
from webhook.enums import (
    Exchange,
    OrderAction,
    OrderType,
)


REQUIRED_WEBHOOK_FIELDS = (
    ("strategyName",),
    ("ticker",),
    ("bar", "time"),
    ("bar", "close"),
    ("strategy", "order_action"),
    ("strategy", "order_contracts"),
    ("strategy", "order_price"),
    ("strategy", "position_size"),
    ("strategy", "order_id"),
    ("strategy", "market_position"),
    ("strategy", "market_position_size"),
    ("strategy", "prev_market_position"),
    ("strategy", "prev_market_position_size"),
    ("leverage",),
)

FINITE_NUMERIC_WEBHOOK_FIELDS = (
    (("bar", "close"), "bar.close"),
    (("strategy", "order_contracts"), "strategy.order_contracts"),
    (("strategy", "order_price"), "strategy.order_price"),
    (("strategy", "position_size"), "strategy.position_size"),
    (("strategy", "market_position_size"), "strategy.market_position_size"),
    (("strategy", "prev_market_position_size"), "strategy.prev_market_position_size"),
    (("leverage",), "leverage"),
)


@dataclass(frozen=True)
class WebhookPayload:
    raw: dict[str, Any]
    strategy_name: Any
    ticker: Any
    bar_time: Any
    bar_close: float
    order_action: OrderAction
    order_contracts: Any
    order_contracts_number: float
    order_price: float
    position_size: float
    order_id: Any
    market_position: Any
    market_position_size: float
    prev_market_position: Any
    prev_market_position_size: float
    leverage: float
    order_type: OrderType
    exchange: Exchange | Any | None

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise InvalidFieldTypeError("payload", "an object")

        cls._validate_required_fields(data)
        numeric_values = cls._parse_numeric_fields(data)
        order_contracts_number = numeric_values["strategy.order_contracts"]
        if order_contracts_number <= 0:
            raise InvalidPositiveQuantityError()

        order_type = cls._parse_order_type(data.get("order_type"))
        order_action = cls._parse_order_action(data["strategy"]["order_action"])
        exchange = cls._parse_exchange(data.get("exchange"), order_type)

        return cls(
            raw=copy.deepcopy(data),
            strategy_name=data["strategyName"],
            ticker=data["ticker"],
            bar_time=data["bar"]["time"],
            bar_close=numeric_values["bar.close"],
            order_action=order_action,
            order_contracts=data["strategy"]["order_contracts"],
            order_contracts_number=order_contracts_number,
            order_price=numeric_values["strategy.order_price"],
            position_size=numeric_values["strategy.position_size"],
            order_id=data["strategy"]["order_id"],
            market_position=data["strategy"]["market_position"],
            market_position_size=numeric_values["strategy.market_position_size"],
            prev_market_position=data["strategy"]["prev_market_position"],
            prev_market_position_size=numeric_values["strategy.prev_market_position_size"],
            leverage=numeric_values["leverage"],
            order_type=order_type,
            exchange=exchange,
        )

    def to_execution_dict(self):
        data = copy.deepcopy(self.raw)
        data.pop("passphrase", None)
        data["order_type"] = self.order_type.value
        if self.order_type == OrderType.REAL and isinstance(self.exchange, Exchange):
            data["exchange"] = self.exchange.value
        return data

    @staticmethod
    def _validate_required_fields(data):
        for path in REQUIRED_WEBHOOK_FIELDS:
            current = data
            traversed = []
            for key in path:
                traversed.append(key)
                if not isinstance(current, dict):
                    field = ".".join(traversed[:-1])
                    raise InvalidFieldTypeError(field, "an object")
                if key not in current:
                    raise MissingRequiredFieldError(".".join(path))
                current = current[key]

    @classmethod
    def _parse_numeric_fields(cls, data):
        numeric_values = {}
        for path, field in FINITE_NUMERIC_WEBHOOK_FIELDS:
            current = data
            for key in path:
                current = current[key]
            numeric_values[field] = cls.parse_finite_number(current, field)
        return numeric_values

    @staticmethod
    def parse_finite_number(value, field):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise InvalidFiniteNumericTypeError(field)
        if not math.isfinite(number):
            raise InvalidFiniteNumericValueError(field)
        return number

    @staticmethod
    def _parse_order_type(value):
        normalized = str(value if value is not None else OrderType.PAPER.value).upper()
        try:
            return OrderType(normalized)
        except ValueError:
            raise InvalidOrderTypeError() from None

    @staticmethod
    def _parse_order_action(value):
        normalized = str(value).upper()
        try:
            return OrderAction(normalized)
        except ValueError:
            raise InvalidOrderActionError() from None

    @staticmethod
    def _parse_exchange(value, order_type):
        if order_type == OrderType.PAPER:
            return value

        normalized = str(value or "").upper()
        try:
            return Exchange(normalized)
        except ValueError:
            raise UnsupportedExchangeError() from None
