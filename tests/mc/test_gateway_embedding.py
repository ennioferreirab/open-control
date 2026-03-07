import os
from unittest.mock import MagicMock, patch


def _make_bridge(setting_value):
    bridge = MagicMock()
    bridge.query.return_value = setting_value
    return bridge


def test_gateway_sets_env_var_when_setting_present():
    from mc.runtime.gateway import _sync_embedding_model

    bridge = _make_bridge('openrouter/openai/text-embedding-3-small')
    with patch.dict(os.environ, {}, clear=False):
        _sync_embedding_model(bridge)
        assert os.environ.get('NANOBOT_MEMORY_EMBEDDING_MODEL') == 'openrouter/openai/text-embedding-3-small'


def test_gateway_clears_env_var_when_setting_empty():
    from mc.runtime.gateway import _sync_embedding_model

    bridge = _make_bridge('')
    with patch.dict(os.environ, {'NANOBOT_MEMORY_EMBEDDING_MODEL': 'old-model'}, clear=False):
        _sync_embedding_model(bridge)
        assert 'NANOBOT_MEMORY_EMBEDDING_MODEL' not in os.environ


def test_gateway_clears_env_var_when_setting_none():
    from mc.runtime.gateway import _sync_embedding_model

    bridge = _make_bridge(None)
    with patch.dict(os.environ, {'NANOBOT_MEMORY_EMBEDDING_MODEL': 'old-model'}, clear=False):
        _sync_embedding_model(bridge)
        assert 'NANOBOT_MEMORY_EMBEDDING_MODEL' not in os.environ
