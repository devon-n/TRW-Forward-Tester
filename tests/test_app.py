import pytest
from unittest.mock import patch, MagicMock
import os
from app import app, whitelist_ip, execute_order, record_trade

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_welcome(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.data == b""



@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1,192.168.1.1', 'WEBHOOK_PASSPHRASE': 'test_passphrase'})
@patch('app.execute_order')
def test_webhook_valid_passphrase(mock_execute_order, client):
    mock_execute_order.return_value = True
    data = {
        'passphrase': 'test_passphrase',
        'strategyName': 'TestStrategy',
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

    # Print the current whitelisted IPs for debugging
    print(f"Whitelisted IPs: {os.environ.get('WHITELISTED_IPS')}")

    response = client.post('/webhook', json=data, headers={'X-Forwarded-For': '127.0.0.1'})

    # Print response data for debugging
    print(f"Response status code: {response.status_code}")
    print(f"Response data: {response.data}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response data: {response.data}"
    assert response.json == {"code": "success", "message": "Order executed"}

# Add a test to check the whitelist_ip decorator directly
def test_whitelist_ip_decorator():
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

@patch('app.UMFutures')
@patch('app.record_trade')
def test_execute_order_real(mock_record_trade, mock_um_futures):
    mock_client = MagicMock()
    mock_um_futures.return_value = mock_client
    mock_client.new_order.return_value = {'orderId': '123456'}

    data = {
        'strategy': {'order_action': 'BUY', 'order_contracts': '0.001'},
        'ticker': 'BTCUSDT',
        'leverage': 10,
        'order_type': 'REAL',
        'bar': {'time': '2023-01-01T00:00:00Z', 'close': 50000},
        'strategyName': 'TestStrategy'
    }

    result = execute_order(data)
    assert result == True
    mock_client.new_order.assert_called_once_with(
        symbol='BTCUSDT',
        side='BUY',
        type='MARKET',
        quantity='0.002'  # This should match the minQtyDict value for 'BTCUSDT'
    )
    mock_record_trade.assert_called_once()

@patch('app.record_trade')
def test_execute_order_paper(mock_record_trade):
    data = {
        'strategy': {'order_action': 'SELL', 'order_contracts': '0.001'},
        'ticker': 'ETHUSDT',
        'leverage': 5,
        'order_type': 'PAPER',
        'bar': {'time': '2023-01-01T00:00:00Z', 'close': 3000},
        'strategyName': 'TestStrategy'
    }

    result = execute_order(data)
    assert result == True
    mock_record_trade.assert_called_once_with(data, None)

@patch('app.trades_collection')
def test_record_trade(mock_trades_collection):
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
#test for when empty payload being sent
@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_PASSPHRASE': 'test_passphrase'})
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

    # Status code depends on your app logic (400 or 403 are both acceptable)
    assert response.status_code in (400, 403)

    # Optional: if you return JSON error messages
    if response.is_json:
        assert "error" in response.json or "message" in response.json
