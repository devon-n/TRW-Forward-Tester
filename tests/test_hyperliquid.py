import os
from unittest.mock import MagicMock, patch

import pytest
import ccxt

from exchanges.hyperliquid import (
    _resolve_market_reference_price,
    cancel_entry_and_children_hyperliquid,
    create_hyperliquid_exchange,
    extract_order_params,
    fetch_fills_by_time_hyperliquid,
    fetch_historical_orders_hyperliquid,
    normalize_symbol_hyperliquid,
    place_order_hyperliquid,
    set_leverage_hyperliquid,
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


def test_normalize_symbol_hyperliquid_supports_usdt_and_usd_formats():
    assert normalize_symbol_hyperliquid('btcusdt') == 'BTC/USDC:USDC'
    assert normalize_symbol_hyperliquid('ETHUSD') == 'ETH/USDC:USDC'
    assert normalize_symbol_hyperliquid('SOLUSD.P') == 'SOL/USDC:USDC'


def test_normalize_symbol_hyperliquid_rejects_unknown_formats():
    with pytest.raises(ValueError, match='Unsupported Hyperliquid symbol format'):
        normalize_symbol_hyperliquid('BTC')


def test_resolve_market_reference_price_uses_strategy_price_when_present():
    exchange = MagicMock()
    data = {'strategy': {'order_price': '65000'}}

    reference_price = _resolve_market_reference_price(exchange, 'BTC/USDC:USDC', data)

    assert reference_price == 65000.0
    exchange.fetch_ticker.assert_not_called()


def test_resolve_market_reference_price_falls_back_to_ticker_values():
    exchange = MagicMock()
    exchange.fetch_ticker.return_value = {'last': None, 'close': 64000, 'bid': 63950}

    reference_price = _resolve_market_reference_price(exchange, 'BTC/USDC:USDC', {'strategy': {}})

    assert reference_price == 64000.0
    exchange.fetch_ticker.assert_called_once_with('BTC/USDC:USDC')


def test_resolve_market_reference_price_raises_when_ticker_has_no_reference_values():
    exchange = MagicMock()
    exchange.fetch_ticker.return_value = {'last': None, 'close': None, 'bid': None}

    with pytest.raises(ValueError, match='needs a reference price'):
        _resolve_market_reference_price(exchange, 'BTC/USDC:USDC', {'strategy': {}})


def test_set_leverage_hyperliquid_returns_true_on_success():
    exchange = MagicMock()

    result = set_leverage_hyperliquid(exchange, 'BTC/USDC:USDC', 5)

    assert result is True
    exchange.set_margin_mode.assert_called_once_with('isolated', 'BTC/USDC:USDC', {'leverage': 5})


def test_set_leverage_hyperliquid_returns_false_for_ccxt_errors():
    exchange = MagicMock()
    exchange.set_margin_mode.side_effect = ccxt.ExchangeError('leverage rejected')

    result = set_leverage_hyperliquid(exchange, 'BTC/USDC:USDC', 5)

    assert result is False
    exchange.set_margin_mode.assert_called_once_with('isolated', 'BTC/USDC:USDC', {'leverage': 5})


def test_set_leverage_hyperliquid_does_not_swallow_non_ccxt_errors():
    exchange = MagicMock()
    exchange.set_margin_mode.side_effect = RuntimeError('unexpected failure')

    with pytest.raises(RuntimeError, match='unexpected failure'):
        set_leverage_hyperliquid(exchange, 'BTC/USDC:USDC', 5)


@patch.dict(os.environ, {'HYPERLIQUID_SLIPPAGE': ''}, clear=False)
@patch('exchanges.hyperliquid.create_hyperliquid_exchange')
def test_place_order_hyperliquid_happy_path(mock_create_exchange):
    exchange = MagicMock()
    exchange.create_order.return_value = {'id': 'order-1', 'status': 'open'}
    mock_create_exchange.return_value = exchange

    data = {
        'leverage': 0,
        'strategy': {
            'order_action': 'BUY',
            'order_price': '65000',
        },
    }

    order_response = place_order_hyperliquid('BTCUSDT', '0.25', data)

    assert order_response == {'id': 'order-1', 'status': 'open'}
    exchange.create_order.assert_called_once_with(
        'BTC/USDC:USDC',
        'market',
        'buy',
        0.25,
        65000.0,
        {},
    )


@patch.dict(os.environ, {'HYPERLIQUID_SLIPPAGE': ''}, clear=False)
@patch('exchanges.hyperliquid.create_hyperliquid_exchange')
def test_place_order_hyperliquid_raises_clear_error_for_missing_order_action(mock_create_exchange):
    mock_create_exchange.return_value = MagicMock()
    data = {
        'leverage': 0,
        'strategy': {},
    }

    with pytest.raises(ValueError, match='strategy.order_action'):
        place_order_hyperliquid('BTCUSDT', '0.25', data)


@patch.dict(os.environ, {'HYPERLIQUID_SLIPPAGE': ''}, clear=False)
@patch('exchanges.hyperliquid.create_hyperliquid_exchange')
def test_place_order_hyperliquid_raises_when_leverage_setup_fails(mock_create_exchange):
    exchange = MagicMock()
    mock_create_exchange.return_value = exchange
    data = {
        'leverage': 3,
        'strategy': {
            'order_action': 'BUY',
            'order_price': '65000',
        },
    }

    with patch('exchanges.hyperliquid.set_leverage_hyperliquid', return_value=False) as mock_set_leverage:
        with pytest.raises(RuntimeError, match='Failed to set Hyperliquid leverage'):
            place_order_hyperliquid('BTCUSDT', '0.25', data)

    mock_set_leverage.assert_called_once_with(exchange, 'BTC/USDC:USDC', 3)
    exchange.create_order.assert_not_called()


@patch.dict(os.environ, {'HYPERLIQUID_SLIPPAGE': ''}, clear=False)
@patch('exchanges.hyperliquid.create_hyperliquid_exchange')
def test_place_order_hyperliquid_propagates_exchange_api_errors(mock_create_exchange):
    exchange = MagicMock()
    exchange.create_order.side_effect = ccxt.ExchangeError('order rejected')
    mock_create_exchange.return_value = exchange
    data = {
        'leverage': 0,
        'strategy': {
            'order_action': 'BUY',
            'order_price': '65000',
        },
    }

    with pytest.raises(ccxt.ExchangeError, match='order rejected'):
        place_order_hyperliquid('BTCUSDT', '0.25', data)
