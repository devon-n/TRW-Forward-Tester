import json
import math
import time
from binance.enums import FuturesOrderType
from binance.helpers import get_position_size, get_stop_side
from models.signal import SignalPayload
import os
import logging

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
    ConfigurationRestAPI,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
)
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
    NewOrderTimeInForceEnum,
    TestOrderSideEnum,
    NewOrderSideEnum,
    TestOrderTimeInForceEnum,
    NewOrderResponse,
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


def new_order(signal: SignalPayload) -> NewOrderResponse:
    try:
        print(json.dumps(signal.model_dump(), indent=2, default=str))

        change_levarege_response = client.rest_api.change_initial_leverage(
            symbol=signal.ticker, leverage=math.ceil(signal.comment_data.leverage)
        )
        logging.info(
            f"change_initial_leverage rate limits: {change_levarege_response.rate_limits}"
        )
        logging.info(
            f"change_initial_leverage response: {change_levarege_response.data}"
        )

        response = client.rest_api.new_order(
            symbol=signal.ticker,
            side=NewOrderSideEnum[signal.strategy.order_action.upper()],
            type=FuturesOrderType[signal.comment_data.order_type.value].value,
            quantity=signal.strategy.order_contracts,
            price=signal.strategy.order_price,
            time_in_force=NewOrderTimeInForceEnum.GTC,
        )
        logging.info(f"new_order() rate limits: {response.rate_limits}")
        logging.info(f"new_order() response: {response.data()}")

        stop_side = get_stop_side(signal.strategy.order_action)
        sl_resp = client.rest_api.new_order(
            symbol=signal.ticker,
            side=stop_side,
            type=FuturesOrderType.STOP_MARKET.value,
            stop_price=signal.comment_data.sl,
            close_position="true",
        )
        logging.info(f"stop_loss() rate limits: {sl_resp.rate_limits}")
        logging.info(f"stop_loss() response: {sl_resp.data()}")

        return response.data()
    except Exception as e:
        logging.error(f"new_order() error: {e}")
        return NewOrderResponse(type=str(e))


def tp_close_order(signal: SignalPayload):
    try:
        print(json.dumps(signal.model_dump(), indent=2, default=str))

        size = get_position_size(client=client, ticker=signal.ticker)
        if size == 0:
            logging.info("Already flat.")
            cancel_open_orders(signal.ticker)
            return
        stop_side = get_stop_side(signal.strategy.order_action)
        response = client.rest_api.new_order(
            symbol=signal.ticker,
            side=stop_side,
            type=FuturesOrderType.TAKE_PROFIT_MARKET.value,
            # stop_price=signal.comment_data.tp,
            quantity=size,
            reduce_only="true",
        )
        logging.info(f"tp_close_order() rate limits: {response.rate_limits}")
        logging.info(f"tp_close_order() response: {response.data()}")

        cancel_open_orders(signal.ticker)
    except Exception as e:
        logging.error(f"tp_close_order() error: {e}")


def be_close_order(signal: SignalPayload):
    try:
        print(json.dumps(signal.model_dump(), indent=2, default=str))

        response = client.rest_api.new_order(
            symbol=signal.ticker,
            side=NewOrderSideEnum[signal.strategy.order_action.upper()],
            type=FuturesOrderType.STOP_MARKET.value,
            stop_price=signal.comment_data.sl,
            close_position="true",
        )
        logging.info(f"be_close_order() rate limits: {response.rate_limits}")
        logging.info(f"be_close_order() response: {response.data()}")

        # cancel_open_orders(signal.ticker)
    except Exception as e:
        logging.error(f"be_close_order() error: {e}")


def open_test_order(signal: SignalPayload):
    try:
        print(json.dumps(signal.model_dump(), indent=2, default=str))

        change_levarege_response = client.rest_api.change_initial_leverage(
            symbol=signal.ticker, leverage=math.ceil(signal.comment_data.leverage)
        )
        logging.info(
            f"change_initial_leverage rate limits: {change_levarege_response.rate_limits}"
        )
        logging.info(
            f"change_initial_leverage response: {change_levarege_response.data}"
        )

        response = client.rest_api.test_order(
            symbol=signal.ticker,
            side=TestOrderSideEnum[signal.strategy.order_action.upper()],
            type=FuturesOrderType[signal.comment_data.order_type.value].value,
            quantity=signal.strategy.order_contracts,
            price=signal.strategy.order_price,
            time_in_force=TestOrderTimeInForceEnum.GTC,
        )
        logging.info(f"test_order() rate limits: {response.rate_limits}")
        logging.info(f"test_order() response: {response.data()}")

        stop_side = (
            TestOrderSideEnum.SELL
            if signal.strategy.order_action.upper() == "BUY"
            else TestOrderSideEnum.BUY
        )
        sl_resp = client.rest_api.test_order(
            symbol=signal.ticker,
            side=stop_side,
            type=FuturesOrderType.STOP_MARKET.value,
            stop_price=signal.comment_data.sl,
            close_position="true",
            time_in_force=TestOrderTimeInForceEnum.GTC,
        )
        logging.info(f"stop_loss() rate limits: {sl_resp.rate_limits}")
        logging.info(f"stop_loss() response: {sl_resp.data()}")

    except Exception as e:
        logging.error(f"test_order() error: {e}")


def cancel_open_orders(ticker: str):
    close_orders_response = client.rest_api.cancel_all_open_orders(symbol=ticker)
    logging.info(f"close_position() rate limits: {close_orders_response.rate_limits}")
    logging.info(f"close_position() response: {close_orders_response.data()}")
