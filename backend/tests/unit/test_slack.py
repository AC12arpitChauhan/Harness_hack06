"""Slack build-failure alerts: disabled-by-default, correct payload, deduped. No network."""
from __future__ import annotations

from app.config import Settings
from app.services import slack_service


def _settings(**kw) -> Settings:
    return Settings(**kw)


def test_disabled_is_noop(monkeypatch):
    slack_service.reset_dedupe()
    posted = []
    monkeypatch.setattr(slack_service, "_post", lambda url, payload: posted.append(payload) or True)
    s = _settings(slack_webhook_url="")
    ok = slack_service.notify_build_failed(
        s, number=12, title="t", target="main", author="a", failing_checks=["build"]
    )
    assert ok is False
    assert posted == []  # never attempted a post


def test_enabled_posts_expected_payload(monkeypatch):
    slack_service.reset_dedupe()
    captured: dict = {}
    monkeypatch.setattr(
        slack_service, "_post", lambda url, payload: (captured.update(url=url, payload=payload), True)[1]
    )
    s = _settings(slack_webhook_url="https://hooks.slack.com/services/x")
    ok = slack_service.notify_build_failed(
        s,
        number=12,
        title="Add cache",
        target="main",
        author="alice",
        failing_checks=["ci/unit", "ci/lint"],
        pr_url="https://github.com/o/r/pull/12",
        fix_url="https://dash/repos/R/prs/P",
        dedupe_key="P:sha",
    )
    assert ok is True
    text = captured["payload"]["blocks"][0]["text"]["text"]
    assert "PR #12" in text and "Add cache" in text
    assert "ci/unit, ci/lint" in text
    assert "View PR" in text and "AI fix suggestion" in text


def test_dedupe_sends_once(monkeypatch):
    slack_service.reset_dedupe()
    posts = []
    monkeypatch.setattr(slack_service, "_post", lambda url, payload: posts.append(payload) or True)
    s = _settings(slack_webhook_url="https://hooks.slack.com/services/x")
    args = dict(number=1, title="t", target="main", author="a", failing_checks=["b"], dedupe_key="P:sha")
    assert slack_service.notify_build_failed(s, **args) is True
    assert slack_service.notify_build_failed(s, **args) is False  # same key -> skipped
    assert len(posts) == 1
