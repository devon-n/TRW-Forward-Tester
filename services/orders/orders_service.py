import json
import traceback

from models.signal import CommentData, SignalPayload
from services.orders.helpers import format_position_size
from services.trade_logger import record_trade


def execute_order(data: bytes):
    try:
        signal = SignalPayload.model_validate_json(data)
        side = signal.strategy.order_action.upper()

        if isinstance(signal.comment_data, CommentData):
            comment_data = signal.comment_data

        print(
            f"Preparing order {signal.order_type} - {side} {signal.strategy.order_contracts} {signal.ticker} with leverage"
        )
        signal.strategy.order_contracts = format_position_size(
            signal.ticker, signal.strategy.order_contracts
        )
        print(signal.strategy.order_id.value)

        if signal.order_type == "REAL":
            print(f"\nSending Order: {json.dumps(data)}\n")

            order_response = "TEST"
            print(
                f"Real order executed: {signal.order_type} - {side} {signal.strategy.order_contracts} {signal.ticker} | {order_response}"
            )
            record_trade(data, order_response)
        else:
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
