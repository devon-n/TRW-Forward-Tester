import json
import os
from binance.um_futures import UMFutures
from pybit.unified_trading import HTTP

def place_binance_order(order_type, symbol, side, qty, data):
    client = UMFutures(os.getenv('API_KEY'), os.getenv('API_SECRET'))
    leverage = int(data.get('leverage', 0))
    if leverage > 1:
        print(f"\nSetting leverage to {leverage}x\n")
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
    elif leverage == 1:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
    else:
        pass # Doesn't touch leverage if set to "0"

    print(f"Sending Order: {json.dumps(data)}\n")

    order_response = client.new_order(
        symbol=symbol,
        side=side,
        type=order_type,
        quantity=qty
    )

    print(f"Real order executed: {order_type} - {side} {qty} {symbol} | {order_response}")

    return order_response

def place_bybit_order(order_type, symbol, side, qty, data):
    session = HTTP(
        testnet=False,
        api_key=os.getenv('API_KEY'),
        api_secret=os.getenv('API_SECRET'),
    )
    leverage = float(data.get('leverage', 0))
    if leverage > 1:
        print(f"\nSetting leverage to {leverage}x\n")
        session.set_leverage(category="linear",
                             symbol=symbol,
                             buyLeverage=str(leverage),
                             sellLeverage=str(leverage),
                             )
    elif leverage == 1:
        session.set_leverage(category="linear",
                             symbol=symbol,
                             buyLeverage="1",
                             sellLeverage="1",
                             )
    else:
        pass # Doesn't touch leverage if set to "0"

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
