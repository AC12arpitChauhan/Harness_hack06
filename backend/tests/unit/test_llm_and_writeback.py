"""LLM narration + writeback. Proves scores never depend on the LLM, and that
writeback is gated by WRITEBACK_ENABLED. No network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.analyzers.registry import enabled_analyzers
from app.domain.models import (
    Check,
    Commit,
    Diff,
    DiffFile,
    PRRef,
    PRState,
    PullRequest,
    Review,
    ReviewState,
)
from app.llm.base import LLMProvider, Narrative
from app.llm.templated_fallback import TemplatedNarrator
from app.providers.base import SCMProvider
from app.scoring.engine import ScoringEngine
from app.services import analysis_service
from app.services.writeback_service import do_writeback

_OPENED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------- helpers
def _pr(number=1):
    return PullRequest(
        provider="github", repo="o/r", number=number, title="Add feature", description="",
        author="alice", state=PRState.MERGED, source_branch="f", target_branch="main",
        commit_sha="sha1", opened_at=_OPENED, merged_at=_OPENED + timedelta(minutes=200),
    )


class HealthyProvider(SCMProvider):
    name = "github"

    def get_pull_request(self, repo, pr_id):
        return _pr(pr_id)

    def get_diff(self, repo, pr_id):
        return Diff(files_changed=2, additions=40, deletions=10,
                    files=[DiffFile("a.py", 40, 10, "modified")])

    def get_reviews(self, repo, pr_id):
        return [Review("bob", ReviewState.APPROVED), Review("cara", ReviewState.APPROVED)]

    def get_checks(self, repo, sha):
        from app.domain.models import CheckStatus
        return [Check("build", CheckStatus.SUCCESS, required=True)]

    def get_commits(self, repo, pr_id):
        return [Commit("sha1", "alice", "msg")]

    def list_pull_requests(self, repo, since):
        return [PRRef("github", repo, 1)]

    def post_comment(self, repo, pr_id, body):
        pass

    def set_status(self, repo, sha, state, context, description):
        pass


class RecordingProvider(HealthyProvider):
    def __init__(self):
        self.comments = []
        self.statuses = []

    def post_comment(self, repo, pr_id, body):
        self.comments.append((repo, pr_id, body))

    def set_status(self, repo, sha, state, context, description):
        self.statuses.append((repo, sha, state, context, description))


class FakeLLMNarrator(LLMProvider):
    """Simulates LLM_ENABLED=true without a network call."""

    def narrate(self, pr, signals, score):
        return Narrative(summary="LLM summary", recommendation="- LLM rec", model="claude-opus-4-8")


def _run(repository):
    return analysis_service.run_analysis(
        "o/r", 1, provider=HealthyProvider(), repository=repository,
        analyzers=enabled_analyzers(), engine=ScoringEngine(),
    )


# ---------------------------------------------------------------- templated narrator
def test_templated_narrator_is_deterministic_and_mentions_scores():
    pr = _pr()
    signals = enabled_analyzers()
    sigs = [s for a in signals for s in a.analyze(pr, analysis_service.AnalysisContext(
        diff=Diff(files_changed=1, additions=2000, deletions=0)))]
    score = ScoringEngine().compute(sigs)
    n1 = TemplatedNarrator().narrate(pr, sigs, score)
    n2 = TemplatedNarrator().narrate(pr, sigs, score)
    assert n1 == n2
    assert f"{score.health_score:.0f}/100" in n1.summary
    assert n1.model == "templated-fallback"


# ---------------------------------------------------------------- anthropic narrator (mocked)
def test_anthropic_narrator_parses_sections(monkeypatch):
    import app.llm.anthropic_provider as ap

    canned = SimpleNamespace(
        model="claude-opus-4-8",
        content=[SimpleNamespace(type="text", text="SUMMARY: Looks risky.\nRECOMMENDATION: - add tests")],
    )
    fake_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: canned))
    monkeypatch.setattr(ap.anthropic, "Anthropic", lambda **kw: fake_client)

    narrator = ap.AnthropicNarrator(api_key="x", model="claude-opus-4-8")
    pr = _pr()
    score = ScoringEngine().compute([])
    n = narrator.narrate(pr, [], score)
    assert n.summary == "Looks risky."
    assert n.recommendation == "- add tests"
    assert n.model == "claude-opus-4-8"


# ---------------------------------------------------------------- the key guarantee
def test_scores_identical_regardless_of_llm(repository):
    result = _run(repository)
    before = (
        result.score.health_score,
        result.score.review_quality_score,
        result.score.merge_readiness,
    )

    # LLM_ENABLED=false path (templated) then a simulated LLM_ENABLED=true path.
    for narrator in (TemplatedNarrator(), FakeLLMNarrator()):
        analysis_service.post_analysis(
            result, "o/r", narrator=narrator, repository=repository,
            provider=RecordingProvider(), writeback_enabled=False, ready_threshold=70.0,
        )
        row = repository.latest_score_for_pr(result.pr_id)
        assert (row.health_score, row.review_quality_score, row.merge_readiness) == before

    # a narrative was persisted (last writer wins)
    assert repository.narrative_for_pr(result.pr_id) is not None


# ---------------------------------------------------------------- writeback toggle
def test_writeback_disabled_makes_no_calls(repository):
    result = _run(repository)
    rec = RecordingProvider()
    do_writeback(rec, "o/r", result.pull_request, result.score,
                 Narrative("s", "r", "templated-fallback"), enabled=False, ready_threshold=70.0)
    assert rec.comments == [] and rec.statuses == []


def test_writeback_enabled_posts_comment_and_status(repository):
    result = _run(repository)
    rec = RecordingProvider()
    do_writeback(rec, "o/r", result.pull_request, result.score,
                 Narrative("s", "r", "templated-fallback"), enabled=True, ready_threshold=70.0)
    assert len(rec.comments) == 1
    assert len(rec.statuses) == 1
    # healthy PR -> success status in the "pr-health" context
    assert rec.statuses[0][2] == "success"
    assert rec.statuses[0][3] == "pr-health"
