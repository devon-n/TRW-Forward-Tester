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


def test_dashboard_load_with_no_trades_does_not_write_test_csv(monkeypatch, tmp_path):
    class FakeStreamlit:
        session_state = {}

        @staticmethod
        def cache_data(ttl=None):
            def decorator(func):
                return func
            return decorator

        @staticmethod
        def set_page_config(**kwargs):
            return None

    class FakeTradesCollection:
        @staticmethod
        def find(query):
            assert query == {}
            return []

    fake_mongo_client = types.SimpleNamespace(
        trading=types.SimpleNamespace(trades=FakeTradesCollection())
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(sys.modules, "streamlit", FakeStreamlit)
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda: None))
    monkeypatch.setitem(sys.modules, "pymongo", types.SimpleNamespace(MongoClient=lambda uri: fake_mongo_client))
    monkeypatch.syspath_prepend(str(DASHBOARD_DIR))
    monkeypatch.syspath_prepend(str(REPO_ROOT))

    module_name = "dashboard_dashboard_no_trades"
    module_path = DASHBOARD_DIR / "dashboard.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(SystemExit):
        spec.loader.exec_module(module)

    assert not (tmp_path / "test.csv").exists()
