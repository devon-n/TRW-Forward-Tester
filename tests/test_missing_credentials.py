import os
from unittest.mock import patch

import pytest

from exchanges.binance import place_order_binance
from exchanges.bybit import place_order_bybit
from exchanges.hyperliquid import create_hyperliquid_exchange
from utils.errors import MissingCredentialError, TRWError


def test_missing_credential_error_has_structured_safe_payload():
    failure = MissingCredentialError("Binance REAL", ("API_KEY", "API_SECRET"))

    assert isinstance(failure, TRWError)
    assert failure.to_dict() == {
        "code": "missing_credential",
        "stage": "configuration",
        "message": "Missing required Binance REAL credentials: API_KEY, API_SECRET",
    }
    assert "secret-value" not in str(failure.to_dict())


@patch.dict(os.environ, {}, clear=True)
@patch("exchanges.binance.UMFutures")
def test_binance_missing_credentials_are_translated_before_client_creation(mock_client):
    with pytest.raises(MissingCredentialError) as exc_info:
        place_order_binance("BTCUSDT", "1", {})

    assert "API_KEY" in str(exc_info.value)
    assert "API_SECRET" in str(exc_info.value)
    mock_client.assert_not_called()


@patch.dict(os.environ, {"API_KEY": "key"}, clear=True)
@patch("exchanges.bybit.HTTP")
def test_bybit_missing_credentials_are_translated_before_client_creation(mock_http):
    with pytest.raises(MissingCredentialError) as exc_info:
        place_order_bybit("BTCUSDT", "1", {})

    assert "API_SECRET" in str(exc_info.value)
    assert "key" not in str(exc_info.value)
    mock_http.assert_not_called()


@patch.dict(os.environ, {}, clear=True)
@patch("exchanges.hyperliquid.ccxt.hyperliquid")
def test_hyperliquid_public_requires_wallet_only(mock_hyperliquid):
    with pytest.raises(MissingCredentialError) as exc_info:
        create_hyperliquid_exchange(require_private_key=False)

    assert "HYPERLIQUID_WALLET_ADDRESS" in str(exc_info.value)
    assert "HYPERLIQUID_PRIVATE_KEY" not in str(exc_info.value)
    mock_hyperliquid.assert_not_called()


@patch.dict(os.environ, {"HYPERLIQUID_WALLET_ADDRESS": "wallet"}, clear=True)
@patch("exchanges.hyperliquid.ccxt.hyperliquid")
def test_hyperliquid_signed_requires_private_key(mock_hyperliquid):
    with pytest.raises(MissingCredentialError) as exc_info:
        create_hyperliquid_exchange()

    assert "HYPERLIQUID_PRIVATE_KEY" in str(exc_info.value)
    assert "wallet" not in str(exc_info.value)
    mock_hyperliquid.assert_not_called()


@patch.dict(os.environ, {"HYPERLIQUID_WALLET_ADDRESS": "wallet"}, clear=True)
@patch("exchanges.hyperliquid.ccxt.hyperliquid")
def test_hyperliquid_public_does_not_require_private_key(mock_hyperliquid):
    create_hyperliquid_exchange(require_private_key=False)

    mock_hyperliquid.assert_called_once_with({"walletAddress": "wallet"})
