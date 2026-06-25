"""Repository-baseline anomaly: math module, analyzer, and engine deduction."""
from __future__ import annotations

from app.analyzers.baseline_anomaly import BaselineAnomalyAnalyzer
from app.domain.models import AnalysisContext, MetricBaseline, RepoBaseline
from app.domain.signals import AnalysisSignal, Severity
from app.scoring.baseline import MIN_HISTORY, build_repo_baseline
from app.scoring.engine import DEFAULT_BASELINE_MAX_PENALTY, ScoringEngine

from tests.unit._builders import make_diff, make_pr, review
from app.domain.models import ReviewState


# --- pure baseline math ---------------------------------------------------
def test_build_baseline_none_without_enough_history():
    short = [100.0] * (MIN_HISTORY - 1)
    assert build_repo_baseline(short, short, short) is None


def test_build_baseline_none_when_no_spread():
    flat = [100.0] * (MIN_HISTORY + 2)
    # zero std on every metric => no usable baseline
    assert build_repo_baseline(flat, flat, flat) is None


def test_build_baseline_computes_mean_and_std():
    sizes = [80.0, 90.0, 100.0, 110.0, 120.0]
    baseline = build_repo_baseline(sizes, [1.0, 2.0, 2.0, 3.0, 2.0], [])
    assert baseline is not None
    assert baseline.size is not None and baseline.size.n == 5
    assert baseline.size.mean == 100.0
    assert baseline.merge_minutes is None  # no samples


# --- analyzer -------------------------------------------------------------
def _ctx(diff=None, reviews=None, baseline=None) -> AnalysisContext:
    return AnalysisContext(diff=diff or make_diff(), reviews=reviews or [], baseline=baseline)


def test_analyzer_reports_insufficient_history_without_baseline():
    sigs = BaselineAnomalyAnalyzer().analyze(make_pr(), _ctx(baseline=None))
    assert [s.key for s in sigs] == ["baseline_anomaly.insufficient_history"]
    assert sigs[0].severity is Severity.INFO


def test_analyzer_flags_size_outlier():
    baseline = RepoBaseline(size=MetricBaseline(n=10, mean=100.0, std=20.0))
    # 160 lines == +3 sigma => HIGH
    sigs = BaselineAnomalyAnalyzer().analyze(make_pr(), _ctx(diff=make_diff(additions=160), baseline=baseline))
    assert sigs[0].key == "baseline_anomaly.size_outlier"
    assert sigs[0].severity is Severity.HIGH
    assert sigs[0].metadata["z_score"] == 3.0


def test_analyzer_flags_thin_review_outlier():
    baseline = RepoBaseline(reviewers=MetricBaseline(n=10, mean=3.0, std=1.0))
    # 0 reviewers == -3 sigma below norm => HIGH
    sigs = BaselineAnomalyAnalyzer().analyze(make_pr(), _ctx(reviews=[], baseline=baseline))
    assert sigs[0].key == "baseline_anomaly.thin_review_outlier"
    assert sigs[0].severity is Severity.HIGH


def test_analyzer_flags_fast_merge_outlier():
    baseline = RepoBaseline(merge_minutes=MetricBaseline(n=10, mean=120.0, std=20.0))
    pr = make_pr(merged=True, merged_after_min=20)  # 20 min == -5 sigma
    sigs = BaselineAnomalyAnalyzer().analyze(pr, _ctx(baseline=baseline))
    assert sigs[0].key == "baseline_anomaly.fast_merge_outlier"
    assert sigs[0].severity is Severity.HIGH


def test_analyzer_within_norms_does_not_flag():
    baseline = RepoBaseline(
        size=MetricBaseline(n=10, mean=100.0, std=20.0),
        reviewers=MetricBaseline(n=10, mean=2.0, std=1.0),
    )
    ctx = _ctx(
        diff=make_diff(additions=100),
        reviews=[review("x", ReviewState.APPROVED), review("y", ReviewState.APPROVED)],
        baseline=baseline,
    )
    sigs = BaselineAnomalyAnalyzer().analyze(make_pr(), ctx)
    assert [s.key for s in sigs] == ["baseline_anomaly.within_norms"]
    assert sigs[0].severity is Severity.INFO


def test_analyzer_ignores_safe_direction():
    # A much SMALLER-than-norm change is not risky => no signal for size.
    baseline = RepoBaseline(size=MetricBaseline(n=10, mean=500.0, std=50.0))
    sigs = BaselineAnomalyAnalyzer().analyze(make_pr(), _ctx(diff=make_diff(additions=10), baseline=baseline))
    assert [s.key for s in sigs] == ["baseline_anomaly.within_norms"]


# --- engine deduction -----------------------------------------------------
def _sig(name, severity):
    return AnalysisSignal(analyzer="baseline_anomaly", name=name, severity=severity, explanation="x")


def test_engine_deducts_for_baseline_signal():
    score = ScoringEngine().compute([_sig("size_outlier", Severity.HIGH)])
    # HIGH penalty 30, capped at DEFAULT_BASELINE_MAX_PENALTY (20)
    assert score.health_score == 100.0 - DEFAULT_BASELINE_MAX_PENALTY
    bd = score.breakdown.as_dict()
    assert bd["components"]["baseline_adjustment"]["penalty"] == DEFAULT_BASELINE_MAX_PENALTY
    assert bd["components"]["health"]["base_value"] == 100.0


def test_engine_baseline_penalty_is_capped():
    # Two HIGH outliers (60 raw) still cap at the max.
    signals = [_sig("size_outlier", Severity.HIGH), _sig("thin_review_outlier", Severity.HIGH)]
    score = ScoringEngine().compute(signals)
    assert score.health_score == 100.0 - DEFAULT_BASELINE_MAX_PENALTY


def test_engine_no_deduction_when_within_norms():
    score = ScoringEngine().compute([_sig("within_norms", Severity.INFO)])
    assert score.health_score == 100.0
