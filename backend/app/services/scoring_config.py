"""Effective scoring config = engine defaults overlaid with the team's override.

A single global override row (orm.ScoringConfig) lets a team personalize which
parameters weigh more/less and where each signal trips. When unset, the documented
engine defaults apply. The effective config is fed into the analyzers + engine at
analyze time, so it changes how FUTURE analyses score — the deterministic core
(app.scoring.engine) is itself untouched.

This module also sanitizes incoming overrides (drop unknown keys, fill missing
ones from defaults, normalize weights to sum 1.0) so a bad payload can never
produce an out-of-range score.
"""
from __future__ import annotations

from app.config import Settings
from app.persistence.repository import Repository

# Analyzer thresholds a team may personalize (names match Settings fields exactly).
THRESHOLD_KEYS = (
    "merge_fast_minutes",
    "merge_slow_minutes",
    "change_medium_lines",
    "change_high_lines",
    "change_critical_lines",
    "change_high_files",
    "review_trivial_lines",
    "review_thin_reviewers",
)


def default_config(settings: Settings) -> dict:
    """The documented engine defaults, in the same shape as an effective config."""
    return {
        "health_weights": dict(settings.health_weights),
        "thresholds": {k: float(getattr(settings, k)) for k in THRESHOLD_KEYS},
    }


def _overlay(defaults: dict[str, float], override: dict | None) -> dict[str, float]:
    """Per-key overlay: take the override value where it's a valid number, else default.
    Only keys present in ``defaults`` survive, so a stale override can't add phantoms."""
    out = dict(defaults)
    if override:
        for key in defaults:
            value = override.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[key] = float(value)
    return out


def effective_config(settings: Settings, repository: Repository) -> dict:
    """Defaults overlaid with the stored override (if any).

    ``customized`` flags whether a team override is active, so the UI can show
    "team settings" vs "defaults".
    """
    base = default_config(settings)
    row = repository.get_scoring_config()
    if row is None:
        return {**base, "customized": False}
    return {
        "health_weights": _overlay(base["health_weights"], row.health_weights_json),
        "thresholds": _overlay(base["thresholds"], row.thresholds_json),
        "customized": True,
    }


def sanitize_weights(submitted: dict, defaults: dict[str, float]) -> dict[str, float]:
    """Coerce a submitted weight map to non-negative numbers over the known keys,
    then normalize to sum 1.0. Falls back to defaults if nothing usable was sent."""
    cleaned: dict[str, float] = {}
    for key in defaults:
        value = submitted.get(key, defaults[key])
        cleaned[key] = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else 0.0
    total = sum(cleaned.values())
    if total <= 0:
        return dict(defaults)
    return {key: value / total for key, value in cleaned.items()}


def sanitize_thresholds(submitted: dict, settings: Settings) -> dict[str, float]:
    """Coerce submitted thresholds to non-negative numbers over the known keys,
    falling back to the default for any missing/invalid value."""
    out: dict[str, float] = {}
    for key in THRESHOLD_KEYS:
        default = float(getattr(settings, key))
        value = submitted.get(key, default)
        out[key] = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else default
    return out
