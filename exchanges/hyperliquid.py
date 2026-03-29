"""
Hyperliquid orders via CCXT.

CCXT passes `price` into create_order even for type=market: it is the reference used only to
compute the IOC limit bounds (price * (1 ± slippage)). Set strategy.order_price from the webhook
or we fall back to fetch_ticker. Slippage is a fraction (e.g. 0.05 for 5%), same as a typical
ExchangeClient-style wrapper.

Requires ccxt>=4.5 (see requirements.txt): older ccxt triggers Hyperliquid HTTP 422 on place order.
"""
import json
import os

import ccxt
from packaging.version import parse

# ccxt<4.5 still embeds deprecated fields (e.g. brokerCode) in POST /exchange; Hyperliquid returns 422 deserialize.
_MIN_CCXT_FOR_HYPERLIQUID = "4.5.0"


def _assert_ccxt_hyperliquid_compatible():
    current_version = getattr(ccxt, '__version__', '0') or '0'
    if parse(current_version) < parse(_MIN_CCXT_FOR_HYPERLIQUID):
        ver = getattr(ccxt, '__version__', 'unknown')
        raise RuntimeError(
            f'Hyperliquid requires ccxt>={_MIN_CCXT_FOR_HYPERLIQUID} '
            f'(found {ver}). Older builds send JSON the API rejects with HTTP 422. '
            f'Install deps from this repo: pip install -r requirements.txt'
        )


def create_hyperliquid_exchange():
    _assert_ccxt_hyperliquid_compatible()
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


def _resolve_market_reference_price(exchange, hyperliquid_symbol, data):
    """Hyperliquid market orders need a reference price so CCXT can apply slippage bounds."""
    strategy = data.get('strategy', {})
    raw = strategy.get('order_price')
    if raw is not None and raw != '':
        try:
            p = float(raw)
            if p > 0:
                return p
        except (TypeError, ValueError):
            pass
    ticker = exchange.fetch_ticker(hyperliquid_symbol)
    last = ticker.get('last') or ticker.get('close') or ticker.get('bid')
    if last is None:
        raise ValueError(
            'Hyperliquid market order needs a reference price: set strategy.order_price in the webhook '
            'or ensure the market ticker returns last/close/bid.'
        )
    return float(last)


def _parse_slippage(raw):
    if raw is None or raw == '':
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def extract_order_params(data):
    params = {}
    strategy = data.get('strategy', {})

    for key in ('reduceOnly', 'stopLossPrice', 'takeProfitPrice', 'triggerPrice', 'clientOrderId'):
        value = data.get(key, strategy.get(key))
        if value is not None:
            params[key] = value

    slippage = _parse_slippage(data.get('slippage')) or _parse_slippage(os.getenv('HYPERLIQUID_SLIPPAGE'))
    if slippage is not None and slippage > 0:
        params['slippage'] = slippage

    return params


def place_order_hyperliquid(symbol, qty, data):
    """Market order: amount + reference price + optional params (slippage, reduceOnly, etc.)."""
    exchange = create_hyperliquid_exchange()
    hyperliquid_symbol = normalize_symbol_hyperliquid(symbol)
    side = data['strategy']['order_action'].lower()
    leverage = int(float(data.get('leverage', 0) or 0))
    params = extract_order_params(data)

    print(f"Preparing order for Hyperliquid: REAL - {side.upper()} {qty} {hyperliquid_symbol} with leverage {leverage}")

    if leverage != 0 and not set_leverage_hyperliquid(exchange, hyperliquid_symbol, leverage):
        raise RuntimeError(f'Failed to set Hyperliquid leverage to {leverage}x for {hyperliquid_symbol}')

    print(f"Sending Order: {json.dumps(data)}\n")

    reference_price = _resolve_market_reference_price(exchange, hyperliquid_symbol, data)

    order_response = exchange.create_order(
        hyperliquid_symbol,
        'market',
        side,
        float(qty),
        reference_price,
        params,
    )

    print(f"Order executed: REAL - {side.upper()} {qty} {hyperliquid_symbol} | {order_response}")
    return order_response


def set_leverage_hyperliquid(exchange, symbol, leverage):
    print(f"\nSetting leverage to {leverage}x\n")
    try:
        exchange.set_margin_mode('isolated', symbol, {'leverage': leverage})
        print(f"Leverage successfully set to {leverage}x")
        return True
    except Exception as e:
        print(f"Error while adjusting leverage(Hyperliquid): {e}")
        return False


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
    return all(result.get('status') == 'canceled' for result in cancel_results)
