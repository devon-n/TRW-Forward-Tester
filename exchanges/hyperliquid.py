import json
import os

import ccxt


def create_hyperliquid_exchange():
    wallet_address = os.getenv('HYPERLIQUID_WALLET_ADDRESS')
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')

    if not wallet_address or not private_key:
        raise ValueError('Missing Hyperliquid credentials. Set HYPERLIQUID_WALLET_ADDRESS and HYPERLIQUID_PRIVATE_KEY.')

    return ccxt.hyperliquid({
        'walletAddress': wallet_address,
        'privateKey': private_key,
    })


def normalize_symbol_hyperliquid(symbol):
    normalized = symbol.replace('.P', '').upper()
    if normalized.endswith('USDT'):
        base = normalized[:-4]
    elif normalized.endswith('USD'):
        base = normalized[:-3]
    else:
        raise ValueError(f'Unsupported Hyperliquid symbol format: {symbol}')
    return f'{base}/USDC:USDC'


def extract_order_params(data):
    params = {}
    strategy = data.get('strategy', {})

    for key in ('reduceOnly', 'stopLossPrice', 'takeProfitPrice', 'triggerPrice', 'clientOrderId'):
        value = data.get(key, strategy.get(key))
        if value is not None:
            params[key] = value

    slippage = data.get('slippage') or os.getenv('HYPERLIQUID_SLIPPAGE')
    if slippage:
        params['slippage'] = str(slippage)

    return params


def place_order_hyperliquid(symbol, qty, data):
    exchange = create_hyperliquid_exchange()
    hyperliquid_symbol = normalize_symbol_hyperliquid(symbol)
    side = data['strategy']['order_action'].lower()
    leverage = int(float(data.get('leverage', 0) or 0))
    params = extract_order_params(data)

    print(f"Preparing order for Hyperliquid: REAL - {side.upper()} {qty} {hyperliquid_symbol} with leverage {leverage}")

    if leverage != 0:
        set_leverage_hyperliquid(exchange, hyperliquid_symbol, leverage)

    print(f"Sending Order: {json.dumps(data)}\n")

    order_response = exchange.create_order(
        hyperliquid_symbol,
        'market',
        side,
        float(qty),
        None,
        params,
    )

    print(f"Order executed: REAL - {side.upper()} {qty} {hyperliquid_symbol} | {order_response}")
    return order_response


def set_leverage_hyperliquid(exchange, symbol, leverage):
    print(f"\nSetting leverage to {leverage}x\n")
    try:
        exchange.set_margin_mode('isolated', symbol, {'leverage': leverage})
        print(f"Leverage successfully set to {leverage}x")
    except Exception as e:
        print(f"Error while adjusting leverage(Hyperliquid): {e}")


def cancel_orders_hyperliquid(order_ids, symbol, params=None):
    exchange = create_hyperliquid_exchange()
    hyperliquid_symbol = normalize_symbol_hyperliquid(symbol)
    return exchange.cancel_orders(order_ids, hyperliquid_symbol, params or {})


def cancel_entry_and_children_hyperliquid(entry_id, child_ids, symbol, params=None):
    exchange = create_hyperliquid_exchange()
    hyperliquid_symbol = normalize_symbol_hyperliquid(symbol)
    entry_result = exchange.cancel_orders([entry_id], hyperliquid_symbol, params or {})

    if not _all_cancellations_succeeded(entry_result):
        return {
            'entry': entry_result,
            'children': [],
            'children_cancelled': False,
        }

    clean_child_ids = [order_id for order_id in child_ids if order_id]
    child_result = []
    if clean_child_ids:
        child_result = exchange.cancel_orders(clean_child_ids, hyperliquid_symbol, params or {})

    return {
        'entry': entry_result,
        'children': child_result,
        'children_cancelled': True,
    }


def fetch_balance_hyperliquid():
    exchange = create_hyperliquid_exchange()
    return exchange.fetch_balance()


def fetch_historical_orders_hyperliquid():
    exchange = create_hyperliquid_exchange()
    return exchange.public_post_info({
        'type': 'historicalOrders',
        'user': os.getenv('HYPERLIQUID_WALLET_ADDRESS'),
    })


def fetch_fills_by_time_hyperliquid(start_time, end_time):
    exchange = create_hyperliquid_exchange()
    return exchange.public_post_info({
        'type': 'userFillsByTime',
        'user': os.getenv('HYPERLIQUID_WALLET_ADDRESS'),
        'startTime': start_time,
        'endTime': end_time,
    })


def _all_cancellations_succeeded(cancel_results):
    if not cancel_results:
        return False
    return all(result.get('status') == 'success' for result in cancel_results)
