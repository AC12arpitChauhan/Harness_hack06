# Harness wiring for PR Health Analytics

```
GitHub PR opened/updated
   → Harness webhook trigger (trigger.yaml)
   → Harness CI pipeline (pipeline.yaml): build/test, then POST /api/v1/analyze
   → PR Health FastAPI service (running locally, exposed via ngrok)
        fetches the PR from GitHub, scores it, persists it,
        and (if WRITEBACK_ENABLED) posts a PR comment + commit status
```

## Files
| File | What | Status |
|---|---|---|
| `pipeline.yaml` | The CI pipeline (calls `/api/v1/analyze`) | **new** — paste over `demo_for_hack06` |
| `trigger.yaml` | PR open/reopen/synchronize webhook trigger | **new** (or keep your existing one) |
| `connector.github.yaml` | GitHub connector | reference — you already have `arpit_github_connector` |
| `secret.api-token.yaml` | `pr_health_api_token` text secret | **new** — create in UI, value == `FASTAPI_AUTH_TOKEN` |

## One-time Harness setup
1. Create secret `pr_health_api_token` (value = your service's `FASTAPI_AUTH_TOKEN`).
2. Paste `pipeline.yaml` into the pipeline (or import). Set the `fastapi_url`
   pipeline variable to your current ngrok https URL.
3. Ensure the PR trigger is enabled.

The service does NOT receive your GitHub PAT from the pipeline — it uses its own
`GITHUB_TOKEN` (in `backend/.env`) to read the PR and to write the comment/status.
The pipeline only sends PR context + the `pr_health_api_token` bearer.
