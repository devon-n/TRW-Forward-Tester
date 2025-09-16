import json
import os
from binance.um_futures import UMFutures
from pybit.unified_trading import HTTP

def place_binance_order(order_type, symbol, side, qty, leverage, data):
    client = UMFutures(os.getenv('API_KEY'), os.getenv('API_SECRET'))
    if leverage != 0:
        print(f"\nSetting leverage to {leverage}x\n")
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")

    print(f"Sending Order: {json.dumps(data)}\n")

    order_response = client.new_order(
        symbol=symbol,
        side=side,
        type=order_type,
        quantity=qty
    )

    print(f"Real order executed: {order_type} - {side} {qty} {symbol} | {order_response}")

    return order_response

def place_bybit_order(order_type, symbol, side, qty, leverage, data):
    session = HTTP(
        testnet=False,
        api_key=os.getenv('API_KEY'),
        api_secret=os.getenv('API_SECRET'),
    )
    if leverage != 0:
        print(f"\nSetting leverage to {leverage}x\n")
        session.set_leverage(category="linear",
                             symbol=symbol,
                             buyLeverage=leverage,
                             sellLeverage=leverage,
                             )

    print(f"Sending Order: {json.dumps(data)}\n")

    order_response = session.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        orderType=order_type,
        qty=qty,
    )

    print(f"Real order executed: {order_type} - {side} {qty} {symbol} | {order_response}")

    return order_response
