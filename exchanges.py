import json
import os
from binance.um_futures import UMFutures
from pybit.unified_trading import HTTP

def place_binance_order(symbol, qty, data):
    client = UMFutures(os.getenv('API_KEY'), os.getenv('API_SECRET'))
    side = data['strategy']['order_action'].upper()
    leverage = int(data.get('leverage', 0))
    print(f"Preparing order for Binance: REAL - {side} {qty} {symbol} with leverage {leverage}")

    if leverage != 0:
        print(f"\nSetting leverage to {leverage}x\n")
        try:
            client.futures_change_leverage(symbol=symbol, leverage=leverage)
            client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
        except Exception as e:
            print(f"Error while adjusting leverage: {e}")
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

def place_bybit_order(symbol, qty, data):
    session = HTTP(
        testnet=False,
        api_key=os.getenv('API_KEY_6'),
        api_secret=os.getenv('API_SECRET_6'),
    )
    # Ignore specific error codes.
    #session.ignore_codes.add(110043) # 110043: Leverage already set
    side = data['strategy']['order_action'][0].upper() + data['strategy']['order_action'][1:]
    leverage = float(data.get('leverage', 0))
    print(f"Preparing order for Bybit: REAL - {side} {qty} {symbol} with leverage {leverage}")
    if leverage != 0:
        print(f"\nSetting leverage to {leverage}x\n")
        try:
            lev_response = session.set_leverage(category="linear",
                                 symbol=symbol,
                                 buyLeverage=str(leverage),
                                 sellLeverage=str(leverage),
                                 )
            lev_json=lev_response.json()
            if lev_json["retCode"] == 110043 :
                print(f"Leverage already set to {leverage}x.")
        except Exception as e:
            print(f"Error while adjusting leverage: {e}")
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
