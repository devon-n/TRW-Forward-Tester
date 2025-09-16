import json
import os
from binance.um_futures import UMFutures
from pybit.unified_trading import HTTP

from set_leverage_api import set_leverage_binance, set_leverage_bybit

def place_order_binance(symbol, qty, data):
    client = UMFutures(os.getenv('API_KEY'), os.getenv('API_SECRET'))
    side = data['strategy']['order_action'].upper()
    leverage = int(data.get('leverage', 0))
    print(f"Preparing order for Binance: REAL - {side} {qty} {symbol} with leverage {leverage}")

    if leverage != 0:
        set_leverage_binance(client, symbol, leverage)
    else:
        pass # Doesn't touch leverage if set to "0"

    print(f"Sending Order: {json.dumps(data)}\n")

    order_response = client.new_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=qty
    )

    print(f"Order executed: REAL - {side} {qty} {symbol} | {order_response}")

    return order_response

def place_order_bybit(symbol, qty, data):
    session = HTTP(
        testnet=False,
        api_key=os.getenv('API_KEY_6'),
        api_secret=os.getenv('API_SECRET_6'),
    )
    side = data['strategy']['order_action'][0].upper() + data['strategy']['order_action'][1:]
    leverage = float(data.get('leverage', 0))
    print(f"Preparing order for Bybit: REAL - {side} {qty} {symbol} with leverage {leverage}")
    if leverage != 0:
        set_leverage_bybit(session, symbol, leverage)
    else:
        pass # Doesn't touch leverage if set to "0"

    print(f"Sending Order: {json.dumps(data)}\n")

    order_response = session.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        orderType="Market",
        qty=qty,
    )

    print(f"Order executed: REAL - {side} {qty} {symbol} | {order_response}")

    return order_response
