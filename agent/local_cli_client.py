"""OpenAI-shaped adapter for local Claude Code and Codex CLI delegation.

This adapter is intentionally small: it lets Hermes run explicit subagent
commands such as ``acp_command='claude'`` through the installed local CLI when
those commands are not ACP stdio servers. It returns a Chat Completions-shaped
object so the normal Hermes chat_completions transport can consume it.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from typing import Any, Iterable, List, Mapping, Optional


_ACP_ONLY_FLAGS = {"--acp", "--stdio"}


def normalized_local_cli_name(command: str | None) -> str:
    """Normalize a command/executable path for POSIX and Windows forms."""
    raw = str(command or "").strip()
    if not raw:
        return ""
    base = raw.replace("\\", "/").rsplit("/", 1)[-1]
    lower = base.lower()
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if lower.endswith(suffix):
            return lower[: -len(suffix)]
    return lower


def _strip_acp_only_args(args: Iterable[str] | None) -> List[str]:
    return [str(arg) for arg in (args or []) if str(arg) not in _ACP_ONLY_FLAGS]


def _message_content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, Mapping):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            elif item is not None:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _prompt_from_messages(messages: Iterable[Mapping[str, Any]] | None) -> str:
    chunks: list[str] = []
    for message in messages or []:
        role = str(message.get("role") or "user")
        content = _message_content_text(message.get("content"))
        if content:
            chunks.append(f"{role}: {content}" if role != "user" else content)
    return "\n\n".join(chunks)


class LocalCLIClient:
    """A minimal OpenAI Chat Completions-compatible local CLI client."""

    supports_streaming = False

    def __init__(
        self,
        *,
        command: str | None = None,
        args: Optional[list[str]] = None,
        base_url: str | None = None,
        timeout: int | float | None = None,
        **_: Any,
    ) -> None:
        self.command = command or self._command_from_base_url(base_url) or "claude"
        self.args = list(args or [])
        self.timeout = timeout or 300
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    @staticmethod
    def _command_from_base_url(base_url: str | None) -> str | None:
        prefix = "local-cli://"
        text = str(base_url or "")
        if text.startswith(prefix):
            return text[len(prefix) :] or None
        return None

    def _argv(self, prompt: str) -> list[str]:
        name = normalized_local_cli_name(self.command)
        args = _strip_acp_only_args(self.args)
        if name == "claude":
            return [
                self.command,
                "-p",
                prompt,
                "--output-format",
                "text",
                "--permission-mode",
                "bypassPermissions",
                *args,
            ]
        if name == "codex":
            return [
                self.command,
                "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                *args,
                prompt,
            ]
        return [self.command, *self.args, prompt]

    def _create(self, *, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        prompt = _prompt_from_messages(messages)
        argv = self._argv(prompt)
        timeout = kwargs.get("timeout") or self.timeout
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"local CLI timed out after {timeout}s: {self.command}") from exc
        except TimeoutError as exc:
            raise TimeoutError(f"local CLI timed out after {timeout}s: {self.command}") from exc

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        if proc.returncode != 0:
            tail = stderr[-4000:] if stderr else stdout[-4000:]
            raise RuntimeError(
                f"local CLI command {self.command!r} exited with code {proc.returncode}. "
                f"stderr tail: {tail}"
            )

        content = stdout.strip()
        return SimpleNamespace(
            id="local-cli-response",
            object="chat.completion",
            created=0,
            model=model,
            choices=[
                SimpleNamespace(
                    index=0,
                    finish_reason="stop",
                    message=SimpleNamespace(
                        role="assistant",
                        content=content,
                        tool_calls=None,
                    ),
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
            ),
        )
