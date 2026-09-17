import os
from unittest.mock import MagicMock, patch

import pytest

from config.config import EnvNames
from exchanges.binance import place_order_binance
from exchanges.bybit import place_order_bybit
from exchanges.hyperliquid import create_hyperliquid_exchange
from utils.errors import MissingCredentialError, TRWError


def test_missing_credential_error_has_structured_safe_payload():
    failure = MissingCredentialError((EnvNames.API_KEY, EnvNames.API_SECRET))

    assert isinstance(failure, TRWError)
    assert failure.to_dict() == {
        "code": "missing_credential",
        "stage": "configuration",
        "message": "Missing required credentials: API_KEY, API_SECRET",
    }
    assert "secret-value" not in str(failure.to_dict())


@pytest.mark.parametrize(
    ("place_order", "context", "environment", "client_path"),
    [
        (place_order_binance, EnvNames.API_KEY, {}, "exchanges.binance.UMFutures"),
        (place_order_bybit, EnvNames.API_SECRET, {EnvNames.API_KEY: "key"}, "exchanges.bybit.HTTP"),
    ],
)
def test_binance_and_bybit_missing_credentials_are_local(place_order, context, environment, client_path):
    with patch.dict(os.environ, environment, clear=True), patch(client_path) as mock_client:
        with pytest.raises(MissingCredentialError, match=context):
            place_order("BTCUSDT", "1", {})

    mock_client.assert_not_called()


def test_hyperliquid_signed_requires_private_key():
    with patch.dict(os.environ, {EnvNames.HYPERLIQUID_WALLET_ADDRESS: "wallet"}, clear=True), patch("exchanges.hyperliquid.ccxt.hyperliquid") as mock_exchange:
        with pytest.raises(MissingCredentialError, match=EnvNames.HYPERLIQUID_PRIVATE_KEY):
            create_hyperliquid_exchange()

    mock_exchange.assert_not_called()


def test_hyperliquid_public_requires_wallet_but_not_private_key():
    with patch.dict(os.environ, {}, clear=True), patch("exchanges.hyperliquid.ccxt.hyperliquid", return_value=MagicMock()) as mock_exchange:
        with pytest.raises(MissingCredentialError, match=EnvNames.HYPERLIQUID_WALLET_ADDRESS):
            create_hyperliquid_exchange(require_private_key=False)

    mock_exchange.assert_not_called()


def test_hyperliquid_public_accepts_wallet_without_private_key():
    with patch.dict(os.environ, {EnvNames.HYPERLIQUID_WALLET_ADDRESS: "wallet"}, clear=True), patch("exchanges.hyperliquid.ccxt.hyperliquid", return_value=MagicMock()) as mock_exchange:
        create_hyperliquid_exchange(require_private_key=False)

    mock_exchange.assert_called_once_with({"walletAddress": "wallet"})


def test_exchange_credentials_are_read_at_operation_boundary():
    with patch.dict(
        'os.environ',
        {EnvNames.API_KEY: 'key-after-import', EnvNames.API_SECRET: 'secret-after-import'},
        clear=True,
    ), patch('exchanges.binance.UMFutures') as mock_binance:
        place_order_binance('BTCUSDT', '1', {'strategy': {'order_action': 'buy'}})
    mock_binance.assert_called_once_with('key-after-import', 'secret-after-import')

    with patch.dict(
        'os.environ',
        {EnvNames.API_KEY: 'key-after-import', EnvNames.API_SECRET: 'secret-after-import'},
        clear=True,
    ), patch('exchanges.bybit.HTTP') as mock_bybit:
        place_order_bybit('BTCUSDT', '1', {'strategy': {'order_action': 'buy'}})
    mock_bybit.assert_called_once_with(
        testnet=False,
        api_key='key-after-import',
        api_secret='secret-after-import',
    )

    with patch.dict(
        'os.environ',
        {EnvNames.HYPERLIQUID_WALLET_ADDRESS: 'wallet-after-import'},
        clear=True,
    ), patch('exchanges.hyperliquid.ccxt.hyperliquid') as mock_hyperliquid:
        create_hyperliquid_exchange(require_private_key=False)
    mock_hyperliquid.assert_called_once_with({'walletAddress': 'wallet-after-import'})
