import json
import traceback

from binance.binance_orders_service import open_test_order
from models.signal import SignalPayload
from services.orders.helpers import format_position_size, is_open_order
from services.trade_logger import record_trade


def execute_order(data: bytes):
    try:
        signal = SignalPayload.model_validate_json(data)
        side = signal.strategy.order_action.upper()

        signal.strategy.order_contracts = format_position_size(
            signal.ticker, signal.strategy.order_contracts
        )

        if signal.order_type == "REAL":

            if is_open_order(signal.strategy.order_id):
                open_test_order(signal)

            order_response = "TEST"
            print(
                f"Real order executed: {signal.order_type} - {side} {signal.strategy.order_contracts} {signal.ticker} | {order_response}"
            )
            record_trade(data, order_response)
        else:
            if is_open_order(signal.strategy.order_id):
                open_test_order(signal)

            print(
                f"Simulated paper order: {signal.order_type} - {side} {signal.strategy.order_contracts} {signal.ticker}"
            )
            record_trade(data, None)

        return True
    except Exception as e:
        record_trade(data, "Failed Real Order?")
        print(f"Failed Order: An exception occurred: {e}")
        traceback.print_exc()
        return False
