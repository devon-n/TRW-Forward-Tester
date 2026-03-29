import os
from unittest.mock import MagicMock, patch

import pytest

from exchanges.hyperliquid import (
    cancel_entry_and_children_hyperliquid,
    create_hyperliquid_exchange,
    extract_order_params,
    fetch_fills_by_time_hyperliquid,
    fetch_historical_orders_hyperliquid,
)


@patch.dict(os.environ, {'HYPERLIQUID_SLIPPAGE': ''}, clear=False)
def test_extract_order_params_uses_strategy_values_when_top_level_values_are_blank():
    data = {
        'reduceOnly': '',
        'clientOrderId': '',
        'strategy': {
            'reduceOnly': True,
            'clientOrderId': 'strategy-client-order-id',
            'triggerPrice': '64000',
        },
    }

    params = extract_order_params(data)

    assert params == {
        'reduceOnly': True,
        'clientOrderId': 'strategy-client-order-id',
        'triggerPrice': '64000',
    }


@patch('exchanges.hyperliquid.create_hyperliquid_exchange')
def test_cancel_entry_and_children_hyperliquid_marks_partial_child_failures(mock_create_exchange):
    mock_exchange = MagicMock()
    mock_exchange.cancel_orders.side_effect = [
        [{'status': 'canceled'}],
        [{'status': 'canceled'}, {'status': 'open'}],
    ]
    mock_create_exchange.return_value = mock_exchange

    result = cancel_entry_and_children_hyperliquid('entry-order', ['tp-order', 'sl-order'], 'BTCUSDT')

    assert result == {
        'entry': [{'status': 'canceled'}],
        'children': [{'status': 'canceled'}, {'status': 'open'}],
        'children_cancelled': False,
    }


@patch.dict(os.environ, {'HYPERLIQUID_WALLET_ADDRESS': '0xabc'}, clear=True)
@patch('exchanges.hyperliquid.ccxt.hyperliquid')
def test_create_hyperliquid_exchange_allows_public_exchange_without_private_key(mock_hyperliquid):
    mock_exchange = MagicMock()
    mock_hyperliquid.return_value = mock_exchange

    result = create_hyperliquid_exchange(require_private_key=False)

    mock_hyperliquid.assert_called_once_with({'walletAddress': '0xabc'})
    assert result is mock_exchange


@patch.dict(os.environ, {'HYPERLIQUID_WALLET_ADDRESS': '0xabc'}, clear=True)
@patch('exchanges.hyperliquid.create_hyperliquid_exchange')
def test_fetch_historical_orders_hyperliquid_uses_public_exchange(mock_create_exchange):
    mock_exchange = MagicMock()
    mock_create_exchange.return_value = mock_exchange

    fetch_historical_orders_hyperliquid()

    mock_create_exchange.assert_called_once_with(require_private_key=False)
    mock_exchange.public_post_info.assert_called_once_with({
        'type': 'historicalOrders',
        'user': '0xabc',
    })


@patch.dict(os.environ, {'HYPERLIQUID_WALLET_ADDRESS': '0xabc'}, clear=True)
@patch('exchanges.hyperliquid.create_hyperliquid_exchange')
def test_fetch_fills_by_time_hyperliquid_uses_public_exchange(mock_create_exchange):
    mock_exchange = MagicMock()
    mock_create_exchange.return_value = mock_exchange

    fetch_fills_by_time_hyperliquid(100, 200)

    mock_create_exchange.assert_called_once_with(require_private_key=False)
    mock_exchange.public_post_info.assert_called_once_with({
        'type': 'userFillsByTime',
        'user': '0xabc',
        'startTime': 100,
        'endTime': 200,
    })


@patch.dict(os.environ, {'HYPERLIQUID_WALLET_ADDRESS': '0xabc'}, clear=True)
def test_create_hyperliquid_exchange_requires_private_key_by_default():
    with pytest.raises(ValueError, match='Missing Hyperliquid private key'):
        create_hyperliquid_exchange()
