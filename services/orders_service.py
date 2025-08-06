import json
from config import minQtyDict, precisionDecimalDict
from services.trade_logger import record_trade


def execute_order(data):
    try:
        side = data["strategy"]["order_action"].upper()
        quantity = data["strategy"]["order_contracts"]
        ticker = data["ticker"]
        leverage = int(data.get("leverage", 0))
        order_type = data.get("order_type", "PAPER").upper()

        print(
            f"Preparing order {order_type} - {side} {quantity} {ticker} with leverage {leverage}"
        )

        ticker = ticker.replace(".P", "")
        ticker = ticker + "T" if ticker.endswith("USD") else ticker

        if ticker in minQtyDict and float(quantity) < float(minQtyDict[ticker]):
            quantity = minQtyDict[ticker]

        if ticker in precisionDecimalDict:
            quantity = str(round(float(quantity), precisionDecimalDict[ticker]))

        data["strategy"]["order_contracts"] = quantity

        if order_type == "REAL":
            print(f"\nSending Order: {json.dumps(data)}\n")
            # Placeholder for real Binance order logic
            order_response = "TEST"
            print(
                f"Real order executed: {order_type} - {side} {quantity} {ticker} | {order_response}"
            )
            record_trade(data, order_response)
        else:
            print(f"Simulated paper order: {order_type} - {side} {quantity} {ticker}")
            record_trade(data, None)

        return True
    except Exception as e:
        record_trade(data, "Failed Real Order?")
        print(f"Failed Order: An exception occurred: {e}")
        return False
