"""Model provider adapter.

One wire format: OpenAI-compatible ``POST /v1/chat/completions`` with function
calling. Keeping to a single, widely-implemented format means the prototype is not
tied to a vendor, and it means the adapter is small enough to audit.

Failure is a first-class outcome, not an exception that escapes. Every call returns a
``LLMResult`` that says whether it worked, and the orchestrator decides what to do.
A dead endpoint degrades the app; it does not break it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import SETTINGS


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    raw_arguments: str = ""


@dataclass
class LLMResult:
    ok: bool
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    error: str | None = None
    model: str | None = None
    usage: dict | None = None
    # Wall-clock duration of the HTTP call, surfaced so the trace page can show
    # real latency for the evaluation notes.
    elapsed_ms: int | None = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMUnavailable(RuntimeError):
    """Raised only by ``complete_or_raise``. Normal callers use ``complete``."""


class Provider:
    """Thin client for an OpenAI-compatible chat endpoint."""

    def __init__(self, settings=None):
        self.s = settings or SETTINGS.llm
        self._client: httpx.Client | None = None

    # -------------------------------------------------------------- lifecycle

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            # Trust env proxies; the timeout is deliberately generous because the
            # demo machine may be behind a slow network and a timeout here produces
            # a user-visible failure.
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.s.timeout_s, connect=10.0),
                headers=self._headers(),
                follow_redirects=True,
            )
        return self._client

    def _headers(self) -> dict[str, str]:
        h = {"content-type": "application/json"}
        if self.s.api_key:
            h["authorization"] = f"Bearer {self.s.api_key}"
        return h

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------ calls

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 900,
    ) -> LLMResult:
        """Make one completion call. Never raises for network/HTTP problems."""
        if not self.s.live:
            return LLMResult(
                ok=False,
                error=(
                    "No model endpoint is configured "
                    f"({self.s.describe().get('reason') or 'unknown reason'})"
                ),
            )

        payload: dict[str, Any] = {
            "model": self.s.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        # Only include temperature if it's supported by the model
        # Some models (e.g., claude-sonnet-5-5) don't support temperature parameter
        if temperature != 0.2 or not self.s.model.startswith("claude-sonnet-5"):
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        import time

        started = time.monotonic()
        try:
            resp = self.client.post(
                f"{self.s.base_url.rstrip('/')}/chat/completions", json=payload
            )
        except httpx.TimeoutException:
            return LLMResult(ok=False, error=f"The model did not respond within {self.s.timeout_s:.0f}s")
        except httpx.HTTPError as exc:
            return LLMResult(ok=False, error=f"Could not reach the model service: {type(exc).__name__}")
        except Exception as exc:  # pragma: no cover - defensive
            return LLMResult(ok=False, error=f"Unexpected model error: {type(exc).__name__}")

        elapsed = int((time.monotonic() - started) * 1000)

        if resp.status_code >= 400:
            return LLMResult(
                ok=False,
                error=f"The model service returned HTTP {resp.status_code}",
                elapsed_ms=elapsed,
            )

        try:
            body = resp.json()
        except Exception:
            return LLMResult(
                ok=False, error="The model service returned a response we could not read",
                elapsed_ms=elapsed,
            )

        try:
            choice = (body.get("choices") or [{}])[0]
            message = choice.get("message") or {}
        except Exception:
            return LLMResult(ok=False, error="Unexpected response shape", elapsed_ms=elapsed)

        calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            raw = fn.get("arguments") or "{}"
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except json.JSONDecodeError:
                # A malformed argument string is a model failure, not a crash. The
                # orchestrator will see a call whose arguments failed to parse and
                # can respond without executing anything.
                parsed = {"__parse_error__": raw[:500]}
            calls.append(
                ToolCall(
                    id=tc.get("id") or "call_0",
                    name=fn.get("name") or "unknown",
                    arguments=parsed,
                    raw_arguments=raw if isinstance(raw, str) else json.dumps(raw),
                )
            )

        return LLMResult(
            ok=True,
            content=(message.get("content") or "").strip(),
            tool_calls=calls,
            finish_reason=choice.get("finish_reason"),
            model=body.get("model"),
            usage=body.get("usage"),
            elapsed_ms=elapsed,
        )

    def complete_or_raise(self, *args, **kwargs) -> LLMResult:
        result = self.complete(*args, **kwargs)
        if not result.ok:
            raise LLMUnavailable(result.error or "model unavailable")
        return result


_PROVIDER: Provider | None = None


def get_provider() -> Provider:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = Provider()
    return _PROVIDER
