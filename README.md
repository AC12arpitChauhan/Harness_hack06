# PR Vitals.   | Engineering Quality Analytics

> **The vital signs of how your team ships code.** A deterministic health score for every
> pull request — across **GitHub** *and* **Harness Code** — with an AI that explains the score
> and tells you how to fix a failing build.

**▶ Live dashboard:** http://34.11.187.253/
**API + Swagger docs:** http://136.109.192.193:8000/docs

**Team Vitals** — Ashmita Poddar · Yuvraj Pratiksh Raghuvanshi · Kushal Gupta · Arpit Chauhan
Harness Hackathon · Problem 01 — *PR Health & Engineering Quality*


<img width="1019" height="727" alt="Screenshot 2026-06-24 at 12 43 47 AM" src="https://github.com/user-attachments/assets/b1d9f92d-4d32-436d-97db-c9b2b1ffa9b8" />


---

## The problem

At scale, pull requests are the clearest signal of how a team ships code — but the bad ones
(rushed merges, skipped reviews, builds shipped red, untraceable changes) stay invisible until
they cause an incident. The signal already exists in SCM data; nobody reads it systematically.

This product answers the three questions leadership actually asks:

1. **How healthy are our PR practices?** → a per-repo **PR Health Index**.
2. **Which repos need attention right now?** → a ranked, anti-noise **watch-list**.
3. **What behaviours correlate with quality?** → **revert correlation**.

## What it does

- **Deterministic PR scoring** — Health / Review-quality / Merge-readiness for every PR.
- **Needs-attention ranking** — repos ranked by weighted build-violation rate (≥5 merged PRs to flag).
- **Revert correlation** — which good practices lead to fewer reverts (`Revert … #N` detection).
- **AI fix suggester** — when CI fails, Claude reads the failing checks and writes concrete fix steps (in the PR drawer + the PR comment).
- **AI narrative** — a plain-English health summary per PR (Claude) — *never* influences the score.
- **Provider-agnostic** — GitHub and Harness Code (Gitness) behind one `SCMProvider` port; everything downstream is provider-blind.
- **Write-back** — posts a health comment + commit status onto the PR.
- **Slack alerts** — deduped build-failure notifications (opt-in via webhook).
- **Editorial dashboard** — health index + lollipop trend, recent PRs, signal breakdown, merge funnel, author spotlight, scoring settings, CSV export.

## How the score works (deterministic — the LLM never touches it)

```
signals → severity penalty → per-analyzer sub-score → weighted scores
INFO 0 · LOW 5 · MEDIUM 15 · HIGH 30 · CRITICAL 50
subscore(analyzer) = max(0, 100 − Σ penalties)
health_score = Σ weightᴴ · subscore        review_quality_score = subscore(review_quality)
merge_readiness = health_score (capped at 15 if a hard blocker fires)
ready = merge_readiness ≥ 70  AND  no hard blocker
```

Five pure analyzers feed it: **ci_status · merge_speed · change_size · review_quality · ticket_linkage (Jira)**.
Hard blockers (cap readiness): required CI failing · merged-despite-failure · no review on a non-trivial change.
Claude reads the finished scores to write prose and fix suggestions — it has **no vote**.

## Architecture

```
 PR opened → Harness trigger → pipeline → POST /analyze
                                            │
 GitHub / Harness Code ──► Adapter ──► Deterministic core ──► FastAPI + Postgres ──► Dashboard
 (one SCMProvider port)   (normalize)   5 analyzers→scoring                          PR write-back
                                            ▲  (NO LLM here)                          Slack alert
                                            ┆ reads the score — never moves it
                                   Claude · Bedrock / Anthropic  →  narrative + AI fix
            Runs on Kubernetes · shipped by a Harness CI/CD pipeline
```

Hexagonal: the pure core (analyzers + scoring engine) imports nothing external; provider adapters
and the LLM point **inward**. Swapping GitHub ↔ Harness Code changes only the adapter + mapper.

## Tech stack

- **Backend:** FastAPI · SQLAlchemy 2.0 · PostgreSQL (Alembic) · pydantic-settings · httpx · `anthropic` SDK (Bedrock + first-party).
- **Frontend:** React 18 · TypeScript · Vite · TanStack Query · React Router · Tailwind v4 · Framer Motion · hand-built SVG charts (Instrument Serif + Geist).
- **AI:** Claude (`claude-sonnet-4-6`) via Amazon Bedrock or the first-party Anthropic API — narration + fix suggestions only.
- **Delivery:** Docker → Docker Hub → Kubernetes (namespace `hack06-pr-health`) via **Harness CI/CD**; LoadBalancer public IPs; PR-event triggers call `/analyze`.

## Repository layout

```
backend/      FastAPI service — app/{analyzers,scoring,domain,providers,services,llm,api,persistence}
              k8s/ + harness/ deploy manifests + pipeline · tests/ (80 tests, SQLite + Postgres)
frontend/     React + TS dashboard — src/{lib,components,pages} · Dockerfile + nginx + k8s/ + harness/
presentation/ index.html — the keynote (open in a browser, press F; → / ← to navigate, N for notes)
```

## Run locally

```bash
# backend (SQLite, zero setup)
cd backend && pip install -e . && uvicorn app.main:app --reload --port 8000

# frontend (proxies /api to the deployed backend — no CORS needed)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

## Key API endpoints (all GET are open / no auth)

`/api/v1/repositories` · `…/overview` · `…/score_history` · `…/needs_attention` ·
`…/prs` · `…/prs/{id}` · `…/prs/{id}/merge_readiness` · `…/prs/{id}/ai_fix` ·
`…/revert_analysis` · `/authors/{a}/pr_stats` · `/scoring-config` ·
`POST /analyze` · `POST /admin/backfill` · `GET /admin/llm_check` *(auth: `Bearer <token>`)*

## Tests

```bash
cd backend && python -m pytest -q                                   # SQLite
DATABASE_URL=postgresql+psycopg2://localhost:5432/prhealth_test \
  python -m pytest -q                                               # Postgres
```
**80 passing** on both engines — including a golden test that the Jira signal is surface-only and
never changes existing scores.
