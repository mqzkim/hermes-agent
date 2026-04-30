from types import SimpleNamespace

import pytest

from agent.local_cli_client import LocalCLIClient, normalized_local_cli_name


def test_normalized_local_cli_name_handles_windows_paths():
    assert normalized_local_cli_name(r"C:\Users\mqz\AppData\Roaming\npm\claude.cmd") == "claude"
    assert normalized_local_cli_name("/opt/bin/codex.exe") == "codex"
    assert normalized_local_cli_name("custom-copilot.cmd") == "custom-copilot"


def test_claude_argv_strips_acp_flags_and_uses_print_mode():
    client = LocalCLIClient(command="claude", args=["--acp", "--stdio", "--verbose"])

    argv = client._argv("hello")

    assert argv == [
        "claude",
        "-p",
        "hello",
        "--output-format",
        "text",
        "--permission-mode",
        "bypassPermissions",
        "--verbose",
    ]


def test_codex_argv_strips_acp_flags_and_uses_exec_mode():
    client = LocalCLIClient(command="codex", args=["--acp", "--stdio", "--full-auto"])

    argv = client._argv("hello")

    assert argv == [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--full-auto",
        "hello",
    ]


def test_custom_command_preserves_args_and_passes_prompt_last():
    client = LocalCLIClient(command="custom-acp", args=["--stdio"])

    argv = client._argv("hello")

    assert argv == ["custom-acp", "--stdio", "hello"]


def test_success_response_is_openai_chat_completion_shape(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout="LOCAL_OK\n", stderr="progress\n", returncode=0)

    monkeypatch.setattr("agent.local_cli_client.subprocess.run", fake_run)
    client = LocalCLIClient(command="claude")

    response = client.chat.completions.create(
        model="anthropic/claude-sonnet-4",
        messages=[{"role": "user", "content": "reply"}],
    )

    assert response.choices[0].message.content == "LOCAL_OK"
    assert response.choices[0].message.tool_calls is None
    assert response.choices[0].finish_reason == "stop"
    assert response.usage.total_tokens == 0


def test_nonzero_exit_raises_with_stderr_tail(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout="", stderr="bad\n" * 100, returncode=2)

    monkeypatch.setattr("agent.local_cli_client.subprocess.run", fake_run)
    client = LocalCLIClient(command="claude")

    with pytest.raises(RuntimeError) as exc:
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])

    assert "exited with code 2" in str(exc.value)
    assert "bad" in str(exc.value)


def test_timeout_raises_clear_error(monkeypatch):
    def fake_run(*args, **kwargs):
        raise TimeoutError("expired")

    monkeypatch.setattr("agent.local_cli_client.subprocess.run", fake_run)
    client = LocalCLIClient(command="claude", timeout=3)

    with pytest.raises(TimeoutError) as exc:
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])

    assert "local CLI timed out after 3s" in str(exc.value)


def test_timeout_expired_raises_clear_error(monkeypatch):
    import subprocess

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr("agent.local_cli_client.subprocess.run", fake_run)
    client = LocalCLIClient(command="claude", timeout=4)

    with pytest.raises(TimeoutError) as exc:
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])

    assert "local CLI timed out after 4s" in str(exc.value)


def test_empty_command_and_base_url_fallbacks():
    assert normalized_local_cli_name(None) == ""
    assert LocalCLIClient(base_url="local-cli://codex").command == "codex"
    assert LocalCLIClient(base_url="https://example.com").command == "claude"


def test_prompt_builder_handles_empty_list_and_non_string_content(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["prompt"] = argv[2]
        return SimpleNamespace(stdout="OK", stderr="", returncode=0)

    monkeypatch.setattr("agent.local_cli_client.subprocess.run", fake_run)
    client = LocalCLIClient(command="claude")
    client.chat.completions.create(
        model="m",
        messages=[
            {"role": "system", "content": None},
            {"role": "user", "content": [{"type": "text", "text": "hello"}, 123, None]},
            {"role": "assistant", "content": {"structured": True}},
        ],
    )

    assert captured["prompt"] == "hello\n123\n\nassistant: {'structured': True}"


def test_nonzero_exit_uses_stdout_tail_when_stderr_empty(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout="stdout failure", stderr="", returncode=9)

    monkeypatch.setattr("agent.local_cli_client.subprocess.run", fake_run)
    client = LocalCLIClient(command="claude")

    with pytest.raises(RuntimeError) as exc:
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])

    assert "exited with code 9" in str(exc.value)
    assert "stdout failure" in str(exc.value)
