# How Checks Are Evaluated & How Severity (incl. CRITICAL) Is Decided

This document explains, end to end, how the PR Health service turns a pull request
into the four scores you see on the dashboard — with special focus on **CI check
evaluation** and **how a signal becomes CRITICAL**.

Everything here is deterministic: the same inputs always produce the same scores.
The LLM only writes the human-readable narrative; it never touches scoring.

---

## 1. The pipeline at a glance

```
PR + checks + reviews + diff
        │
        ▼
 ┌─────────────┐   each analyzer inspects one dimension and emits Signals,
 │  analyzers  │   each Signal carrying a Severity (INFO…CRITICAL)
 └─────────────┘
        │  list[AnalysisSignal]
        ▼
 ┌─────────────┐   Severity → penalty points; penalties subtract from 100
 │   engine    │   per analyzer; weighted blend → health/review/merge
 └─────────────┘
        │
        ▼
 health_score · review_quality_score · merge_readiness
```

- **Analyzers** (`app/analyzers/`) detect conditions and assign severity.
- **Engine** (`app/scoring/engine.py`) converts severities to points and combines them.
- **Policies** (`app/scoring/policies.py`) decide which signals *hard-block* a merge.

---

## 2. Severity → penalty

Every signal carries one severity. Severity maps to a fixed penalty in points
(`engine.py`, `DEFAULT_SEVERITY_PENALTIES`):

| Severity | Penalty |
|----------|---------|
| INFO     | 0       |
| LOW      | 5       |
| MEDIUM   | 15      |
| HIGH     | 30      |
| CRITICAL | 50      |

Notes:

- The penalty is **per signal**, by severity only. It does **not** scale with the
  signal's `value` (e.g. 2 failing checks ≠ double penalty — see §5).
- `INFO` = 0 → a neutral/healthy observation that never lowers a score.

---

## 3. From penalties to scores

In `engine.py`:

1. Seed the four **weighted** analyzers at penalty 0 (a silent analyzer stays perfect).
2. For each signal, add its severity penalty **only if its analyzer is weighted**.
3. `subscore[a] = max(0, 100 − Σ penalties[a])`
4. `health_score = Σ HEALTH_WEIGHTS[a] × subscore[a]`
5. `review_quality_score = subscore["review_quality"]`
6. `merge_readiness`: if any hard blocker is present → `min(health, 15)`, else `health`.

**Weighted analyzers** (`DEFAULT_HEALTH_WEIGHTS`):

| Analyzer        | Health weight |
|-----------------|---------------|
| review_quality  | 0.35          |
| change_size     | 0.25          |
| merge_speed     | 0.20          |
| ci_status       | 0.20          |

> **`ticket_linkage` is NOT weighted.** Its signals (e.g. `no_jira`) show on the
> dashboard but contribute **zero** to the health/merge scores. They are
> recorded with `counted_toward_score=False`.

All weights sum to 1.0, so every score lands in `[0, 100]`.

---

## 4. CI check evaluation (`ci_status` analyzer)

The `ci_status` analyzer ranks the PR's checks using a **strict priority ladder**.
It evaluates conditions in order and **returns at the first match**, so each run
produces exactly one CI outcome (except the merged-despite-failure add-on).

| Priority | Condition                                              | Signal                    | Severity  | Penalty | Hard blocker |
|----------|--------------------------------------------------------|---------------------------|-----------|---------|--------------|
| 0        | No checks reported at all                              | `no_checks`               | INFO      | 0       | no           |
| 1        | ≥1 **required** check = FAILURE                        | `required_failing`        | CRITICAL  | 50      | **yes**      |
| 1b       | …and the PR is **already merged**                      | `merged_despite_failure`  | CRITICAL  | 50      | **yes**      |
| 2        | No required failing, but a **non-required** = FAILURE  | `optional_failing`        | MEDIUM    | 15      | no           |
| 3        | No failures, but a **required** check = PENDING        | `checks_pending`          | LOW       | 5       | no           |
| 4        | All required checks green                              | `checks_passing`          | INFO      | 0       | no           |

What this means in practice:

- **"Required" is what makes a failure severe.** A failing *required* check is
  CRITICAL **and** a hard blocker; a failing *optional* check is only MEDIUM.
  Whether a check is required comes from your branch-protection rules in Harness
  Code — not from this service.
- **First match wins.** A failing required check masks everything below it; you
  will not also see `checks_pending` for the same run.
- **PENDING is only LOW.** A required check still running is mild (5 points) and is
  **not** a blocker. (This is why an analyzer that runs *inside* the same pipeline
  whose check it is reading will see `checks_pending` instead of the terminal
  `required_failing` — it must observe the check after that pipeline finishes.)
- **`no_checks` and `checks_passing` are both INFO** (0 penalty) but are distinct
  signals so the narrative can tell "all green" from "nothing ran".

---

## 5. Does N failing checks penalize N times?

**No.** `ci_status` emits a **single aggregated** `required_failing` signal even when
several required checks fail:

