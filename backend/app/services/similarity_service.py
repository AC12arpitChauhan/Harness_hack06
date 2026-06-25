"""Find a PR's nearest historical neighbours and summarize their outcomes.

Thin orchestration: pull the repo's similarity corpus from the database, rank it
with the pure app.scoring.similarity functions, and roll the neighbours' outcomes
into a one-line risk read. No I/O beyond the injected Repository; no model calls.
"""
from __future__ import annotations

from app.persistence.repository import Repository
from app.scoring.similarity import rank_similar


def similar_prs(repository: Repository, repo_id: str, pr_id: str, k: int = 5) -> dict:
    """Return the ``k`` most similar past PRs to ``pr_id`` plus an outcome summary.

    ``neighbors`` is empty when the PR has no stored diff or the repo has no other
    analyzed PRs to compare against — the caller surfaces that as "no comparable
    history yet" rather than an error.
    """
    corpus = repository.similarity_corpus(repo_id)
    target = next((c for c in corpus if c["pr_id"] == pr_id), None)
    if target is None:
        return {"pr_id": pr_id, "neighbors": [], "summary": _empty_summary()}

    neighbors = rank_similar(target, corpus, k)
    healths = [n["health_score"] for n in neighbors if n["health_score"] is not None]
    reverted = sum(1 for n in neighbors if n["reverted"])
    summary = {
        "neighbor_count": len(neighbors),
        "reverted_count": reverted,
        "reverted_rate": round(reverted / len(neighbors) * 100, 1) if neighbors else None,
        "avg_health_score": round(sum(healths) / len(healths), 2) if healths else None,
    }
    return {"pr_id": pr_id, "neighbors": neighbors, "summary": summary}


def _empty_summary() -> dict:
    return {
        "neighbor_count": 0,
        "reverted_count": 0,
        "reverted_rate": None,
        "avg_health_score": None,
    }
