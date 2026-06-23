"""Application configuration — the single env-driven settings home.

EDGE module (imports pydantic-settings). It MAY import the pure core inward:
the canonical scoring weights / severity penalties live in ``app.scoring.engine``
and are re-exposed here so every tunable knob is reachable from one place, while
the core remains the single source of truth for their default values.

Settings load from environment variables and an optional ``.env`` file.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.scoring.engine import (
    DEFAULT_BLOCKED_CAP,
    DEFAULT_HEALTH_WEIGHTS,
    DEFAULT_RISK_WEIGHTS,
    DEFAULT_SEVERITY_PENALTIES,
)


class Settings(BaseSettings):
    """Env-driven configuration. Field names map to UPPER_SNAKE env vars."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Persistence -----------------------------------------------------
    database_url: str = "sqlite:///./dev.db"

    # --- Auth ------------------------------------------------------------
    fastapi_auth_token: str = "dev-token"  # override in prod; gate on POST routes

    # --- CORS (dashboard frontend) ---------------------------------------
    cors_allow_origins: str = "*"  # comma-separated origins; "*" allows all (demo default)

    # --- GitHub provider -------------------------------------------------
    github_token: str = ""
    github_api_url: str = "https://api.github.com"

    # --- Harness SCM provider (interface-complete this round) ------------
    harness_token: str = ""
    harness_api_url: str = "https://app.harness.io"
    harness_account_id: str = ""
    harness_org_id: str = ""
    harness_project_id: str = ""

    # --- LLM (narration only; never influences scores) -------------------
    llm_enabled: bool = False
    llm_backend: str = "anthropic"  # "anthropic" (direct) | "bedrock" (Amazon Bedrock)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"  # cost flip: claude-sonnet-4-6
    llm_max_tokens: int = 1024

    # --- Bedrock (used when LLM_BACKEND=bedrock) --------------------------
    bedrock_region: str = "us-east-1"
    # Bedrock needs an INFERENCE-PROFILE id (geo-prefixed), not the bare model id.
    # us-east-1 -> "us."; for EU/APAC regions use "eu."/"apac." prefixes.
    bedrock_model: str = "us.anthropic.claude-sonnet-4-6"
    bedrock_api_key: str = ""  # Bedrock API key (bearer); falls back to ANTHROPIC_API_KEY if empty

    # --- Writeback (GitHub comment + status check) -----------------------
    writeback_enabled: bool = False

    # --- Slack alerts (build-failure notifications) ----------------------
    # Disabled until SLACK_WEBHOOK_URL is set (graceful no-op). DASHBOARD_URL is
    # the public dashboard base used to build the "AI fix" deep link in alerts.
    slack_webhook_url: str = ""
    dashboard_url: str = ""

    # --- CI analysis -----------------------------------------------------
    # Comma-separated names treated as "required". Empty => every check is required.
    # Kept as a raw string (not list[str]) so an empty REQUIRED_CHECKS= in .env
    # doesn't trip pydantic-settings' JSON decoding of complex fields. Use the
    # `required_checks_list` property to get the parsed list.
    required_checks: str = ""

    # --- Scoring: merge-readiness gate -----------------------------------
    ready_threshold: float = 70.0  # merge_readiness >= this AND no blocker => ready

    # --- Analyzer thresholds (env-overridable; defaults documented) ------
    merge_fast_minutes: int = 15        # open->merge faster than this => CRITICAL (rubber-stamp)
    merge_slow_minutes: int = 60        # faster than this (but >= fast) => HIGH
    change_medium_lines: int = 250      # additions+deletions
    change_high_lines: int = 500
    change_critical_lines: int = 1000
    change_high_files: int = 30         # files_changed
    review_trivial_lines: int = 10      # <= this many changed lines => un-reviewed PR doesn't block
    review_thin_reviewers: int = 2      # fewer distinct reviewers than this => thin review

    @property
    def required_checks_list(self) -> list[str]:
        """REQUIRED_CHECKS parsed from comma-separated string into a list."""
        return [c.strip() for c in self.required_checks.split(",") if c.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ALLOW_ORIGINS parsed; '*' (or empty) means allow all."""
        v = self.cors_allow_origins.strip()
        if not v or v == "*":
            return ["*"]
        return [o.strip() for o in v.split(",") if o.strip()]

    @property
    def slack_enabled(self) -> bool:
        """Slack alerts fire only when a webhook URL is configured."""
        return bool(self.slack_webhook_url.strip())

    # --- Scoring weights (single source of truth lives in scoring/engine.py) ---
    @property
    def health_weights(self) -> dict[str, float]:
        return dict(DEFAULT_HEALTH_WEIGHTS)

    @property
    def risk_weights(self) -> dict[str, float]:
        return dict(DEFAULT_RISK_WEIGHTS)

    @property
    def severity_penalties(self) -> dict[str, float]:
        return {sev.value: pts for sev, pts in DEFAULT_SEVERITY_PENALTIES.items()}

    @property
    def blocked_cap(self) -> float:
        return DEFAULT_BLOCKED_CAP


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (one instance per process)."""
    return Settings()
