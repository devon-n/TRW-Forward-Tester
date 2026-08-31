import os
from unittest.mock import (
    MagicMock,
    patch,
)

import pytest

from logging_utils import sanitize_dict
from errors import TRWError


def build_webhook_payload(passphrase='test-secret'):
    return {
        'strategyName': 'TestStrategy',
        'passphrase': passphrase,
        'ticker': 'BTCUSDT',
        'bar': {'time': '2023-01-01T00:00:00Z', 'close': 50000},
        'strategy': {
            'order_action': 'buy',
            'order_contracts': '0.001',
            'order_price': 50000,
            'position_size': 0.001,
            'order_id': '123',
            'market_position': 'long',
            'market_position_size': 0.001,
            'prev_market_position': 'flat',
            'prev_market_position_size': 0
        },
        'leverage': 10,
        'order_type': 'PAPER'
    }


def test_welcome(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.data == b""

@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1,192.168.1.1', 'WEBHOOK_SECRET': 'test-secret'})
def test_webhook(client):
    with patch('app.execute_order') as mock_execute_order:
        mock_execute_order.return_value = True
        data = build_webhook_payload()

        response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response data: {response.data}"
        assert response.json == {"code": "success", "message": "Order executed"}
        expected_data = dict(data)
        expected_data.pop('passphrase')
        mock_execute_order.assert_called_once_with(expected_data)

@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1'})
def test_whitelist_ip_decorator():
    from app import (
        app,
        whitelist_ip,
    )

    @whitelist_ip
    def test_func():
        return "Access granted"

    with app.test_request_context(headers={'X-Forwarded-For': '127.0.0.1'}):
        result = test_func()
        assert result == "Access granted"

    with app.test_request_context(headers={'X-Forwarded-For': '1.1.1.1'}):
        with pytest.raises(Exception) as excinfo:
            test_func()
        assert "Access denied" in str(excinfo.value)


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_missing_passphrase(mock_execute_order, client):
    data = build_webhook_payload()
    data.pop('passphrase')

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 401
    assert response.json == {"status": "error", "message": "Invalid Passphrase"}


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_wrong_passphrase(mock_execute_order, client):
    response = client.post(
        '/webhook',
        json=build_webhook_payload(passphrase='wrong-secret'),
        headers={'X-Forwarded-For': '127.0.0.1'}
    )

    mock_execute_order.assert_not_called()
    assert response.status_code == 401
    assert response.json == {"status": "error", "message": "Invalid Passphrase"}


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_missing_required_json_field_returns_structured_validation_failure(mock_execute_order, client):
    data = build_webhook_payload()
    del data['strategy']['order_contracts']

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 400
    assert response.json == {
        "status": "error",
        "reason": "invalid payload",
        "failure": {
            "code": "missing_required_field",
            "stage": "validation",
            "message": "Missing required webhook field: strategy.order_contracts",
        },
    }


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_malformed_strategy_returns_structured_validation_failure(mock_execute_order, client):
    data = build_webhook_payload()
    data['strategy'] = 'not-an-object'

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 400
    assert response.json == {
        "status": "error",
        "reason": "invalid payload",
        "failure": {
            "code": "invalid_field_type",
            "stage": "validation",
            "message": "Webhook field must be an object: strategy",
        },
    }


@pytest.mark.parametrize(
    "quantity",
    ['0', '-0.001', float('nan'), float('inf'), float('-inf')],
)
@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_rejects_invalid_quantities(mock_execute_order, client, quantity):
    data = build_webhook_payload()
    data['strategy']['order_contracts'] = quantity

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 400
    assert response.json["status"] == "error"
    assert response.json["reason"] == "invalid payload"
    assert response.json["failure"]["code"] == "invalid_field_value"
    assert "strategy.order_contracts" in response.json["failure"]["message"]


@patch.object(TRWError, 'log', autospec=True)
@patch('app.record_trade')
def test_execute_order_rejects_quantity_that_rounds_to_zero(mock_record_trade, mock_log):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')
    data['ticker'] = 'KAVAUSDT'
    data['strategy']['order_contracts'] = '0.04'

    result = execute_order(data)

    assert result is False
    mock_record_trade.assert_not_called()
    mock_log.assert_called_once()
    assert mock_log.call_args[0][0].to_dict()["code"] == "invalid_field_value"


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_rejects_unsupported_order_type(mock_execute_order, client):
    data = build_webhook_payload()
    data['order_type'] = 'PAPERX'

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 400
    assert response.json["failure"] == {
        "code": "invalid_field_value",
        "stage": "validation",
        "message": "Webhook field has unsupported value; expected PAPER or REAL: order_type",
    }


@patch('app.record_trade')
def test_execute_order_accepts_oddly_cased_valid_order_type(mock_record_trade):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')
    data['order_type'] = 'pApEr'

    result = execute_order(data)

    assert result is True
    assert data['order_type'] == 'PAPER'
    mock_record_trade.assert_called_once_with(data, None)


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_accepts_paper_without_exchange(mock_execute_order, client):
    data = build_webhook_payload()

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    assert response.status_code == 200
    assert response.json == {"code": "success", "message": "Order executed"}
    expected_data = dict(data)
    expected_data.pop('passphrase')
    mock_execute_order.assert_called_once_with(expected_data)


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_accepts_paper_with_arbitrary_exchange_metadata(mock_execute_order, client):
    data = build_webhook_payload()
    data['exchange'] = 'SOME_METADATA_VALUE'

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    assert response.status_code == 200
    assert response.json == {"code": "success", "message": "Order executed"}
    expected_data = dict(data)
    expected_data.pop('passphrase')
    mock_execute_order.assert_called_once_with(expected_data)


@patch('app.record_trade')
def test_execute_order_paper_preserves_mixed_case_exchange_metadata(mock_record_trade):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')
    data['exchange'] = 'paper_Metadata_Value'

    result = execute_order(data)

    assert result is True
    assert data['exchange'] == 'paper_Metadata_Value'
    mock_record_trade.assert_called_once_with(data, None)


@patch('app.place_order_binance', return_value={'orderId': '123456', 'status': 'FILLED'})
@patch('app.record_trade')
def test_execute_order_real_accepts_mixed_case_supported_exchange_and_routes(
    mock_record_trade,
    mock_place_order_binance,
):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')
    data['order_type'] = 'REAL'
    data['exchange'] = 'bInAnCe'

    result = execute_order(data)

    assert result is True
    assert data['exchange'] == 'BINANCE'
    mock_place_order_binance.assert_called_once_with('BTCUSDT', '0.002', data)
    mock_record_trade.assert_called_once_with(data, {'orderId': '123456', 'status': 'FILLED'})


@patch('app.record_trade')
def test_execute_order_raises_positive_quantity_below_minimum_to_configured_minimum(mock_record_trade):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')
    data['strategy']['order_contracts'] = '0.001'

    result = execute_order(data)

    assert result is True
    assert data['strategy']['order_contracts'] == '0.002'
    mock_record_trade.assert_called_once_with(data, None)


@patch('app.record_trade')
def test_execute_order_accepts_scientific_notation_quantity(mock_record_trade):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')
    data['ticker'] = 'ETHUSDT'
    data['strategy']['order_contracts'] = '1e-3'

    result = execute_order(data)

    assert result is True
    assert data['strategy']['order_contracts'] == '1e-3'
    mock_record_trade.assert_called_once_with(data, None)


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_rejects_unsupported_exchange(mock_execute_order, client):
    data = build_webhook_payload()
    data['order_type'] = 'REAL'
    data['exchange'] = 'UNKNOWN'

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 400
    assert response.json["failure"] == {
        "code": "unsupported_exchange",
        "stage": "routing",
        "message": "No exchange value matching Binance, Bybit, or Hyperliquid",
    }


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_rejects_invalid_order_action(mock_execute_order, client):
    data = build_webhook_payload()
    data['strategy']['order_action'] = 'hold'

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 400
    assert response.json["failure"] == {
        "code": "invalid_field_value",
        "stage": "validation",
        "message": "Webhook field has unsupported value; expected BUY or SELL: strategy.order_action",
    }


@pytest.mark.parametrize(
    "path",
    [
        ('bar', 'close'),
        ('strategy', 'order_price'),
        ('strategy', 'position_size'),
        ('strategy', 'market_position_size'),
        ('strategy', 'prev_market_position_size'),
        ('leverage',),
    ],
)
@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_rejects_malformed_numeric_fields(mock_execute_order, client, path):
    data = build_webhook_payload()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = 'not-a-number'

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 400
    assert response.json["failure"]["code"] == "invalid_field_type"
    assert ".".join(path) in response.json["failure"]["message"]


@pytest.mark.parametrize(
    "path",
    [
        ('bar', 'close'),
        ('strategy', 'order_price'),
        ('strategy', 'position_size'),
        ('strategy', 'market_position_size'),
        ('strategy', 'prev_market_position_size'),
        ('leverage',),
    ],
)
def test_validate_webhook_payload_rejects_non_finite_numeric_fields(path):
    from app import validate_webhook_payload

    data = build_webhook_payload()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = float('inf')

    failure = validate_webhook_payload(data)

    assert failure.to_dict()["code"] == "invalid_field_value"
    assert ".".join(path) in failure.to_dict()["message"]


@patch('exchanges.binance.UMFutures')
@patch('app.record_trade')
def test_execute_order_real(mock_record_trade, mock_um_futures):
    from app import execute_order

    # Mock the Binance client instance and its methods
    mock_client = MagicMock()
    mock_um_futures.return_value = mock_client

    # Mock the order response
    mock_client.new_order.return_value = {'orderId': '123456', 'status': 'FILLED'}

    # Mock leverage methods
    mock_client.change_leverage.return_value = {'leverage': 10}
    mock_client.futures_change_margin_type = MagicMock()

    data = {
        'exchange': 'BINANCE',
        'strategy': {'order_action': 'BUY', 'order_contracts': '0.001', 'order_price': 50000,
                     'position_size': 0.001, 'order_id': '123', 'market_position': 'long',
                     'market_position_size': 0.001, 'prev_market_position': 'flat',
                     'prev_market_position_size': 0},
        'ticker': 'BTCUSDT',
        'leverage': 10,
        'order_type': 'REAL',
        'bar': {'time': '2023-01-01T00:00:00Z', 'close': 50000},
        'strategyName': 'TestStrategy'
    }

    result = execute_order(data)
    assert result

    # Verify that the Binance client was called
    mock_client.new_order.assert_called_once()
    mock_record_trade.assert_called_once()


@patch.dict(os.environ, {'HYPERLIQUID_SLIPPAGE': ''}, clear=False)
@patch('exchanges.hyperliquid.create_hyperliquid_exchange')
@patch('app.record_trade')
def test_execute_order_real_hyperliquid(mock_record_trade, mock_create_exchange):
    from app import execute_order

    mock_exchange = MagicMock()
    mock_create_exchange.return_value = mock_exchange
    mock_exchange.create_order.return_value = {'id': 'abc123', 'status': 'open'}

    data = {
        'exchange': 'HYPERLIQUID',
        'strategy': {'order_action': 'BUY', 'order_contracts': '0.002', 'order_price': 50000,
                     'position_size': 0.001, 'order_id': '123', 'market_position': 'long',
                     'market_position_size': 0.001, 'prev_market_position': 'flat',
                     'prev_market_position_size': 0},
        'ticker': 'BTCUSDT',
        'leverage': 10,
        'order_type': 'REAL',
        'bar': {'time': '2023-01-01T00:00:00Z', 'close': 50000},
        'strategyName': 'TestStrategy'
    }

    result = execute_order(data)
    assert result

    mock_exchange.set_margin_mode.assert_called_once_with('isolated', 'BTC/USDC:USDC', {'leverage': 10})
    mock_exchange.create_order.assert_called_once_with('BTC/USDC:USDC', 'market', 'buy', 0.002, 50000.0, {})
    mock_record_trade.assert_called_once()


@pytest.mark.parametrize(
    ('order_action', 'expected_side'),
    [
        ('bUy', 'Buy'),
        ('sElL', 'Sell'),
    ],
)
@patch('exchanges.bybit.HTTP')
@patch('app.record_trade')
def test_execute_order_real_bybit_normalizes_mixed_case_order_action(
    mock_record_trade,
    mock_http,
    order_action,
    expected_side,
):
    from app import execute_order

    mock_session = MagicMock()
    mock_http.return_value = mock_session
    mock_session.place_order.return_value = {'orderId': 'bybit-123', 'status': 'FILLED'}

    data = build_webhook_payload()
    data.pop('passphrase')
    data['order_type'] = 'REAL'
    data['exchange'] = 'BYBIT'
    data['leverage'] = 0
    data['strategy']['order_action'] = order_action
    data['strategy']['order_contracts'] = '0.002'

    result = execute_order(data)

    assert result is True
    mock_session.place_order.assert_called_once_with(
        category="linear",
        symbol='BTCUSDT',
        side=expected_side,
        orderType="Market",
        qty='0.002',
    )
    mock_record_trade.assert_called_once_with(data, {'orderId': 'bybit-123', 'status': 'FILLED'})

@patch('app.record_trade')
def test_execute_order_paper(mock_record_trade):
    from app import execute_order

    data = {
        'strategy': {'order_action': 'SELL', 'order_contracts': '0.001', 'order_price': 3000,
                     'position_size': 0.001, 'order_id': '123', 'market_position': 'short',
                     'market_position_size': 0.001, 'prev_market_position': 'flat',
                     'prev_market_position_size': 0},
        'ticker': 'ETHUSDT',
        'leverage': 5,
        'order_type': 'PAPER',
        'bar': {'time': '2023-01-01T00:00:00Z', 'close': 3000},
        'strategyName': 'TestStrategy'
    }

    result = execute_order(data)
    assert result
    mock_record_trade.assert_called_once_with(data, None)


@patch('app.record_trade')
def test_execute_order_defaults_missing_order_type(mock_record_trade):
    from app import execute_order

    data = {
        'strategy': {'order_action': 'SELL', 'order_contracts': '0.001', 'order_price': 3000,
                     'position_size': 0.001, 'order_id': '123', 'market_position': 'short',
                     'market_position_size': 0.001, 'prev_market_position': 'flat',
                     'prev_market_position_size': 0},
        'ticker': 'ETHUSDT',
        'leverage': 5,
        'passphrase': 'test-secret',
        'bar': {'time': '2023-01-01T00:00:00Z', 'close': 3000},
        'strategyName': 'TestStrategy'
    }

    result = execute_order(data)
    assert result
    assert data['order_type'] == 'PAPER'
    assert 'passphrase' not in data
    mock_record_trade.assert_called_once_with(data, None)


@patch.object(TRWError, 'log', autospec=True)
def test_execute_order_unsupported_real_exchange_returns_false_with_structured_failure(mock_log):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')
    data['order_type'] = 'REAL'
    data['exchange'] = 'UNKNOWN'

    result = execute_order(data)

    assert result is False
    mock_log.assert_called_once()
    assert mock_log.call_args[0][0].to_dict() == {
        "code": "unsupported_exchange",
        "stage": "routing",
        "message": "No exchange value matching Binance, Bybit, or Hyperliquid",
    }


@patch('app.place_order_binance', side_effect=RuntimeError('secret-bearing adapter error'))
@patch('app.record_trade')
@patch.object(TRWError, 'log', autospec=True)
def test_execute_order_real_adapter_exception_records_legacy_and_structured_failure(
    mock_log,
    mock_record_trade,
    mock_place_order_binance,
):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')
    data['order_type'] = 'REAL'
    data['exchange'] = 'BINANCE'

    result = execute_order(data)

    assert result is False
    mock_place_order_binance.assert_called_once()
    failure = {
        "code": "exchange_submission_failed",
        "stage": "exchange_submission",
        "message": "Exchange order submission failed",
    }
    mock_record_trade.assert_called_once_with(data, "Failed Real Order?", failure)
    mock_log.assert_called_once()
    assert mock_log.call_args[0][0].to_dict() == failure
    assert isinstance(mock_log.call_args[0][1], RuntimeError)

@patch('app.trades_collection')
def test_record_trade(mock_trades_collection):
    from app import record_trade

    data = {
        'bar': {'time': '2023-01-01T00:00:00Z', 'close': 50000},
        'strategyName': 'TestStrategy',
        'ticker': 'BTCUSDT',
        'strategy': {
            'order_action': 'buy',
            'order_contracts': '0.001',
            'order_price': 50000,
            'position_size': 0.001,
            'order_id': '123',
            'market_position': 'long',
            'market_position_size': 0.001,
            'prev_market_position': 'flat',
            'prev_market_position_size': 0
        },
        'leverage': 10,
        'order_type': 'PAPER'
    }
    order_response = {'orderId': '123456'}

    record_trade(data, order_response)
    mock_trades_collection.insert_one.assert_called_once()
    call_args = mock_trades_collection.insert_one.call_args[0][0]
    assert call_args['symbol'] == 'BTCUSDT'
    assert call_args['side'] == 'BUY'
    assert call_args['quantity'] == '0.001'
    assert call_args['leverage'] == 10
    assert call_args['order_type'] == 'PAPER'
    assert call_args['order_response'] == order_response


@patch('app.trades_collection')
def test_record_trade_adds_structured_failure_metadata(mock_trades_collection):
    from app import record_trade

    data = build_webhook_payload()
    data.pop('passphrase')
    failure = {
        "code": "exchange_submission_failed",
        "stage": "exchange_submission",
        "message": "Exchange order submission failed",
    }

    result = record_trade(data, "Failed Real Order?", failure)

    assert result is True
    call_args = mock_trades_collection.insert_one.call_args[0][0]
    assert call_args['order_response'] == "Failed Real Order?"
    assert call_args['failure'] == failure


@patch.object(TRWError, 'log', autospec=True)
@patch('app.trades_collection')
def test_record_trade_mongo_insert_failure_logs_structured_failure(mock_trades_collection, mock_log):
    from app import record_trade

    data = build_webhook_payload()
    data.pop('passphrase')
    mock_trades_collection.insert_one.side_effect = RuntimeError('mongo password leaked here')

    result = record_trade(data, None)

    assert result is False
    failure = {
        "code": "persistence_failed",
        "stage": "persistence",
        "message": "Failed to persist trade record",
    }
    mock_log.assert_called_once()
    assert mock_log.call_args[0][0].to_dict() == failure
    assert isinstance(mock_log.call_args[0][1], RuntimeError)

@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_empty_payload(mock_execute_order, client):
    """
    Test webhook behavior when receiving an empty JSON payload.
    The bot should NOT execute any order and should return an error.
    """

    response = client.post(
        '/webhook',
        json={},  # Empty payload
        headers={'X-Forwarded-For': '127.0.0.1'}
    )

    # execute_order should NEVER be called
    mock_execute_order.assert_not_called()

    # Status code should be 400
    assert response.status_code == 400

    print(f"Response JSON: {response.json}")
    # Check for either 'empty' in status or reason fields
    response_text = str(response.json).lower()
    assert 'empty' in response_text or 'missing' in response_text


def test_sanitize_dict_redacts_passphrase():
    payload = {
        'passphrase': 'test-secret',
        'strategy': {'order_action': 'buy'},
    }

    sanitized = sanitize_dict(payload)

    assert sanitized['passphrase'] == '***REDACTED***'
    assert sanitized['strategy']['order_action'] == 'buy'
