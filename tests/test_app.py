import os
from unittest.mock import (
    MagicMock,
    patch,
)

import pytest

from errors import TRWError
from logging_utils import sanitize_dict


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
            'prev_market_position_size': 0,
        },
        'leverage': 10,
        'order_type': 'PAPER',
    }


def test_welcome(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.data == b""


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order', return_value=True)
def test_webhook_accepts_valid_paper_payload(mock_execute_order, client):
    data = build_webhook_payload()

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    assert response.status_code == 200
    assert response.json == {"code": "success", "message": "Order executed"}
    expected_data = dict(data)
    expected_data.pop('passphrase')
    mock_execute_order.assert_called_once_with(expected_data)


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order', return_value=True)
def test_webhook_accepts_valid_real_payload_with_normalized_exchange(mock_execute_order, client):
    data = build_webhook_payload()
    data['order_type'] = 'real'
    data['exchange'] = 'bInAnCe'

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    assert response.status_code == 200
    expected_data = dict(data)
    expected_data.pop('passphrase')
    expected_data['order_type'] = 'REAL'
    expected_data['exchange'] = 'BINANCE'
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


@pytest.mark.parametrize('passphrase', [None, 'wrong-secret'])
@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_rejects_missing_or_wrong_passphrase(mock_execute_order, client, passphrase):
    data = build_webhook_payload(passphrase=passphrase)
    if passphrase is None:
        data.pop('passphrase')

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 401
    assert response.json == {"status": "error", "message": "Invalid Passphrase"}


@pytest.mark.parametrize(
    ('mutate', 'expected_code', 'expected_field'),
    [
        (lambda data: data['strategy'].pop('order_contracts'), 'missing_required_field', 'strategy.order_contracts'),
        (lambda data: data.update({'strategy': 'not-an-object'}), 'invalid_field_type', 'strategy'),
        (lambda data: data.update({'order_type': 'PAPERX'}), 'invalid_field_value', 'order_type'),
        (lambda data: data['strategy'].update({'order_action': 'hold'}), 'invalid_field_value', 'strategy.order_action'),
        (lambda data: data.update({'order_type': 'REAL', 'exchange': 'UNKNOWN'}), 'unsupported_exchange', 'exchange'),
    ],
)
@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_returns_structured_validation_failures(
    mock_execute_order,
    client,
    mutate,
    expected_code,
    expected_field,
):
    data = build_webhook_payload()
    mutate(data)

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 400
    assert response.json["status"] == "error"
    assert response.json["reason"] == "invalid payload"
    assert response.json["failure"]["code"] == expected_code
    if expected_field != 'exchange':
        assert expected_field in response.json["failure"]["message"]


@pytest.mark.parametrize(
    'path',
    [
        ('bar', 'close'),
        ('leverage',),
    ],
)
@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_rejects_representative_malformed_numeric_fields(mock_execute_order, client, path):
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


@patch('app.record_trade')
def test_execute_order_defaults_missing_order_type_and_preserves_legacy_dict(mock_record_trade):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')
    data.pop('order_type')
    data['exchange'] = 'paper_Metadata_Value'

    result = execute_order(data)

    assert result is True
    assert data['order_type'] == 'PAPER'
    assert data['exchange'] == 'paper_Metadata_Value'
    mock_record_trade.assert_called_once_with(data, None)


@patch('app.record_trade')
def test_execute_order_raises_positive_quantity_below_minimum_to_configured_minimum(mock_record_trade):
    from app import execute_order

    data = build_webhook_payload()
    data.pop('passphrase')

    result = execute_order(data)

    assert result is True
    assert data['strategy']['order_contracts'] == '0.002'
    mock_record_trade.assert_called_once_with(data, None)


@patch('app.place_order_binance', return_value={'orderId': '123456', 'status': 'FILLED'})
@patch('app.record_trade')
def test_execute_order_real_routes_to_supported_exchange(mock_record_trade, mock_place_order_binance):
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


@patch.dict(os.environ, {'HYPERLIQUID_SLIPPAGE': ''}, clear=False)
@patch('exchanges.hyperliquid.create_hyperliquid_exchange')
@patch('app.record_trade')
def test_execute_order_real_hyperliquid(mock_record_trade, mock_create_exchange):
    from app import execute_order

    mock_exchange = MagicMock()
    mock_create_exchange.return_value = mock_exchange
    mock_exchange.create_order.return_value = {'id': 'abc123', 'status': 'open'}

    data = build_webhook_payload()
    data.pop('passphrase')
    data['order_type'] = 'REAL'
    data['exchange'] = 'HYPERLIQUID'
    data['strategy']['order_action'] = 'BUY'
    data['strategy']['order_contracts'] = '0.002'

    result = execute_order(data)

    assert result is True
    mock_exchange.set_margin_mode.assert_called_once_with('isolated', 'BTC/USDC:USDC', {'leverage': 10})
    mock_exchange.create_order.assert_called_once_with('BTC/USDC:USDC', 'market', 'buy', 0.002, 50000.0, {})
    mock_record_trade.assert_called_once()


@pytest.mark.parametrize(
    ('order_action', 'expected_side'),
    [('bUy', 'Buy')],
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
    assert mock_log.call_args[0][0].to_dict()["code"] == "unsupported_exchange"


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

    data = build_webhook_payload()
    data.pop('passphrase')
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
    assert mock_log.call_args[0][0].to_dict()["code"] == "persistence_failed"
    assert isinstance(mock_log.call_args[0][1], RuntimeError)


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_empty_payload(mock_execute_order, client):
    response = client.post('/webhook', json={}, headers={'X-Forwarded-For': '127.0.0.1'})

    mock_execute_order.assert_not_called()
    assert response.status_code == 400
    assert 'empty' in str(response.json).lower()


def test_sanitize_dict_redacts_passphrase():
    payload = {
        'passphrase': 'test-secret',
        'strategy': {'order_action': 'buy'},
    }

    sanitized = sanitize_dict(payload)

    assert sanitized['passphrase'] == '***REDACTED***'
    assert sanitized['strategy']['order_action'] == 'buy'
