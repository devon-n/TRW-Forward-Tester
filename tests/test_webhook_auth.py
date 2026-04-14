import os
from unittest.mock import patch

from tests.test_app import build_webhook_payload


@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': ''})
@patch('app.execute_order')
def test_webhook_bypass_when_secret_not_set(mock_execute_order, client):
    """
    Verify that if WEBHOOK_SECRET is empty string, the webhook is allowed
    even without a passphrase.
    """
    mock_execute_order.return_value = True
    data = build_webhook_payload()
    data.pop('passphrase') # No passphrase provided

    response = client.post(
        '/webhook',
        json=data,
        headers={'X-Forwarded-For': '127.0.0.1'}
    )

    assert response.status_code == 200
    assert response.json == {"code": "success", "message": "Order executed"}
    mock_execute_order.assert_called_once()

@patch.dict(os.environ, {'WHITELISTED_IPS': '127.0.0.1', 'WEBHOOK_SECRET': 'test-secret'})
@patch('app.execute_order')
def test_webhook_enforced_when_secret_is_set(mock_execute_order, client):
    """
    Verify that if WEBHOOK_SECRET is set, the webhook is rejected
    if the passphrase is missing or wrong.
    """
    data = build_webhook_payload()
    data.pop('passphrase')

    response = client.post(
        '/webhook',
        json=data,
        headers={'X-Forwarded-For': '127.0.0.1'}
    )

    assert response.status_code == 401
    mock_execute_order.assert_not_called()
