import json
from binance.um_futures import UMFutures
from config.config import Config
from utils.errors import MissingCredentialError
from utils.logging_utils import sanitize_dict


def place_order_binance(symbol, qty, data):
    try:
        api_key, api_secret = Config.validate_binance_real()
    except RuntimeError as error:
        missing = tuple(
            name for name in (Config.API_KEY, Config.API_SECRET)
            if not str(Config.get_optional(name) or "").strip()
        )
        raise MissingCredentialError("Binance REAL", missing) from error
    client = UMFutures(api_key, api_secret)
    side = data['strategy']['order_action'].upper()
    leverage = int(data.get('leverage', 0))
    print(f"Preparing order for Binance: REAL - {side} {qty} {symbol} with leverage {leverage}")

    if leverage != 0:
        set_leverage_binance(client, symbol, leverage)

    print(f"Sending Order: {json.dumps(sanitize_dict(data))}\n")

    order_response = client.new_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=qty
    )

    print(f"Order executed: REAL - {side} {qty} {symbol} | {order_response}")

    return order_response

def set_leverage_binance(client,symbol, leverage):
    print(f"\nSetting leverage to {leverage}x\n")
    try:
        client.futures_change_margin_type(symbol=symbol, marginType="ISOLATED")
        client.futures_change_leverage(symbol=symbol, leverage=leverage)

        print(f"Leverage successfully set to {leverage}x")

    except Exception as e:
        print(f"Error while adjusting leverage(Binance): {e}")
