import math

import pytest

from errors import (
    InvalidFiniteNumericValueError,
    InvalidOrderActionError,
    InvalidOrderTypeError,
    InvalidPositiveQuantityError,
    UnsupportedExchangeError,
)
from webhook import (
    Exchange,
    OrderAction,
    OrderType,
    WebhookPayload,
)


def build_payload():
    return {
        "strategyName": "TestStrategy",
        "passphrase": "test-secret",
        "ticker": "BTCUSDT",
        "bar": {"time": "2023-01-01T00:00:00Z", "close": 50000},
        "strategy": {
            "order_action": "buy",
            "order_contracts": "0.001",
            "order_price": 50000,
            "position_size": 0,
            "order_id": "123",
            "market_position": "long",
            "market_position_size": "0",
            "prev_market_position": "flat",
            "prev_market_position_size": 0,
        },
        "leverage": "10",
    }


def test_missing_order_type_defaults_to_paper_in_legacy_execution_dict():
    data = build_payload()

    payload = WebhookPayload.from_dict(data)

    assert payload.order_type == OrderType.PAPER
    execution_data = payload.to_execution_dict()
    assert execution_data["order_type"] == "PAPER"
    assert "passphrase" not in execution_data


def test_paper_allows_missing_exchange_and_arbitrary_exchange_metadata():
    data = build_payload()

    without_exchange = WebhookPayload.from_dict(data)
    assert without_exchange.exchange is None

    data["exchange"] = "paper_Metadata_Value"
    with_exchange = WebhookPayload.from_dict(data)
    assert with_exchange.exchange == "paper_Metadata_Value"
    assert with_exchange.to_execution_dict()["exchange"] == "paper_Metadata_Value"


@pytest.mark.parametrize(
    ("raw_exchange", "expected_exchange"),
    [
        ("binance", Exchange.BINANCE),
        ("bYbIt", Exchange.BYBIT),
        ("HYPERLIQUID", Exchange.HYPERLIQUID),
    ],
)
def test_real_supported_exchanges_are_case_insensitive(raw_exchange, expected_exchange):
    data = build_payload()
    data["order_type"] = "real"
    data["exchange"] = raw_exchange

    payload = WebhookPayload.from_dict(data)

    assert payload.order_type == OrderType.REAL
    assert payload.exchange == expected_exchange
    assert payload.to_execution_dict()["exchange"] == expected_exchange.value


def test_unsupported_real_exchange_is_rejected():
    data = build_payload()
    data["order_type"] = "REAL"
    data["exchange"] = "UNKNOWN"

    with pytest.raises(UnsupportedExchangeError):
        WebhookPayload.from_dict(data)


def test_malformed_order_type_is_rejected():
    data = build_payload()
    data["order_type"] = "PAPERX"

    with pytest.raises(InvalidOrderTypeError):
        WebhookPayload.from_dict(data)


def test_invalid_order_action_is_rejected():
    data = build_payload()
    data["strategy"]["order_action"] = "hold"

    with pytest.raises(InvalidOrderActionError):
        WebhookPayload.from_dict(data)


@pytest.mark.parametrize("raw_action", ["BUY", "buy", "bUy", "SELL", "sell", "sElL"])
def test_buy_sell_mixed_case_is_accepted(raw_action):
    data = build_payload()
    data["strategy"]["order_action"] = raw_action

    payload = WebhookPayload.from_dict(data)

    assert payload.order_action in {OrderAction.BUY, OrderAction.SELL}


@pytest.mark.parametrize(
    ("quantity", "expected_error"),
    [
        ("0", InvalidPositiveQuantityError),
        ("-0.001", InvalidPositiveQuantityError),
        (float("nan"), InvalidFiniteNumericValueError),
        (float("inf"), InvalidFiniteNumericValueError),
        (float("-inf"), InvalidFiniteNumericValueError),
    ],
)
def test_zero_negative_nan_and_inf_quantity_rejected(quantity, expected_error):
    data = build_payload()
    data["strategy"]["order_contracts"] = quantity

    with pytest.raises(expected_error):
        WebhookPayload.from_dict(data)


def test_scientific_notation_quantity_is_accepted():
    data = build_payload()
    data["strategy"]["order_contracts"] = "1e-3"

    payload = WebhookPayload.from_dict(data)

    assert math.isclose(payload.order_contracts_number, 0.001)


def test_integer_and_numeric_string_finite_fields_are_accepted_with_zero_positions():
    data = build_payload()
    data["bar"]["close"] = "50000"
    data["strategy"]["order_price"] = 50000
    data["strategy"]["position_size"] = 0
    data["strategy"]["market_position_size"] = "0"
    data["strategy"]["prev_market_position_size"] = 0
    data["leverage"] = "10"

    payload = WebhookPayload.from_dict(data)

    assert payload.position_size == 0
    assert payload.market_position_size == 0
    assert payload.prev_market_position_size == 0


@pytest.mark.parametrize(
    "path",
    [
        ("bar", "close"),
        ("strategy", "order_contracts"),
        ("strategy", "order_price"),
        ("strategy", "position_size"),
        ("strategy", "market_position_size"),
        ("strategy", "prev_market_position_size"),
        ("leverage",),
    ],
)
@pytest.mark.parametrize("value", ["not-a-number", float("inf")])
def test_malformed_and_non_finite_numeric_fields_are_rejected(path, value):
    data = build_payload()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(Exception):
        WebhookPayload.from_dict(data)


def test_exact_legacy_execution_dict_shape_is_preserved():
    data = build_payload()
    data["order_type"] = "PAPER"
    data["exchange"] = "paper_Metadata_Value"

    execution_data = WebhookPayload.from_dict(data).to_execution_dict()

    expected = dict(data)
    expected.pop("passphrase")
    assert execution_data == expected
