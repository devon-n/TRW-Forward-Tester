import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from config.config import AppSettings, DatabaseSettings
from repositories.mongo import MongoRepository


def test_app_settings_accepts_required_fields_without_optional_values():
    with patch.dict(os.environ, {"MONGO_URI": "mongodb://test", "WHITELISTED_IPS": "127.0.0.1"}, clear=True):
        settings = AppSettings()

    assert settings.MONGO_URI == "mongodb://test"
    assert settings.WHITELISTED_IPS == "127.0.0.1"
    assert settings.WEBHOOK_SECRET is None


@pytest.mark.parametrize("missing", ["MONGO_URI", "WHITELISTED_IPS"])
def test_app_settings_rejects_missing_startup_fields(missing):
    environment = {"MONGO_URI": "mongodb://test", "WHITELISTED_IPS": "127.0.0.1"}
    environment.pop(missing)

    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(ValidationError, match=missing):
            AppSettings()


def test_database_settings_requires_only_mongo_uri():
    with patch.dict(os.environ, {"MONGO_URI": "mongodb://test"}, clear=True):
        settings = DatabaseSettings()

    assert settings.MONGO_URI == "mongodb://test"

    with patch.dict(os.environ, {}, clear=True), patch('repositories.mongo.MongoClient') as mock_client:
        repository = MongoRepository(validate_uri=False)
        repository.get_mongo_client()
    mock_client.assert_called_once_with(None)

    with patch.dict(os.environ, {}, clear=True), patch('repositories.mongo.MongoClient') as mock_client:
        repository = MongoRepository(validate_uri=True)
        with pytest.raises(ValidationError, match='MONGO_URI'):
            repository.get_mongo_client()
    mock_client.assert_not_called()

    with patch.dict(os.environ, {'MONGO_URI': 'mongodb://present'}, clear=True), \
            patch('repositories.mongo.MongoClient') as mock_client:
        MongoRepository(validate_uri=True).get_mongo_client()
    mock_client.assert_called_once_with('mongodb://present')
