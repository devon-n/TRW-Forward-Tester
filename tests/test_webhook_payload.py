import math

import pytest

from errors import (
    InvalidFiniteNumericValueError,
    InvalidOrderActionError,
    InvalidOrderTypeError,
    InvalidPositiveQuantityError,
)
from tests.test_app import build_webhook_payload
from trw.types.enums import (
    Exchange,
    OrderAction,
    OrderType,
)
from trw.types.webhook import WebhookPayload


def build_payload():
    data = build_webhook_payload()
    data.pop("passphrase")
    data.pop("order_type")
    data["strategy"]["position_size"] = 0
    data["strategy"]["market_position_size"] = "0"
    data["leverage"] = "10"
    return data


def test_missing_order_type_defaults_to_paper_in_legacy_execution_dict():
    payload = WebhookPayload.from_dict(build_payload())

    assert payload.order_type == OrderType.PAPER
    execution_data = payload.to_execution_dict()
    assert execution_data["order_type"] == "PAPER"
    assert "passphrase" not in execution_data


def test_paper_allows_arbitrary_exchange_metadata():
    data = build_payload()
    data["exchange"] = "paper_Metadata_Value"

    payload = WebhookPayload.from_dict(data)

    assert payload.exchange == "paper_Metadata_Value"
    assert payload.to_execution_dict()["exchange"] == "paper_Metadata_Value"


@pytest.mark.parametrize(
    ("raw_exchange", "expected_exchange"),
    [("bYbIt", Exchange.BYBIT)],
)
def test_real_supported_exchanges_are_case_insensitive(raw_exchange, expected_exchange):
    data = build_payload()
    data["order_type"] = "real"
    data["exchange"] = raw_exchange

    payload = WebhookPayload.from_dict(data)

    assert payload.order_type == OrderType.REAL
    assert payload.exchange == expected_exchange
    assert payload.to_execution_dict()["exchange"] == expected_exchange.value


@pytest.mark.parametrize(
    ("mutate", "expected_error"),
    [
        (lambda data: data.update({"order_type": "PAPERX"}), InvalidOrderTypeError),
        (lambda data: data["strategy"].update({"order_action": "hold"}), InvalidOrderActionError),
        (lambda data: data["strategy"].update({"order_contracts": "0"}), InvalidPositiveQuantityError),
        (lambda data: data["strategy"].update({"order_contracts": "-0.001"}), InvalidPositiveQuantityError),
        (lambda data: data["strategy"].update({"order_contracts": float("nan")}), InvalidFiniteNumericValueError),
    ],
)
def test_invalid_payload_values_raise_structured_errors(mutate, expected_error):
    data = build_payload()
    mutate(data)

    with pytest.raises(expected_error):
        WebhookPayload.from_dict(data)


@pytest.mark.parametrize("raw_action", ["buy", "sElL"])
def test_order_action_is_case_insensitive(raw_action):
    data = build_payload()
    data["strategy"]["order_action"] = raw_action

    payload = WebhookPayload.from_dict(data)

    assert payload.order_action in {OrderAction.BUY, OrderAction.SELL}


def test_scientific_notation_quantity_and_zero_positions_are_accepted():
    data = build_payload()
    data["strategy"]["order_contracts"] = "1e-3"

    payload = WebhookPayload.from_dict(data)

    assert math.isclose(payload.order_contracts_number, 0.001)
    assert payload.position_size == 0
    assert payload.market_position_size == 0
    assert payload.prev_market_position_size == 0


def test_exact_legacy_execution_dict_shape_is_preserved():
    data = build_payload()
    data["order_type"] = "PAPER"
    data["exchange"] = "paper_Metadata_Value"

    execution_data = WebhookPayload.from_dict(data).to_execution_dict()

    assert execution_data == data
