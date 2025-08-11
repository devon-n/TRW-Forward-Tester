import math
from binance.enums import FuturesOrderType
from models.signal import SignalPayload
import os
import logging

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
    ConfigurationRestAPI,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
)
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
    TestOrderSideEnum,
    NewOrderSideEnum,
)


logging.basicConfig(level=logging.INFO)

configuration_rest_api = ConfigurationRestAPI(
    api_key=os.getenv("API_KEY", ""),
    api_secret=os.getenv("API_SECRET", ""),
    base_path=os.getenv(
        "BASE_PATH", DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL
    ),
)

client = DerivativesTradingUsdsFutures(config_rest_api=configuration_rest_api)


def new_order(signal: SignalPayload):
    try:
        response = client.rest_api.new_order(
            symbol=signal.ticker,
            side=NewOrderSideEnum[signal.strategy.order_action.upper()],
            type=FuturesOrderType.LIMIT.value,
        )

        rate_limits = response.rate_limits
        logging.info(f"new_order() rate limits: {rate_limits}")

        data = response.data()
        logging.info(f"new_order() response: {data}")

    except Exception as e:
        logging.error(f"new_order() error: {e}")


def open_test_order(signal: SignalPayload):
    try:
        client.rest_api.change_initial_leverage(
            symbol=signal.ticker, leverage=math.ceil(signal.comment_data.leverage)
        )

        response = client.rest_api.test_order(
            symbol=signal.ticker,
            side=TestOrderSideEnum[signal.strategy.order_action.upper()],
            type=FuturesOrderType.LIMIT.value,
            quantity=signal.comment_data.position_size,
        )

        rate_limits = response.rate_limits
        logging.info(f"test_order() rate limits: {rate_limits}")

        data = response.data()
        logging.info(f"test_order() response: {data}")
    except Exception as e:
        logging.error(f"test_order() error: {e}")
