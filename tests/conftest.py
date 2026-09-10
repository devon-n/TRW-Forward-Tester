import os
import pytest
from config.config import AppSettings
from unittest.mock import MagicMock, patch
import sys

# Patch MongoDB BEFORE app.py is imported
mock_mongo_client = MagicMock()
mock_db = MagicMock()
mock_collection = MagicMock()
mock_mongo_client.trading = mock_db
mock_db.trades = mock_collection

# Apply the patch globally before any imports
os.environ.setdefault('MONGO_URI', 'mongodb://test')
os.environ.setdefault('WHITELISTED_IPS', '127.0.0.1')
sys.modules['pymongo'] = MagicMock()
patcher = patch('pymongo.MongoClient', return_value=mock_mongo_client)
patcher.start()

# Now it's safe to import app
import app as app_module  # noqa: E402
from app import app  # noqa: E402


@pytest.fixture(autouse=True)
def clear_app_caches():
    app_module.get_whitelisted_ips.cache_clear()
    yield
    app_module.get_whitelisted_ips.cache_clear()

@pytest.fixture
def client():
    """Flask test client fixture"""
    app_module.app_settings = AppSettings()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_trades_collection():
    """Fixture to access the mocked trades collection"""
    return mock_collection
