"""Repository — the ONLY module that issues SQL.

Methods operate on a single Session and flush (to populate UUID PKs and satisfy
FKs) but do NOT commit; the caller (analysis_service) owns the transaction so the
whole run persists atomically. Domain objects come in; ORM rows go out.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.domain.models import Check, Diff, PullRequest, Review
from app.domain.scores import Score
from app.domain.signals import AnalysisSignal
from app.persistence import orm


def _naive(dt: datetime | None) -> datetime | None:
    """Normalize to naive UTC for cross-dialect storage."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ writes
    def upsert_repository(self, provider: str, provider_id: str, name: str, url: str) -> orm.Repository:
        row = self.session.scalar(
            select(orm.Repository).where(
                orm.Repository.provider == provider,
                orm.Repository.provider_id == provider_id,
            )
        )
        if row is None:
            row = orm.Repository(provider=provider, provider_id=provider_id, name=name, url=url)
            self.session.add(row)
        else:
            row.name = name or row.name
            row.url = url or row.url
        self.session.flush()
        return row

    def upsert_pull_request(self, repo_id: str, pr: PullRequest) -> orm.PullRequest:
        row = self.session.scalar(
            select(orm.PullRequest).where(
                orm.PullRequest.repo_id == repo_id,
                orm.PullRequest.provider_pr_id == (pr.provider_pr_id or str(pr.number)),
            )
        )
        if row is None:
            row = orm.PullRequest(repo_id=repo_id, provider_pr_id=pr.provider_pr_id or str(pr.number))
            self.session.add(row)
        row.provider = pr.provider
        row.title = pr.title
        row.description = pr.description
        row.author = pr.author
        row.state = pr.state.value
        row.opened_at = _naive(pr.opened_at)
        row.merged_at = _naive(pr.merged_at)
        row.closed_at = _naive(pr.closed_at)
        row.source_branch = pr.source_branch
        row.target_branch = pr.target_branch
        row.commit_sha = pr.commit_sha
        row.base_commit_sha = pr.base_commit_sha
        if pr.jira_issue_id:
            row.jira_issue_id = pr.jira_issue_id
        self.session.flush()
        return row

    def replace_diff(self, pr_id: str, diff: Diff) -> None:
        self.session.execute(delete(orm.PrDiff).where(orm.PrDiff.pr_id == pr_id))
        self.session.add(
            orm.PrDiff(
                pr_id=pr_id,
                files_changed=diff.files_changed,
                additions=diff.additions,
                deletions=diff.deletions,
                files_json=[
                    {
                        "filename": f.filename,
                        "additions": f.additions,
                        "deletions": f.deletions,
                        "status": f.status,
                    }
                    for f in diff.files
                ],
            )
        )

    def replace_reviews(self, pr_id: str, reviews: list[Review]) -> None:
        self.session.execute(delete(orm.PrReview).where(orm.PrReview.pr_id == pr_id))
        for r in reviews:
            self.session.add(
                orm.PrReview(
                    pr_id=pr_id,
                    reviewer=r.reviewer,
                    state=r.state.value,
                    submitted_at=_naive(r.submitted_at),
                    lines_commented=r.lines_commented,
                )
            )

    def replace_checks(self, pr_id: str, checks: list[Check]) -> None:
        self.session.execute(delete(orm.PrCheck).where(orm.PrCheck.pr_id == pr_id))
        for c in checks:
            self.session.add(
                orm.PrCheck(
                    pr_id=pr_id,
                    check_name=c.name,
                    status=c.status.value,
                    completed_at=_naive(c.completed_at),
                    url=c.url,
                    metadata_json={"required": c.required, "summary": c.summary},
                )
            )

    def create_run(self, pr_id: str) -> orm.AnalysisRun:
        row = orm.AnalysisRun(pr_id=pr_id, status="running", started_at=_naive(datetime.now(timezone.utc)))
        self.session.add(row)
        self.session.flush()
        return row

    # ---------------------------------------------------- scoring config (global)
    _SCORING_CONFIG_ID = "global"

    def get_scoring_config(self) -> orm.ScoringConfig | None:
        """The single global scoring override, or None if the team hasn't set one."""
        return self.session.get(orm.ScoringConfig, self._SCORING_CONFIG_ID)

    def upsert_scoring_config(
        self,
        health_weights: dict[str, float],
        thresholds: dict[str, float],
    ) -> orm.ScoringConfig:
        """Create or replace the global override. Caller commits."""
        row = self.session.get(orm.ScoringConfig, self._SCORING_CONFIG_ID)
        if row is None:
            row = orm.ScoringConfig(id=self._SCORING_CONFIG_ID)
            self.session.add(row)
        row.health_weights_json = dict(health_weights)
        row.thresholds_json = dict(thresholds)
        self.session.flush()
        return row

    def clear_scoring_config(self) -> None:
        """Forget the override so engine defaults apply again. Caller commits."""
        self.session.execute(
            delete(orm.ScoringConfig).where(orm.ScoringConfig.id == self._SCORING_CONFIG_ID)
        )
        self.session.flush()

    def complete_run(self, run: orm.AnalysisRun) -> None:
        run.status = "completed"
        run.completed_at = _naive(datetime.now(timezone.utc))

    def fail_run(self, run: orm.AnalysisRun, message: str) -> None:
        run.status = "failed"
        run.error_message = message
        run.completed_at = _naive(datetime.now(timezone.utc))

    def save_signals(self, run_id: str, signals: list[AnalysisSignal]) -> None:
        for s in signals:
            self.session.add(
                orm.AnalysisSignal(
                    analysis_run_id=run_id,
                    signal_name=s.key,
                    severity=s.severity.value,
                    value=s.value,
                    threshold=s.threshold,
                    exceeds_threshold=s.exceeds_threshold,
                    explanation=s.explanation,
                    metadata_json={"analyzer": s.analyzer, **s.metadata},
                )
            )

    def save_score(self, run_id: str, pr_id: str, score: Score) -> orm.AnalysisScore:
        row = orm.AnalysisScore(
            analysis_run_id=run_id,
            pr_id=pr_id,
            health_score=score.health_score,
            review_quality_score=score.review_quality_score,
            merge_readiness=score.merge_readiness,
            score_breakdown_json=score.breakdown.as_dict(),
            blocking_reason=score.blocking_reason,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def upsert_narrative(
        self, pr_id: str, run_id: str, summary: str, recommendation: str, model: str,
        posted_at: datetime | None = None,
    ) -> orm.PrNarrative:
        row = self.session.scalar(select(orm.PrNarrative).where(orm.PrNarrative.pr_id == pr_id))
        if row is None:
            row = orm.PrNarrative(pr_id=pr_id, analysis_run_id=run_id)
            self.session.add(row)
        row.analysis_run_id = run_id
        row.ai_summary = summary
        row.ai_recommendation = recommendation
        row.ai_model = model
        if posted_at is not None:
            row.posted_at = _naive(posted_at)
        self.session.flush()
        return row

    # ------------------------------------------------------------------ reads
    def get_repository(self, repo_id: str) -> orm.Repository | None:
        return self.session.get(orm.Repository, repo_id)

    def get_pull_request(self, pr_id: str) -> orm.PullRequest | None:
        return self.session.get(orm.PullRequest, pr_id)

    def latest_score_for_pr(self, pr_id: str) -> orm.AnalysisScore | None:
        return self.session.scalar(
            select(orm.AnalysisScore)
            .where(orm.AnalysisScore.pr_id == pr_id)
            .order_by(orm.AnalysisScore.created_at.desc())
            .limit(1)
        )

    def latest_run_for_pr(self, pr_id: str) -> orm.AnalysisRun | None:
        return self.session.scalar(
            select(orm.AnalysisRun)
            .where(orm.AnalysisRun.pr_id == pr_id)
            .order_by(orm.AnalysisRun.created_at.desc())
            .limit(1)
        )

    def signals_for_run(self, run_id: str) -> list[orm.AnalysisSignal]:
        return list(
            self.session.scalars(
                select(orm.AnalysisSignal).where(orm.AnalysisSignal.analysis_run_id == run_id)
            )
        )

    def narrative_for_pr(self, pr_id: str) -> orm.PrNarrative | None:
        return self.session.scalar(select(orm.PrNarrative).where(orm.PrNarrative.pr_id == pr_id))

    def diff_for_pr(self, pr_id: str) -> orm.PrDiff | None:
        return self.session.scalar(select(orm.PrDiff).where(orm.PrDiff.pr_id == pr_id))

    def checks_for_pr(self, pr_id: str) -> list[orm.PrCheck]:
        """Persisted CI checks for a PR (latest snapshot from the last analysis)."""
        return list(
            self.session.scalars(select(orm.PrCheck).where(orm.PrCheck.pr_id == pr_id))
        )

    # ---- dashboard reads (added in Phase D) ----
    def list_repositories(self) -> list[orm.Repository]:
        return list(self.session.scalars(select(orm.Repository).order_by(orm.Repository.created_at)))

    def list_prs_with_latest_score(
        self, repo_id: str, state: str | None, order_by: str, limit: int
    ) -> list[tuple[orm.PullRequest, orm.AnalysisScore | None]]:
        stmt = select(orm.PullRequest).where(orm.PullRequest.repo_id == repo_id)
        if state:
            stmt = stmt.where(orm.PullRequest.state == state)
        sort_col = {
            "created_at": orm.PullRequest.created_at,
            "merged_at": orm.PullRequest.merged_at,
            "opened_at": orm.PullRequest.opened_at,
            "updated_at": orm.PullRequest.updated_at,
        }.get(order_by, orm.PullRequest.created_at)
        stmt = stmt.order_by(sort_col.desc()).limit(limit)
        prs = list(self.session.scalars(stmt))
        return [(pr, self.latest_score_for_pr(pr.id)) for pr in prs]

    def signal_breach_trend(
        self, repo_id: str, signal_name: str, period_days: int
    ) -> list[dict]:
        """Daily breach counts for a signal across a repo's PRs.

        Buckets by day in Python rather than a SQL date() call, so it's portable
        across SQLite and PostgreSQL (Postgres has no sqlite-style date()).
        """
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=period_days)
        timestamps = self.session.scalars(
            select(orm.AnalysisSignal.created_at)
            .join(orm.AnalysisRun, orm.AnalysisRun.id == orm.AnalysisSignal.analysis_run_id)
            .join(orm.PullRequest, orm.PullRequest.id == orm.AnalysisRun.pr_id)
            .where(
                orm.PullRequest.repo_id == repo_id,
                orm.AnalysisSignal.signal_name == signal_name,
                orm.AnalysisSignal.exceeds_threshold.is_(True),
                orm.AnalysisSignal.created_at >= since,
            )
        )
        counts: dict[str, int] = {}
        for ts in timestamps:
            day = ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10]
            counts[day] = counts.get(day, 0) + 1
        return [{"day": d, "count": c} for d, c in sorted(counts.items())]

    def author_pr_stats(self, author: str) -> dict:
        """Per-author aggregates (individual author, never team)."""
        pr_count = self.session.scalar(
            select(func.count()).select_from(orm.PullRequest).where(orm.PullRequest.author == author)
        )
        avg_health = self.session.scalar(
            select(func.avg(orm.AnalysisScore.health_score))
            .join(orm.PullRequest, orm.PullRequest.id == orm.AnalysisScore.pr_id)
            .where(orm.PullRequest.author == author)
        )
        return {
            "author": author,
            "pr_count": int(pr_count or 0),
            "avg_health_score": round(float(avg_health), 2) if avg_health is not None else None,
        }

    def repo_overview(self, repo_id: str, ready_threshold: float) -> dict:
        """Aggregate counts/averages/severity-distribution/top-signals for the repo,
        over the latest score + latest run per PR. Powers the dashboard hero widgets."""
        pairs = self.list_prs_with_latest_score(repo_id, None, "created_at", 100000)
        counts = {"total": len(pairs), "open": 0, "merged": 0, "closed": 0,
                  "ready": 0, "blocked": 0, "analyzed": 0}
        sums = {"health": 0.0, "review_quality": 0.0, "merge_readiness": 0.0}
        n_scored = 0
        severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        breaches: dict[str, int] = {}
        for pr, score in pairs:
            if pr.state in counts:
                counts[pr.state] += 1
            if score is not None:
                n_scored += 1
                counts["analyzed"] += 1
                sums["health"] += score.health_score
                sums["review_quality"] += score.review_quality_score
                sums["merge_readiness"] += score.merge_readiness
                if score.blocking_reason:
                    counts["blocked"] += 1
                elif score.merge_readiness >= ready_threshold:
                    counts["ready"] += 1
            run = self.latest_run_for_pr(pr.id)
            if run:
                for sig in self.signals_for_run(run.id):
                    if sig.severity in severity:
                        severity[sig.severity] += 1
                    if sig.exceeds_threshold:
                        breaches[sig.signal_name] = breaches.get(sig.signal_name, 0) + 1
        averages = {k: (round(v / n_scored, 2) if n_scored else None) for k, v in sums.items()}
        top = sorted(breaches.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        return {
            "counts": counts,
            "averages": averages,
            "severity_distribution": severity,
            "top_signals": [{"signal_name": k, "count": c} for k, c in top],
        }

    # ---- needs-attention ranking (Question 2: which repos need attention) ----
    # Ported from the sibling app's attention model, mapped onto our signal keys.
    _ATTENTION_WEIGHTS = {
        "merged_without_passing_build": 3,  # shipped unverified — most serious
        "large_change_low_review": 2,       # big change, weak review
        "no_linked_jira_ticket": 1,         # untraceable
        "merged_too_fast": 1,               # rushed
    }
    _ATTENTION_THRESHOLD = 1.0              # weighted violations / merged PR
    _MIN_MERGED_FOR_ATTENTION = 5           # anti-noise: need enough merged PRs to judge
    _CI_FAIL_KEYS = {
        "ci_status.merged_despite_failure",
        "ci_status.required_failing",
        "ci_status.no_checks",  # no CI gating the merge == violation, by design
    }
    _REVIEW_WEAK_KEYS = {
        "review_quality.no_reviews",
        "review_quality.no_approval",
        "review_quality.single_reviewer",
    }

    @classmethod
    def _violations_for(cls, signal_names: set[str]) -> dict[str, bool]:
        """Map a merged PR's persisted signal names to the four violation categories."""
        return {
            "merged_without_passing_build": bool(signal_names & cls._CI_FAIL_KEYS),
            "merged_too_fast": "merge_speed.fast_merge" in signal_names,
            "no_linked_jira_ticket": "ticket_linkage.no_jira" in signal_names,
            "large_change_low_review": (
                "change_size.large_diff" in signal_names and bool(signal_names & cls._REVIEW_WEAK_KEYS)
            ),
        }

    @classmethod
    def _behaviours_for(cls, signal_names: set[str]) -> dict[str, bool]:
        """The GOOD practices present on a merged PR (inverse of the violations)."""
        return {
            "passing_build": not (signal_names & cls._CI_FAIL_KEYS),
            "linked_jira": "ticket_linkage.no_jira" not in signal_names,
            "small_change": "change_size.large_diff" not in signal_names,
            "unrushed_merge": "merge_speed.fast_merge" not in signal_names,
        }

    def needs_attention(self) -> list[dict]:
        """Per-repo attention ranking over merged PRs' latest-run signals. Worst-first
        by the MVP build-violation rate; repos with no merged PRs sink to the bottom."""
        out: list[dict] = []
        for repo in self.list_repositories():
            merged_pairs = self.list_prs_with_latest_score(repo.id, "merged", "created_at", 100000)
            merged = len(merged_pairs)
            counts = {c: 0 for c in self._ATTENTION_WEIGHTS}
            for pr, _score in merged_pairs:
                run = self.latest_run_for_pr(pr.id)
                names = {s.signal_name for s in self.signals_for_run(run.id)} if run else set()
                for cat, bad in self._violations_for(names).items():
                    if bad:
                        counts[cat] += 1
            build_rate = (counts["merged_without_passing_build"] / merged * 100) if merged else None
            weighted = sum(counts[c] * self._ATTENTION_WEIGHTS[c] for c in self._ATTENTION_WEIGHTS)
            score = (weighted / merged) if merged else 0.0
            reasons = [
                f"{counts[c]} {c.replace('_', ' ')} ({counts[c] / merged * 100:.0f}%)"
                for c in sorted(self._ATTENTION_WEIGHTS, key=lambda x: -counts[x])
                if counts[c] and merged
            ]
            out.append(
                {
                    "repo_id": repo.id,
                    "name": repo.name,
                    "provider": repo.provider,
                    "merged_prs": merged,
                    "build_violation_rate": round(build_rate, 1) if build_rate is not None else None,
                    "attention_score": round(score, 2),
                    "needs_attention": merged >= self._MIN_MERGED_FOR_ATTENTION
                    and score >= self._ATTENTION_THRESHOLD,
                    "signal_counts": counts,
                    "reasons": reasons,
                }
            )
        out.sort(key=lambda r: (r["build_violation_rate"] is None, -(r["build_violation_rate"] or 0)))
        return out

    # ---- revert correlation (Question 3: what behaviours correlate with quality) ----
    _REVERT_RE = re.compile(r"#(\d+)")
    _BEHAVIOURS = ["passing_build", "linked_jira", "small_change", "unrushed_merge"]

    def revert_correlation(self, repo_id: str) -> dict:
        """Outcome proxy: a merged PR is 'bad' if a later 'Revert … #N' PR undid it.
        For each good behaviour, compare the revert rate of PRs that HAD it vs didn't.
        Correlation, not causation — and meaningful only with enough history."""
        all_pairs = self.list_prs_with_latest_score(repo_id, None, "created_at", 100000)

        reverted: set[int] = set()
        for pr, _ in all_pairs:
            title = pr.title or ""
            if "revert" in title.lower():
                reverted.update(int(m) for m in self._REVERT_RE.findall(title))

        stats = {
            b: {"with_total": 0, "with_bad": 0, "wo_total": 0, "wo_bad": 0} for b in self._BEHAVIOURS
        }
        merged_total = 0
        reverted_total = 0
        for pr, _ in all_pairs:
            if pr.state != "merged":
                continue
            merged_total += 1
            num = int(pr.provider_pr_id) if (pr.provider_pr_id or "").isdigit() else None
            bad = num is not None and num in reverted
            if bad:
                reverted_total += 1
            run = self.latest_run_for_pr(pr.id)
            names = {s.signal_name for s in self.signals_for_run(run.id)} if run else set()
            for behaviour, present in self._behaviours_for(names).items():
                side = "with" if present else "wo"
                stats[behaviour][f"{side}_total"] += 1
                if bad:
                    stats[behaviour][f"{side}_bad"] += 1

        behaviours = []
        for b in self._BEHAVIOURS:
            s = stats[b]
            behaviours.append(
                {
                    "behaviour": b,
                    "with_total": s["with_total"],
                    "with_rate": round(s["with_bad"] / s["with_total"] * 100, 1) if s["with_total"] else None,
                    "wo_total": s["wo_total"],
                    "wo_rate": round(s["wo_bad"] / s["wo_total"] * 100, 1) if s["wo_total"] else None,
                }
            )
        return {"merged": merged_total, "reverted": reverted_total, "behaviours": behaviours}

    @staticmethod
    def _history_bucket_key(created_at, bucket: str) -> str:
        """Bucket a timestamp by hour / day / week (Python, portable PG+SQLite)."""
        if not hasattr(created_at, "date"):
            return str(created_at)[:10]
        if bucket == "hour":
            return created_at.strftime("%Y-%m-%dT%H:00")
        if bucket == "week":
            d = created_at.date()
            return (d - timedelta(days=d.weekday())).isoformat()  # Monday of that week
        return created_at.date().isoformat()  # day

    def score_history(
        self, repo_id: str, period_days: int, bucket: str = "day", tz_offset_minutes: int = 0
    ) -> list[dict]:
        """Avg health + run count across the repo's analyses, bucketed by hour/day/week
        in the VIEWER's timezone (so hours/days align to local wall-clock, not UTC).
        ``tz_offset_minutes`` is JS ``getTimezoneOffset()`` (e.g. -330 for IST).
        Python bucketing — portable across SQLite and Postgres; keys are local wall-clock."""
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=period_days)
        rows = self.session.execute(
            select(orm.AnalysisScore.created_at, orm.AnalysisScore.health_score)
            .join(orm.PullRequest, orm.PullRequest.id == orm.AnalysisScore.pr_id)
            .where(orm.PullRequest.repo_id == repo_id, orm.AnalysisScore.created_at >= since)
        ).all()
        buckets: dict[str, list] = {}
        for created_at, health in rows:
            ts = created_at
            if tz_offset_minutes and hasattr(ts, "date"):
                ts = ts - timedelta(minutes=tz_offset_minutes)  # UTC → local wall-clock
            key = self._history_bucket_key(ts, bucket)
            b = buckets.setdefault(key, [0, 0.0])
            b[0] += 1
            b[1] += health
        return [
            {"day": d, "runs": n, "avg_health": round(s / n, 2)}
            for d, (n, s) in sorted(buckets.items())
        ]
