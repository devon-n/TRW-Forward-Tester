import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from config.config import AppSettings, EnvNames
from repositories.mongo import MongoRepository


def test_app_settings_accepts_required_fields_without_optional_values():
    with patch.dict(os.environ, {EnvNames.MONGO_URI: "mongodb://test", EnvNames.WHITELISTED_IPS: "127.0.0.1"}, clear=True):
        settings = AppSettings()

    assert settings.MONGO_URI == "mongodb://test"
    assert settings.WHITELISTED_IPS == "127.0.0.1"
    assert settings.WEBHOOK_SECRET is None


def test_app_settings_rejects_missing_startup_database_setting():
    environment = {EnvNames.MONGO_URI: "mongodb://test", EnvNames.WHITELISTED_IPS: "127.0.0.1"}
    environment.pop(EnvNames.MONGO_URI)

    with patch.dict(os.environ, environment, clear=True):
        settings = AppSettings()
        with pytest.raises(ValidationError, match=EnvNames.MONGO_URI):
            settings.validate_startup()


def test_app_settings_rejects_missing_startup_whitelist():
    with patch.dict(os.environ, {EnvNames.MONGO_URI: "mongodb://test"}, clear=True):
        with pytest.raises(ValueError, match=EnvNames.WHITELISTED_IPS):
            AppSettings().validate_startup()


def test_app_settings_validates_context_specific_requirements():
    with patch.dict(os.environ, {EnvNames.MONGO_URI: "mongodb://test"}, clear=True):
        settings = AppSettings()

    assert settings.MONGO_URI == "mongodb://test"
    assert settings.database.MONGO_URI == "mongodb://test"

    with patch.dict(os.environ, {}, clear=True), patch('repositories.mongo.MongoClient') as mock_client:
        repository = MongoRepository(validate_uri=False)
        repository.get_mongo_client()
    mock_client.assert_called_once_with(None)

    with patch.dict(os.environ, {}, clear=True), patch('repositories.mongo.MongoClient') as mock_client:
        repository = MongoRepository(validate_uri=True)
        with pytest.raises(ValidationError, match=EnvNames.MONGO_URI):
            repository.get_mongo_client()
    mock_client.assert_not_called()

    with patch.dict(os.environ, {EnvNames.MONGO_URI: 'mongodb://present'}, clear=True), \
            patch('repositories.mongo.MongoClient') as mock_client:
        MongoRepository(validate_uri=True).get_mongo_client()
    mock_client.assert_called_once_with('mongodb://present')
