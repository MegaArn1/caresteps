"""Environment-driven configuration.

Everything the app needs to decide "can I talk to a model?" lives here, and nothing
else does. The rest of the app never reads os.environ directly, so there is exactly
one place to audit for secret handling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent

# Load .env from the project root if it exists. This is intentionally simple:
# we only set variables that are not already present in the environment, so a
# real deployment's platform-injected values always win over the file.
_dotenv = PROJECT_ROOT / ".env"
if _dotenv.exists():
    for _line in _dotenv.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _k = _k.strip()
        _v = _v.strip().strip('"').strip("'")
        if _k and _k not in os.environ:
            os.environ[_k] = _v
CONTENT_DIR = PROJECT_ROOT / "content"
DEMO_DATA_DIR = PROJECT_ROOT / "demo-data"
DB_PATH = Path(os.environ.get("CARESTEPS_DB", PROJECT_ROOT / "caresteps.db"))


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


@dataclass(frozen=True)
class LLMSettings:
    """Model endpoint configuration.

    The app speaks one wire format: OpenAI-compatible /v1/chat/completions with
    function calling. Any gateway that speaks it works, which keeps us decoupled
    from a specific vendor.
    """

    base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL"))
    api_key: str = field(default_factory=lambda: _env("LLM_API_KEY"))
    model: str = field(default_factory=lambda: _env("LLM_MODEL"))
    timeout_s: float = field(default_factory=lambda: float(_env("LLM_TIMEOUT_S", "30")))
    max_tool_rounds: int = field(default_factory=lambda: int(_env("LLM_MAX_TOOL_ROUNDS", "4")))

    # Force degraded mode regardless of configuration. Used to demo and test the
    # fallback path without unplugging the network.
    force_degraded: bool = field(
        default_factory=lambda: _env("LLM_FORCE_DEGRADED", "").lower() in {"1", "true", "yes"}
    )

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)

    @property
    def live(self) -> bool:
        """Whether the orchestrator should attempt real model calls."""
        return self.configured and not self.force_degraded

    def describe(self) -> dict:
        """Safe-to-display status. Never includes the key itself."""
        return {
            "configured": self.configured,
            "live": self.live,
            "degraded": not self.live,
            "model": self.model or None,
            "base_url_host": _host_of(self.base_url),
            "api_key_present": bool(self.api_key),
            "reason": (
                "forced off by LLM_FORCE_DEGRADED"
                if self.force_degraded
                else (None if self.live else "LLM_BASE_URL / LLM_MODEL not set")
            ),
        }


def _host_of(url: str) -> str | None:
    if not url:
        return None
    try:
        from urllib.parse import urlparse

        return urlparse(url).hostname
    except Exception:
        return None


@dataclass(frozen=True)
class Settings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    db_path: Path = field(default_factory=lambda: DB_PATH)
    app_name: str = "CareSteps"
    challenge_label: str = (
        "Healthcare Track - Challenge Statement 2: AI Healthier Every Day"
    )
    # Session handling. The prototype is single-user-per-browser-session; see
    # docs/architecture.md for why this is sufficient and what it does not claim.
    session_cookie: str = "caresteps_session"


SETTINGS = Settings()
