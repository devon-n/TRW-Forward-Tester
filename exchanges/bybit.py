import json
import os
from pybit.unified_trading import HTTP


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

def set_leverage_bybit(session, symbol, leverage):
    print(f"\nSetting leverage to {leverage}x\n")
    try:
        session.set_margin_mode(setMarginMode="ISOLATED_MARGIN")
        session.set_leverage(
            category="linear",
            symbol=symbol,
            buyLeverage=str(leverage),
            sellLeverage=str(leverage),
            )

        print(f"Leverage successfully set to {leverage}x")

    except Exception as e:
        err_str = str(e)
        if "110043" in err_str: # Leverage already set.
            return
        raise