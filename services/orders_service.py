import json
import traceback
from config import minQtyDict, precisionDecimalDict
from models.signal import CommentData, SignalPayload
from services.trade_logger import record_trade


def execute_order(data):
    try:
        signal = SignalPayload.model_validate_json(data)
        side = signal.strategy.order_action.upper()
        if isinstance(signal.comment_data, CommentData):
            comment_data = signal.comment_data

        print(
            f"Preparing order {signal.order_type} - {side} {signal.strategy.order_contracts} {signal.ticker} with leverage {comment_data.leverage}"
        )

        ticker = signal.ticker.replace(".P", "")
        ticker = ticker + "T" if ticker.endswith("USD") else ticker

        if ticker in minQtyDict and float(signal.strategy.order_contracts) < float(
            minQtyDict[ticker]
        ):
            quantity = minQtyDict[ticker]

        if ticker in precisionDecimalDict:
            quantity = str(
                round(
                    float(signal.strategy.order_contracts), precisionDecimalDict[ticker]
                )
            )

        data["strategy"]["order_contracts"] = signal.strategy.order_contracts

        if signal.order_type == "REAL":
            print(f"\nSending Order: {json.dumps(data)}\n")
            order_response = "TEST"
            print(
                f"Real order executed: {signal.order_type} - {side} {signal.strategy.order_contracts} {ticker} | {order_response}"
            )
            record_trade(data, order_response)
        else:
            print(
                f"Simulated paper order: {signal.order_type} - {side} {signal.strategy.order_contracts} {ticker}"
            )
            record_trade(data, None)

        return True
    except Exception as e:
        record_trade(data, "Failed Real Order?")
        print(f"Failed Order: An exception occurred: {e}")
        traceback.print_exc()
        return False
