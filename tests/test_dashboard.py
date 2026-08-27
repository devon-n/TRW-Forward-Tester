import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_ROOT / "dashboard"


def test_calculate_profit_uses_existing_fee_rates():
    sys.path.insert(0, str(DASHBOARD_DIR))
    try:
        from helpers import calculate_profit
    finally:
        sys.path.remove(str(DASHBOARD_DIR))

    balances = {}

    buy_result = calculate_profit({
        "strategy_name": "fee-check",
        "time": "2026-08-25T00:00:00Z",
        "quantity": 2,
        "order_price": 100,
        "side": "BUY",
    }, balances)

    assert buy_result == pytest.approx((2, -200.4, -201.02, -0.4, -1.02))

    sell_result = calculate_profit({
        "strategy_name": "fee-check",
        "time": "2026-08-25T00:01:00Z",
        "quantity": 2,
        "order_price": 100,
        "side": "SELL",
    }, balances)

    assert sell_result == pytest.approx((0, -0.8, -2.04, -0.8, -2.04))
