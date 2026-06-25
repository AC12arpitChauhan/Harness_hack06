"""Prompt templates for the Anthropic narrator.

The system prompt forbids inventing or recomputing metrics: the model only
narrates the numbers it is handed.
"""
from __future__ import annotations

from app.domain.models import PullRequest
from app.domain.scores import Score
from app.domain.signals import AnalysisSignal, Severity

SYSTEM = (
    "You are a senior engineer writing a concise pull-request health review for a teammate. "
    "You are given pre-computed scores and signals. NEVER invent, recompute, or contradict any "
    "score or metric — describe only what you are given. Be specific and actionable. "
    "Output EXACTLY two sections in this format:\n"
    "SUMMARY: <2-3 sentences>\n"
    "RECOMMENDATION: <1-3 short, actionable bullet points, each on its own line starting with '- '>"
)


# --- AI "fix this failing build" suggester (distinct from the health narrative) ---
SUGGEST_FIX_SYSTEM = (
    "You are a senior CI/build engineer helping a developer get a failing pull "
    "request build to pass. You are given the PR title, the failing checks (with any "
    "summaries), the CHANGED FILES, and CI signal detail. USE ALL OF IT. If no raw "
    "log is available, infer the most likely causes from the changed files and the "
    "check summaries — and if a failing check looks UNRELATED to the diff (e.g. a "
    "docs-only change with a build failure), say so explicitly (likely flaky / "
    "pre-existing / misconfigured pipeline) rather than guessing at the code. "
    "Respond with: (1) one line naming the most likely cause, then (2) numbered, "
    "concrete fix steps with code/config snippets where useful. Be concise and "
    "specific. Do NOT fabricate specific log lines you were not given."
)


def build_fix_user(
    failing_checks: list[dict], pr_title: str | None = None, log_text: str | None = None
) -> str:
    """User prompt for SUGGEST_FIX_SYSTEM. ``failing_checks`` are {name, status, url, summary}
    dicts; ``log_text`` carries extra context (changed files, CI signal detail, description)."""
    lines: list[str] = []
    if pr_title:
        lines.append(f"PR title: {pr_title}")
    lines.append("Failing checks:")
    for c in failing_checks or []:
        name = c.get("name") or "(unnamed check)"
        status = c.get("status")
        line = f"  - {name}" + (f" [{status}]" if status else "")
        if c.get("summary"):
            line += f" — {c['summary']}"
        lines.append(line)
    if log_text:
        lines.append("\nContext:\n" + log_text[-4000:])
    lines.append(
        "\nUsing the title, failing checks, and context above, give concrete steps to make this build pass."
    )
    return "\n".join(lines)


def templated_fix(failing_checks: list[dict], pr_title: str | None = None) -> str:
    """Deterministic, no-LLM fix guidance — used when the LLM is disabled or errors,
    so the feature still returns something useful (mirrors the templated narrator)."""
    names = [(c.get("name") or "check") for c in (failing_checks or [])]
    if not names:
        return "No failing checks were found on this PR."
    head = f"{len(names)} check(s) failing: " + ", ".join(names) + "."
    steps = [
        "1. Open each failing check's log (link in the PR) and read the FIRST error, not the last.",
        "2. Reproduce locally with the exact command the CI step runs (test / lint / build).",
        "3. Test failures: run just the failing test, fix or update it, then re-run the full suite.",
        "4. Lint/format failures: run the formatter/linter locally and commit the fixes.",
        "5. Build/dependency failures: confirm versions and lockfiles match CI; clear stale caches.",
        "6. Push the fix — the checks re-run automatically.",
    ]
    return head + "\n\n" + "\n".join(steps) + (
        "\n\n_(Heuristic guidance — enable the LLM for a cause-specific suggestion.)_"
    )


def build_user(pr: PullRequest, signals: list[AnalysisSignal], score: Score) -> str:
    notable = [s for s in signals if s.severity is not Severity.INFO or s.exceeds_threshold]
    notable.sort(key=lambda s: s.severity.value)
    signal_lines = "\n".join(
        f"- [{s.severity.value.upper()}] {s.key}: {s.explanation}" for s in notable
    ) or "- (no notable issues)"
    blocker = score.blocking_reason or "none"
    return (
        f"PR #{pr.number}: {pr.title}\n"
        f"Author: {pr.author} | {pr.source_branch} -> {pr.target_branch} | state: {pr.state.value}\n\n"
        f"Scores (0-100, do not change these):\n"
        f"- health: {score.health_score}\n"
        f"- risk: {score.risk_score}\n"
        f"- review_quality: {score.review_quality_score}\n"
        f"- merge_readiness: {score.merge_readiness}\n"
        f"- hard blocker: {blocker}\n\n"
        f"Signals:\n{signal_lines}\n"
    )
