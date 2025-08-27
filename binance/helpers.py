from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
    NewOrderSideEnum,
)


def get_stop_side(order_action: str):
    return (
        NewOrderSideEnum.SELL if order_action.upper() == "BUY" else NewOrderSideEnum.BUY
    )
