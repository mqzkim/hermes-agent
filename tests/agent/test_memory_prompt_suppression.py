"""AIAgent memory prompt suppression behavior."""

from run_agent import AIAgent
from tools.memory_tool import MemoryStore


MEMORY_CONFIG = {
    "memory": {
        "memory_enabled": True,
        "user_profile_enabled": True,
        "memory_char_limit": 2200,
        "user_char_limit": 1375,
        "provider": "",
        "nudge_interval": 10,
    },
    "agent": {"tool_use_enforcement": False},
}


def _seed_memory(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.memory_tool.get_memory_dir", lambda: tmp_path)
    store = MemoryStore()
    store.load_from_disk()
    store.add("memory", "cron-visible memory should not be injected")
    store.add("user", "cron-visible user profile should not be injected")


def test_suppress_memory_prompt_keeps_memory_tool_store_available(tmp_path, monkeypatch):
    _seed_memory(tmp_path, monkeypatch)
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: MEMORY_CONFIG)

    agent = AIAgent(
        model="test-model",
        api_key="test-key",
        base_url="https://example.test/v1",
        enabled_toolsets=["memory"],
        skip_memory=False,
        suppress_memory_prompt=True,
        quiet_mode=True,
        skip_context_files=True,
    )

    assert agent._memory_store is not None
    assert agent._memory_enabled is True
    assert agent._user_profile_enabled is True
    assert "memory" in agent.valid_tool_names

    prompt = agent._build_system_prompt()
    assert "cron-visible memory should not be injected" not in prompt
    assert "cron-visible user profile should not be injected" not in prompt


def test_memory_prompt_injects_by_default(tmp_path, monkeypatch):
    _seed_memory(tmp_path, monkeypatch)
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: MEMORY_CONFIG)

    agent = AIAgent(
        model="test-model",
        api_key="test-key",
        base_url="https://example.test/v1",
        enabled_toolsets=["memory"],
        skip_memory=False,
        quiet_mode=True,
        skip_context_files=True,
    )

    prompt = agent._build_system_prompt()
    assert "cron-visible memory should not be injected" in prompt
    assert "cron-visible user profile should not be injected" in prompt
