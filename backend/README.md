# PR Health Analytics — Backend

Deterministic pull-request scoring with provider-agnostic SCM adapters. A PR's
health is computed by **rule-based analyzers + a deterministic scoring engine**
(same inputs → same scores, always). An LLM writes a human narrative *on top of*
the already-computed scores — it never computes or changes a score.

## Architecture (hexagonal)

```
            ┌───────────────────────── pure core (stdlib only) ─────────────────────────┐
 providers ─┤  domain/  ──  analyzers/  ──  scoring/                                      ├─ persistence
 (edge)     └────────────────────────────────────────────────────────────────────────────┘   (edge)
 llm (edge)                         ▲  services/ (orchestration)  ▲                api/ (edge)
```

- **Pure core** — `domain/`, `analyzers/`, `scoring/`: no `httpx`, `sqlalchemy`,
  `anthropic`, or `fastapi`. Just data + rules. Dependencies point **inward** only.
- **Edges** — `providers/` (GitHub + Harness SCM behind one `SCMProvider` port),
  `llm/`, `persistence/` (the only place SQL lives), `api/`.
- **Orchestration** — `services/analysis_service.py` conducts
  `fetch → analyze → score → persist → (async narrate + writeback)`.

Adding GitLab/Bitbucket later = a new adapter class + mapper. Nothing downstream changes.

## The four scores (deterministic)

Computed in one readable function — `scoring/engine.py:ScoringEngine.compute`.

| Severity | INFO | LOW | MEDIUM | HIGH | CRITICAL |
|---|---|---|---|---|---|
| penalty  | 0 | 5 | 15 | 30 | 50 |

1. Each analyzer's **sub-score** = `max(0, 100 − Σ penalties of its signals)`.
2. **health_score** = weighted avg of sub-scores
   (`merge_speed .20, change_size .25, review_quality .35, ci_status .20`).
3. **risk_score** = weighted "badness" (`Σ risk_weight · (100 − sub-score)`).
4. **review_quality_score** = the `review_quality` sub-score.
5. **merge_readiness** = `health_score`, but capped to **15** when a hard blocker
   fires (`scoring/policies.py`: required CI failing, merged-despite-failure, or an
   un-reviewed non-trivial change). `blocking_reason` records why.

Every score ships with a `score_breakdown_json` that explains itself — a reviewer
can answer "why is health 60.75?" from stored data alone.

## Analyzers (this round)

`merge_speed`, `change_size`, `review_quality`, `ci_status` (all real).
`ticket_linkage` is a **FUTURE stub** — the Jira-key regex helper is in place (and
used by the mappers to fill `jira_issue_id`) but it emits no signals and is not
scored. There is **no concept of "team"** anywhere — author is a plain string.

## Quickstart — SQLite, zero setup

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Option A: let the app create tables on startup (default)
uvicorn app.main:app --reload
# Option B: use migrations explicitly
alembic upgrade head && uvicorn app.main:app --reload
```

Then:
```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer dev-token" -H "Content-Type: application/json" \
  -d '{"provider":"github","repo":"owner/name","pr_number":1}'   # needs GITHUB_TOKEN
```

## Run on PostgreSQL (Docker)

```bash
docker compose up -d
export DATABASE_URL=postgresql+psycopg2://prhealth:prhealth@localhost:5432/prhealth
alembic upgrade head
uvicorn app.main:app --reload
```

The same SQLAlchemy models and migration work on both databases (portable types only).

## Configuration & toggles

Copy `.env.example` → `.env`. Key toggles:

| Var | Default | Effect |
|---|---|---|
| `LLM_ENABLED` | `false` | `false` → deterministic templated narrative (no cost). `true` → Anthropic narration (needs `ANTHROPIC_API_KEY`). **Scores are identical either way** (proven by a test). |
| `WRITEBACK_ENABLED` | `false` | `false` → logs the comment/status it *would* post. `true` → posts a PR comment + commit status. |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Narration model (cost flip: `claude-sonnet-4-6`). |
| `FASTAPI_AUTH_TOKEN` | `dev-token` | Bearer token required on POST routes. |

All scoring thresholds (`MERGE_FAST_MINUTES`, `CHANGE_HIGH_LINES`, …) and
`READY_THRESHOLD` are env-tunable; the canonical weight constants live in
`scoring/engine.py`.

## API

| Method | Path | Auth |
|---|---|---|
| POST | `/api/v1/analyze` | bearer |
| GET | `/api/v1/repositories` | open |
| GET | `/api/v1/repositories/{repo_id}/prs?state=&order_by=&limit=` | open |
| GET | `/api/v1/repositories/{repo_id}/prs/{pr_id}` | open |
| GET | `/api/v1/repositories/{repo_id}/signal_trends?signal_name=&period_days=` | open |
| GET | `/api/v1/authors/{author}/pr_stats` | open |
| GET | `/api/v1/repositories/{repo_id}/prs/{pr_id}/merge_readiness` | open |
| POST | `/api/v1/admin/backfill` | bearer |

Interactive docs at `/docs`.

## Testing (three layers)

```bash
# Layer 1 — capture real GitHub JSON as fixtures (one-time; needs GITHUB_TOKEN)
python scripts/capture_fixtures.py --repo owner/name --pr 123

# Layer 2 — unit + endpoint tests (no network, SQLite). The default run.
pytest tests/unit

# Layer 3 — live end-to-end (opt-in)
RUN_E2E=1 GITHUB_TOKEN=ghp_xxx E2E_REPO=owner/name E2E_PR=123 \
  ANTHROPIC_API_KEY=... LLM_ENABLED=true WRITEBACK_ENABLED=true \
  pytest tests/e2e -v
```

Layer 2 covers: mapper field mapping (from committed fixtures), every analyzer's
boundary cases, scoring determinism, the **LLM-on/off scores-identical** guarantee,
writeback on/off, the full `/analyze` chain with persisted-row assertions, the
dashboard endpoints, and the Harness mapper.

## Backfill (populate the dashboard)

```bash
GITHUB_TOKEN=ghp_xxx python scripts/backfill.py --repo owner/name --since-days 30
```

## Where the Harness CI pipeline plugs in (next round)

This FastAPI service is the application plane. Next round, a **Harness CI pipeline**
(triggered by the existing GitHub webhook) will run build/test/scan, then `POST`
to `/api/v1/analyze` with the PR context — so Harness contributes the real CI
signal that feeds `ci_status` and `merge_readiness`. The pipeline/trigger/connector
YAML is intentionally **out of scope for this round**; the `/analyze` contract above
is the integration point.
```
GitHub PR → Harness webhook trigger → Harness CI (build/test/scan) → POST /api/v1/analyze → scores + comment/status
```
