import json
from pybit.unified_trading import HTTP
from config.config import AppSettings, SettingsValidationError
from utils.errors import MissingCredentialError
from utils.logging_utils import sanitize_dict

def place_order_bybit(symbol, qty, data):
    settings = AppSettings()
    try:
        settings.validate_required('API_KEY', 'API_SECRET')
    except SettingsValidationError as error:
        raise MissingCredentialError("Bybit REAL", error.missing) from error
    api_key, api_secret = settings.API_KEY, settings.API_SECRET
    session = HTTP(
        testnet=False,
        api_key=api_key,
        api_secret=api_secret,
    )
    side = data['strategy']['order_action'].upper().capitalize()
    leverage = float(data.get('leverage', 0))
    print(f"Preparing order for Bybit: REAL - {side} {qty} {symbol} with leverage {leverage}")
    if leverage != 0:
        set_leverage_bybit(session, symbol, leverage)

    print(f"Sending Order: {json.dumps(sanitize_dict(data))}\n")

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
