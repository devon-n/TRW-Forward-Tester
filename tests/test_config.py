import os
from unittest.mock import patch

import pytest

from config.config import Config


def test_config_exposes_canonical_environment_name_constants():
    expected = {
        'MONGO_URI': 'MONGO_URI',
        'WHITELISTED_IPS': 'WHITELISTED_IPS',
        'WEBHOOK_SECRET': 'WEBHOOK_SECRET',
        'API_KEY': 'API_KEY',
        'API_SECRET': 'API_SECRET',
        'HYPERLIQUID_WALLET_ADDRESS': 'HYPERLIQUID_WALLET_ADDRESS',
        'HYPERLIQUID_PRIVATE_KEY': 'HYPERLIQUID_PRIVATE_KEY',
        'HYPERLIQUID_SLIPPAGE': 'HYPERLIQUID_SLIPPAGE',
    }

    assert {name: getattr(Config, name) for name in expected} == expected


def test_require_accepts_present_nonblank_values():
    with patch.dict(os.environ, {'CONFIG_TEST_VALUE': ' configured '}, clear=False):
        assert Config.require('CONFIG_TEST_VALUE') == ' configured '


@pytest.mark.parametrize('value', [None, ''])
def test_require_rejects_missing_and_blank_values(value):
    environment = {} if value is None else {'CONFIG_TEST_VALUE': value}
    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(RuntimeError, match='CONFIG_TEST_VALUE'):
            Config.require('CONFIG_TEST_VALUE')


def test_validate_app_startup_requires_only_mongo_and_whitelist():
    with patch.dict(os.environ, {'MONGO_URI': 'mongodb://test', 'WHITELISTED_IPS': '127.0.0.1'}, clear=True):
        Config.validate_app_startup()


def test_validate_app_startup_does_not_require_exchange_or_webhook_values():
    with patch.dict(os.environ, {'MONGO_URI': 'mongodb://test', 'WHITELISTED_IPS': '127.0.0.1'}, clear=True):
        Config.validate_app_startup()


@pytest.mark.parametrize('missing', ['MONGO_URI', 'WHITELISTED_IPS'])
def test_validate_app_startup_remains_fail_fast(missing):
    environment = {'MONGO_URI': 'mongodb://test', 'WHITELISTED_IPS': '127.0.0.1'}
    environment.pop(missing)

    with patch.dict(os.environ, environment, clear=True):
        with pytest.raises(RuntimeError, match=missing):
            Config.validate_app_startup()


def test_context_validators_are_exchange_specific():
    with patch.dict(os.environ, {'API_KEY': 'key', 'API_SECRET': 'secret'}, clear=True):
        Config.validate_binance_real()
        Config.validate_bybit_real()
        with pytest.raises(RuntimeError, match='HYPERLIQUID_WALLET_ADDRESS'):
            Config.validate_hyperliquid_public()

    with patch.dict(os.environ, {'HYPERLIQUID_WALLET_ADDRESS': '0xabc'}, clear=True):
        Config.validate_hyperliquid_public()
        with pytest.raises(RuntimeError, match='HYPERLIQUID_PRIVATE_KEY'):
            Config.validate_hyperliquid_real()


def test_dashboard_validation_requires_mongo_only():
    with patch.dict(os.environ, {'MONGO_URI': 'mongodb://test'}, clear=True):
        Config.validate_dashboard_startup()


def test_dashboard_validation_remains_fail_fast_without_mongo():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match='MONGO_URI'):
            Config.validate_dashboard_startup()


def test_config_reads_environment_dynamically():
    with patch.dict(os.environ, {Config.API_KEY: 'first'}, clear=False):
        assert Config.get_optional(Config.API_KEY) == 'first'
    with patch.dict(os.environ, {Config.API_KEY: 'second'}, clear=False):
        assert Config.get_optional(Config.API_KEY) == 'second'