- The number of failing checks is stored in the signal's `value` field (e.g. `2.0`)
  and the names are joined into the explanation.
- The engine adds the CRITICAL penalty **once** for that one signal — `value` is
  metadata, never a multiplier.
- On the dashboard this is **+1** to the Critical bar and **+1** to
  `Ci Status · Required Failing`, not +2.

The only way `ci_status` produces two CRITICAL penalties in one run is the
**merged-despite-failure** case (failing required checks **and** PR already merged),
which appends a second distinct signal → sub-score floored at 0.

---

## 6. Every way a signal becomes CRITICAL

CRITICAL is assigned in exactly five places across the analyzers:

| # | Signal                            | Analyzer        | Fires when (defaults)                                   | Hard blocker |
|---|-----------------------------------|-----------------|---------------------------------------------------------|--------------|
| 1 | `ci_status.required_failing`      | ci_status       | any required check is FAILURE                           | **yes**      |
| 2 | `ci_status.merged_despite_failure`| ci_status       | #1 **and** PR is merged                                 | **yes**      |
| 3 | `review_quality.no_reviews`       | review_quality  | zero reviewers on a non-trivial PR (> 10 changed lines) | **yes**      |
| 4 | `change_size.large_diff` (top tier)| change_size    | `total_changes >= 1000` lines                           | no           |
| 5 | `merge_speed.fast_merge` (top tier)| merge_speed    | merged in `< 15` minutes from open                      | no           |

How each decides:

- **#1, #2, #3** are *binary* conditions — flatly stamped CRITICAL (no threshold math).
- **#4, #5** are *tiered* — the same analyzer escalates by magnitude:
  - `change_size`: `>= 1000` → CRITICAL, else `>= 500` → HIGH, else `>= 250` → MEDIUM, else INFO.
  - `merge_speed`: `< 15 min` → CRITICAL, else `< 60 min` → HIGH, else INFO.

So **CRITICAL severity ≠ hard blocker**: a 1000-line diff or a 5-minute merge is
CRITICAL (−50 to its analyzer) but does **not** by itself cap `merge_readiness`.

---

## 7. Hard blockers (the merge gate)

`scoring/policies.py` defines the only signals that cap `merge_readiness` to ≤ 15,
regardless of how good the other scores are:

| Signal key                          | Reason shown                                       |
|-------------------------------------|----------------------------------------------------|
| `ci_status.required_failing`        | Required CI check is failing                       |
| `ci_status.merged_despite_failure`  | Merged despite a failing required CI check         |
| `review_quality.no_reviews`         | No approving review on a non-trivial change        |

If any are present, `merge_readiness = min(health, 15)` and `blocking_reason` is set.

---

## 8. The Severity Breakdown & Most Frequent widgets

Both come from `repository.repo_overview()`, aggregating each PR's **latest run**:

- **Severity breakdown** (Critical/High/Medium/Low/Info) = a straight **count of
  signals by severity** across all PRs. One PR can contribute several signals.
- **Most frequent** = counts only signals where `exceeds_threshold = True` (breaches),
  grouped by signal name, top 5 by count then name. INFO/healthy signals usually
  don't appear here because they are `exceeds_threshold = False`.

`exceeds_threshold` affects **only** these dashboard tallies — it plays no part in
scoring. Only `severity` drives penalties.

---

## 9. Worked example

A PR with signals: `merge_speed.not_merged` (INFO), `change_size.small_diff` (INFO),
`review_quality.no_review_trivial` (INFO), `ci_status.checks_pending` (LOW),
`ticket_linkage.no_jira` (LOW):

| Analyzer        | Weight | Penalty            | Sub-score | Contribution |
|-----------------|--------|--------------------|-----------|--------------|
| merge_speed     | 0.20   | 0 (INFO)           | 100       | 20.0         |
| change_size     | 0.25   | 0 (INFO)           | 100       | 25.0         |
| review_quality  | 0.35   | 0 (INFO)           | 100       | 35.0         |
| ci_status       | 0.20   | 5 (LOW)            | 95        | 19.0         |
| ticket_linkage  | —      | 5, **not counted** | —         | —            |

`health_score = 20 + 25 + 35 + 19 = 99.0`. No hard blocker → `merge_readiness = 99.0`.
Note `no_jira` cost nothing (unweighted analyzer).

---

## 10. Tuning

The constants here are the documented defaults in `scoring/engine.py`, re-exposed by
`config.py`. A team can override weights, thresholds, and the blocked cap via
`PUT /api/v1/scoring-config`; the live values in effect are returned by
`GET /api/v1/scoring-config`. The *mechanism* above is unchanged — only the numbers.

### Source files
- `app/analyzers/ci_status.py` — CI check ladder
- `app/analyzers/change_size.py`, `merge_speed.py`, `review_quality.py`, `ticket_linkage.py`
- `app/scoring/engine.py` — penalties, sub-scores, weighted blend
- `app/scoring/policies.py` — hard blockers
- `app/persistence/repository.py` — `repo_overview()` dashboard aggregation