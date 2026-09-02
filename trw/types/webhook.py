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
from trw.types.enums import (
    Exchange,
    OrderAction,
    OrderType,
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

        strategy_name = cls._required(data, "strategyName")
        ticker = cls._required(data, "ticker")
        bar_time = cls._required(data, "bar", "time")
        bar_close = cls._parse_required_number(data, "bar", "close")
        order_action = cls._parse_order_action(cls._required(data, "strategy", "order_action"))
        order_contracts = cls._required(data, "strategy", "order_contracts")
        order_contracts_number = cls.parse_finite_number(order_contracts, "strategy.order_contracts")
        if order_contracts_number <= 0:
            raise InvalidPositiveQuantityError()

        order_type = cls._parse_order_type(data.get("order_type"))
        exchange = cls._parse_exchange(data.get("exchange"), order_type)

        return cls(
            raw=copy.deepcopy(data),
            strategy_name=strategy_name,
            ticker=ticker,
            bar_time=bar_time,
            bar_close=bar_close,
            order_action=order_action,
            order_contracts=order_contracts,
            order_contracts_number=order_contracts_number,
            order_price=cls._parse_required_number(data, "strategy", "order_price"),
            position_size=cls._parse_required_number(data, "strategy", "position_size"),
            order_id=cls._required(data, "strategy", "order_id"),
            market_position=cls._required(data, "strategy", "market_position"),
            market_position_size=cls._parse_required_number(data, "strategy", "market_position_size"),
            prev_market_position=cls._required(data, "strategy", "prev_market_position"),
            prev_market_position_size=cls._parse_required_number(data, "strategy", "prev_market_position_size"),
            leverage=cls._parse_required_number(data, "leverage"),
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

    @classmethod
    def _parse_required_number(cls, data, *path):
        field = ".".join(path)
        return cls.parse_finite_number(cls._required(data, *path), field)

    @staticmethod
    def _required(data, *path):
        current = data
        traversed = []
        for key in path:
            traversed.append(key)
            if not isinstance(current, dict):
                raise InvalidFieldTypeError(".".join(traversed[:-1]), "an object")
            if key not in current:
                raise MissingRequiredFieldError(".".join(path))
            current = current[key]
        return current

    @staticmethod
    def parse_finite_number(value, field):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise InvalidFiniteNumericTypeError(field) from None
        if not math.isfinite(number):
            raise InvalidFiniteNumericValueError(field)
        return number

    @staticmethod
    def _parse_order_type(value):
        normalized = str(value if value is not None else OrderType.PAPER.value).upper()
        try:
            return OrderType(normalized)
        except ValueError:
            raise InvalidOrderTypeError(OrderType) from None

    @staticmethod
    def _parse_order_action(value):
        normalized = str(value).upper()
        try:
            return OrderAction(normalized)
        except ValueError:
            raise InvalidOrderActionError(OrderAction) from None

    @staticmethod
    def _parse_exchange(value, order_type):
        if order_type == OrderType.PAPER:
            return value

        normalized = str(value or "").upper()
        try:
            return Exchange(normalized)
        except ValueError:
            raise UnsupportedExchangeError(Exchange) from None
