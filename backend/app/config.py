"""Application configuration — the single env-driven settings home.

EDGE module (imports pydantic-settings). It MAY import the pure core inward:
the canonical scoring weights / severity penalties live in ``app.scoring.engine``
and are re-exposed here so every tunable knob is reachable from one place, while
the core remains the single source of truth for their default values.

Settings load from environment variables and an optional ``.env`` file.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
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
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"  # cost flip: claude-sonnet-4-6
    llm_max_tokens: int = 1024

    # --- Writeback (GitHub comment + status check) -----------------------
    writeback_enabled: bool = False

    # --- CI analysis -----------------------------------------------------
    # Names of checks treated as "required". Empty => every check is required.
    required_checks: list[str] = []

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

    @field_validator("required_checks", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        """Allow REQUIRED_CHECKS to be a comma-separated env string."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

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
