from unittest.mock import MagicMock, patch

import pytest

from config.config import AppSettings
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


@pytest.mark.parametrize(
    ("place_order", "context", "settings", "client_path"),
    [
        (place_order_binance, "Binance REAL", AppSettings(), "exchanges.binance.UMFutures"),
        (place_order_bybit, "Bybit REAL", AppSettings(API_KEY="key"), "exchanges.bybit.HTTP"),
    ],
)
def test_binance_and_bybit_missing_credentials_are_local(place_order, context, settings, client_path):
    with patch(f"{place_order.__module__}.AppSettings", return_value=settings), patch(client_path) as mock_client:
        with pytest.raises(MissingCredentialError, match=context):
            place_order("BTCUSDT", "1", {})

    mock_client.assert_not_called()


def test_hyperliquid_signed_requires_private_key():
    settings = AppSettings(HYPERLIQUID_WALLET_ADDRESS="wallet")
    with patch("exchanges.hyperliquid.AppSettings", return_value=settings), patch("exchanges.hyperliquid.ccxt.hyperliquid") as mock_exchange:
        with pytest.raises(MissingCredentialError, match="HYPERLIQUID_PRIVATE_KEY"):
            create_hyperliquid_exchange()

    mock_exchange.assert_not_called()


def test_hyperliquid_public_requires_wallet_but_not_private_key():
    settings = AppSettings()
    with patch("exchanges.hyperliquid.AppSettings", return_value=settings), patch("exchanges.hyperliquid.ccxt.hyperliquid", return_value=MagicMock()) as mock_exchange:
        with pytest.raises(MissingCredentialError, match="HYPERLIQUID_WALLET_ADDRESS"):
            create_hyperliquid_exchange(require_private_key=False)

    mock_exchange.assert_not_called()


def test_hyperliquid_public_accepts_wallet_without_private_key():
    settings = AppSettings(HYPERLIQUID_WALLET_ADDRESS="wallet")
    with patch("exchanges.hyperliquid.AppSettings", return_value=settings), patch("exchanges.hyperliquid.ccxt.hyperliquid", return_value=MagicMock()) as mock_exchange:
        create_hyperliquid_exchange(require_private_key=False)

    mock_exchange.assert_called_once_with({"walletAddress": "wallet"})


def test_exchange_credentials_are_read_at_operation_boundary():
    with patch.dict(
        'os.environ',
        {'API_KEY': 'key-after-import', 'API_SECRET': 'secret-after-import'},
        clear=True,
    ), patch('exchanges.binance.UMFutures') as mock_binance:
        place_order_binance('BTCUSDT', '1', {'strategy': {'order_action': 'buy'}})
    mock_binance.assert_called_once_with('key-after-import', 'secret-after-import')

    with patch.dict(
        'os.environ',
        {'API_KEY': 'key-after-import', 'API_SECRET': 'secret-after-import'},
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
        {'HYPERLIQUID_WALLET_ADDRESS': 'wallet-after-import'},
        clear=True,
    ), patch('exchanges.hyperliquid.ccxt.hyperliquid') as mock_hyperliquid:
        create_hyperliquid_exchange(require_private_key=False)
    mock_hyperliquid.assert_called_once_with({'walletAddress': 'wallet-after-import'})
