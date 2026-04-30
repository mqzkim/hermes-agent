"""Gateway agent-cache invalidation for memory configuration."""

from gateway.run import GatewayRunner


def _sig_for_config(config: dict) -> str:
    return GatewayRunner._agent_config_signature(
        "gpt-test",
        {"api_key": "secret", "base_url": "https://example.test", "provider": "test"},
        ["memory", "terminal"],
        "ephemeral",
        cache_keys=GatewayRunner._extract_cache_busting_config(config),
    )


def test_memory_enabled_changes_bust_agent_cache():
    """A gateway agent created while memory was disabled must not be reused after enabling it."""
    disabled = {
        "memory": {
            "memory_enabled": False,
            "user_profile_enabled": False,
            "memory_char_limit": 2200,
            "user_char_limit": 1375,
            "provider": "",
            "nudge_interval": 10,
        }
    }
    enabled = {
        "memory": {
            "memory_enabled": True,
            "user_profile_enabled": True,
            "memory_char_limit": 2200,
            "user_char_limit": 1375,
            "provider": "",
            "nudge_interval": 10,
        }
    }

    assert _sig_for_config(disabled) != _sig_for_config(enabled)


def test_memory_limit_and_provider_changes_bust_agent_cache():
    """Memory limits/provider are read at AIAgent construction, so cache hits would keep stale state."""
    base = {
        "memory": {
            "memory_enabled": True,
            "user_profile_enabled": True,
            "memory_char_limit": 2200,
            "user_char_limit": 1375,
            "provider": "",
            "nudge_interval": 10,
        }
    }
    changed = {
        "memory": {
            "memory_enabled": True,
            "user_profile_enabled": True,
            "memory_char_limit": 3000,
            "user_char_limit": 1500,
            "provider": "honcho",
            "nudge_interval": 5,
        }
    }

    assert _sig_for_config(base) != _sig_for_config(changed)
