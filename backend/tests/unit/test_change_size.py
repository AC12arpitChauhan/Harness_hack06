"""change_size analyzer boundary cases."""
from __future__ import annotations

from app.analyzers.change_size import ChangeSizeAnalyzer
from app.domain.signals import Severity
from tests.unit._builders import make_ctx, make_diff, make_pr

PR = make_pr()


def _band(additions, deletions=0, files=1):
    ctx = make_ctx(make_diff(additions, deletions, files))
    sigs = ChangeSizeAnalyzer().analyze(PR, ctx)
    return {s.name: s for s in sigs}


def test_small_diff_is_info():
    sigs = _band(6)
    assert sigs["small_diff"].severity is Severity.INFO
    assert sigs["small_diff"].exceeds_threshold is False


def test_medium_diff():
    assert _band(300)["large_diff"].severity is Severity.MEDIUM


def test_high_diff():
    assert _band(600)["large_diff"].severity is Severity.HIGH


def test_critical_diff():
    s = _band(1500)["large_diff"]
    assert s.severity is Severity.CRITICAL
    assert s.value == 1500.0


def test_many_files_emits_extra_signal():
    sigs = _band(100, files=40)
    assert "many_files" in sigs
    assert sigs["many_files"].severity is Severity.MEDIUM
    assert sigs["many_files"].value == 40.0
