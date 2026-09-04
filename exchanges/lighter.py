"""Lighter perpetual orders using the official Lighter signer SDK."""

import asyncio
import json
import math
import os
from urllib.request import urlopen

import lighter

_market_metadata_cache = {}


def _required_env(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing Lighter setting. Set {name}.")
    return value


def _required_lighter_private_key():
    return os.getenv("LIGHTER_API_PRIVATE_KEY") or _required_env("LIGHTER_PRIVATE_KEY")


def _int_env(name, default=None):
    value = os.getenv(name)
    if value in (None, ""):
        if default is None:
            raise ValueError(f"Missing Lighter setting. Set {name}.")
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer.") from None


def _slippage_env():
    raw = os.getenv("LIGHTER_SLIPPAGE", "0")
    try:
        slippage = float(raw)
    except ValueError:
        raise ValueError("LIGHTER_SLIPPAGE must be a finite non-negative fraction.") from None
    if not math.isfinite(slippage) or slippage < 0:
        raise ValueError("LIGHTER_SLIPPAGE must be a finite non-negative fraction.")
    return slippage


def _lighter_profile():
    return lighter.get_endpoint_profile("mainnet")


def _normalize_lighter_symbol(symbol):
    normalized = str(symbol).upper().replace(".P", "")
    for suffix in ("USDT", "USD"):
        if normalized.endswith(suffix):
            return normalized[:-len(suffix)]
    return normalized


def _fetch_market_metadata(profile):
    with urlopen(f"{profile.api_url}/api/v1/orderBookDetails", timeout=10) as response:
        return json.load(response)


async def _resolve_market_metadata(symbol, profile):
    cache_key = profile.name
    if cache_key not in _market_metadata_cache:
        loop = asyncio.get_running_loop()
        _market_metadata_cache[cache_key] = await loop.run_in_executor(
            None,
            _fetch_market_metadata,
            profile,
        )

    target = _normalize_lighter_symbol(symbol)
    markets = _market_metadata_cache[cache_key].get("order_book_details", [])
    for market in markets:
        if (
            market.get("market_type") == "perp"
            and market.get("symbol", "").upper() == target
            and market.get("status") == "active"
        ):
            return market
    raise ValueError(
        f"Lighter active perpetual market not found for ticker {symbol} "
        f"(normalized as {target})."
    )


async def create_lighter_client():
    profile = _lighter_profile()
    account_index = _int_env("LIGHTER_ACCOUNT_INDEX")
    api_key_index = _int_env("LIGHTER_API_KEY_INDEX", 1)
    private_key = _required_lighter_private_key()
    client = lighter.SignerClient(
        url=profile.api_url,
        account_index=account_index,
        api_private_keys={api_key_index: private_key},
        chain_id=profile.chain_id,
    )
    error = client.check_client()
    if error is not None:
        await client.close()
        raise RuntimeError(f"Lighter client validation failed: {error}")
    return client


def _run_async(coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    coroutine.close()
    raise RuntimeError("Lighter order submission cannot run inside an active event loop.")


async def _place_market_order(symbol, quantity, price, is_ask):
    profile = _lighter_profile()
    market = await _resolve_market_metadata(symbol, profile)
    market_index = _int_env("LIGHTER_MARKET_INDEX", market["market_id"])
    base_scale = _int_env(
        "LIGHTER_BASE_AMOUNT_SCALE",
        10 ** int(market["size_decimals"]),
    )
    price_scale = _int_env(
        "LIGHTER_PRICE_SCALE",
        10 ** int(market["price_decimals"]),
    )
    slippage = _slippage_env()
    worst_price = price * (1 - slippage if is_ask else 1 + slippage)
    scaled_quantity = round(quantity * base_scale)
    scaled_price = round(worst_price * price_scale)
    if scaled_quantity <= 0 or scaled_price <= 0:
        raise ValueError("Lighter order quantity and strategy.order_price must be positive.")

    client = await create_lighter_client()
    try:
        return await client.create_market_order(
            market_index=market_index,
            client_order_index=0,
            base_amount=scaled_quantity,
            avg_execution_price=scaled_price,
            is_ask=is_ask,
        )
    finally:
        await client.close()


def place_order_lighter(symbol, qty, data):
    """Submit a market order; Lighter amounts are integer fixed-point values."""
    strategy = data.get("strategy", {})
    action = str(strategy.get("order_action", "")).upper()
    if action not in {"BUY", "SELL"}:
        raise ValueError("Lighter order payload is missing strategy.order_action.")

    quantity = float(qty)
    price = float(strategy.get("order_price", 0))
    if quantity <= 0 or price <= 0:
        raise ValueError("Lighter order quantity and strategy.order_price must be positive.")

    profile = _lighter_profile()
    market = _normalize_lighter_symbol(symbol)
    print(
        f"Preparing order for Lighter: REAL - {action} {qty} "
        f"({market} on {profile.name}) with leverage {data.get('leverage', 0)}"
    )
    result = _run_async(
        _place_market_order(
            symbol,
            quantity,
            price,
            action == "SELL",
        )
    )
    if result[2] is not None:
        raise RuntimeError(f"Lighter order rejected: {result[2]}")
    print(f"Order executed: REAL - {action} {qty} ({market} on {profile.name}) | {result}")
    return result
