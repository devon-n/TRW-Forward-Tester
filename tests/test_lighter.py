from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from exchanges.lighter import _market_metadata_cache, place_order_lighter


@patch.dict(
    "os.environ",
    {
        "LIGHTER_ACCOUNT_INDEX": "42",
        "LIGHTER_API_PRIVATE_KEY": "private-key",
        "LIGHTER_SLIPPAGE": "0.01",
    },
    clear=False,
)
@patch("exchanges.lighter.create_lighter_client", new_callable=AsyncMock)
def test_place_order_lighter_submits_scaled_buy(mock_create_client):
    _market_metadata_cache.clear()
    client = MagicMock()
    client.create_market_order = AsyncMock(return_value=("tx", "hash", None))
    client.close = AsyncMock()
    mock_create_client.return_value = client

    with patch(
        "exchanges.lighter._fetch_market_metadata",
        return_value={
            "order_book_details": [{
                "symbol": "BTC",
                "market_id": 7,
                "market_type": "perp",
                "status": "active",
                "size_decimals": 3,
                "price_decimals": 2,
            }],
        },
    ):
        result = place_order_lighter(
            "BTCUSDT.P",
            "0.25",
            {"strategy": {"order_action": "buy", "order_price": "65000"}},
        )

    assert result == ("tx", "hash", None)
    client.create_market_order.assert_awaited_once_with(
        market_index=7,
        client_order_index=0,
        base_amount=250,
        avg_execution_price=6565000,
        is_ask=False,
    )
    client.close.assert_awaited_once()


@patch.dict(
    "os.environ",
    {
        "LIGHTER_ACCOUNT_INDEX": "42",
        "LIGHTER_API_PRIVATE_KEY": "private-key",
        "LIGHTER_SLIPPAGE": "0.01",
    },
    clear=False,
)
@patch("exchanges.lighter.create_lighter_client", new_callable=AsyncMock)
def test_place_order_lighter_applies_sell_slippage(mock_create_client):
    _market_metadata_cache.clear()
    client = MagicMock()
    client.create_market_order = AsyncMock(return_value=("tx", "hash", None))
    client.close = AsyncMock()
    mock_create_client.return_value = client

    with patch(
        "exchanges.lighter._fetch_market_metadata",
        return_value={
            "order_book_details": [{
                "symbol": "BTC",
                "market_id": 7,
                "market_type": "perp",
                "status": "active",
                "size_decimals": 3,
                "price_decimals": 2,
            }],
        },
    ):
        place_order_lighter(
            "BTCUSDT.P",
            "0.25",
            {"strategy": {"order_action": "sell", "order_price": "65000"}},
        )

    client.create_market_order.assert_awaited_once_with(
        market_index=7,
        client_order_index=0,
        base_amount=250,
        avg_execution_price=6435000,
        is_ask=True,
    )
    client.close.assert_awaited_once()


def test_place_order_lighter_rejects_non_positive_price():
    with patch.dict(
        "os.environ",
        {"LIGHTER_ACCOUNT_INDEX": "42", "LIGHTER_API_PRIVATE_KEY": "private-key"},
        clear=False,
    ):
        with pytest.raises(ValueError, match="order quantity and strategy.order_price"):
            place_order_lighter(
                "BTCUSDT",
                "1",
                {"strategy": {"order_action": "BUY", "order_price": "0"}},
            )
