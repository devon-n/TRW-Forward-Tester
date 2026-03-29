import pytest
from unittest.mock import MagicMock, patch
import sys

# Patch MongoDB BEFORE app.py is imported
mock_mongo_client = MagicMock()
mock_db = MagicMock()
mock_collection = MagicMock()
mock_mongo_client.trading = mock_db
mock_db.trades = mock_collection

# Apply the patch globally before any imports
sys.modules['pymongo'] = MagicMock()
patcher = patch('pymongo.MongoClient', return_value=mock_mongo_client)
patcher.start()

# Now it's safe to import app
from app import app  # noqa: E402

@pytest.fixture
def client():
    """Flask test client fixture"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_trades_collection():
    """Fixture to access the mocked trades collection"""
    return mock_collection
