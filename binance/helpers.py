import logging
from binance_sdk_derivatives_trading_usds_futures import DerivativesTradingUsdsFutures
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
    NewOrderSideEnum,
)


def get_stop_side(order_action: str):
    return (
        NewOrderSideEnum.SELL if order_action.upper() == "BUY" else NewOrderSideEnum.BUY
    )


def get_position_size(client: DerivativesTradingUsdsFutures, ticker: str):
    position_size = (
        client.rest_api.position_information_v3(symbol=ticker).data().position_amt
    )
    amt = float(position_size or 0)
    return abs(amt)
