"""PR similarity — "have we shipped a change like this before, and how did it go?"

PURE: stdlib (``re``) only. No embeddings API, no model, no network — similarity is
computed from features we already store, so it runs offline and for free:

* file overlap  — Jaccard over changed file paths (the strongest "same kind of
                  change" signal: two PRs touching the same files are related)
* title overlap — Jaccard over title word tokens
* size affinity — ratio of the smaller changeset to the larger

These combine into a single 0..1 score. The caller (similarity_service) ranks a
repo's historical PRs against a target PR and surfaces each neighbour's *outcome*
(its health score and whether it was later reverted) — turning "this PR resembles
12 past PRs, 4 of which were reverted" into a read-only risk signal for reviewers.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# How the three components combine. File overlap dominates: touching the same code
# is a far stronger similarity signal than a shared word in the title.
W_FILES = 0.55
W_TITLE = 0.25
W_SIZE = 0.20


def tokens(text: str) -> set[str]:
    """Lowercased alphanumeric word tokens, length >= 2 (drops noise like 'a')."""
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) >= 2}


def jaccard(a: set[str], b: set[str]) -> float:
    """Set overlap in [0, 1]. Empty-vs-empty is 0 (no evidence of similarity)."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _size_affinity(a: float, b: float) -> float:
    """1.0 when changesets are the same size, ->0 as they diverge."""
    hi = max(a, b)
    if hi <= 0:
        return 1.0 if a == b else 0.0
    return min(a, b) / hi


def similarity(target: dict, candidate: dict) -> float:
    """Weighted 0..1 similarity between two PR feature bundles (see repository
    similarity_corpus for the bundle shape).

    Size affinity only *refines* a match — it never creates one. Two unrelated PRs
    that happen to be the same size share no files and no title words, so we require
    content overlap (files or title) before size can contribute; otherwise the score
    is 0 and the candidate is treated as not similar."""
    file_sim = jaccard(set(target.get("files") or []), set(candidate.get("files") or []))
    title_sim = jaccard(tokens(target.get("title", "")), tokens(candidate.get("title", "")))
    if file_sim <= 0.0 and title_sim <= 0.0:
        return 0.0
    size_sim = _size_affinity(float(target.get("size") or 0.0), float(candidate.get("size") or 0.0))
    return round(W_FILES * file_sim + W_TITLE * title_sim + W_SIZE * size_sim, 4)


def rank_similar(target: dict, corpus: list[dict], k: int = 5) -> list[dict]:
    """Top-k most similar PRs to ``target`` (excluding itself), each annotated with
    its similarity score. Zero-similarity candidates are dropped so we never present
    an unrelated PR as a "neighbour"."""
    scored: list[dict] = []
    for cand in corpus:
        if cand.get("pr_id") == target.get("pr_id"):
            continue
        score = similarity(target, cand)
        if score <= 0.0:
            continue
        scored.append({**cand, "similarity": score})
    scored.sort(key=lambda c: (-c["similarity"], str(c.get("provider_pr_id"))))
    return scored[:k]
