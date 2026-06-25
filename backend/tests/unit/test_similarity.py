"""PR similarity: pure ranking math + the outcome-summary service."""
from __future__ import annotations

from app.scoring.similarity import jaccard, rank_similar, similarity, tokens
from app.services.similarity_service import similar_prs


def _pr(pr_id, files, title="", size=100.0, health=None, reverted=False):
    return {
        "pr_id": pr_id,
        "provider_pr_id": pr_id,
        "title": title,
        "state": "merged",
        "files": files,
        "size": size,
        "health_score": health,
        "reverted": reverted,
    }


def test_tokens_and_jaccard():
    assert tokens("Fix Login Bug") == {"fix", "login", "bug"}
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert jaccard(set(), {"a"}) == 0.0


def test_similarity_rewards_shared_files():
    target = _pr("t", ["auth/login.py", "auth/session.py"], "login fix", 100)
    same = _pr("a", ["auth/login.py", "auth/session.py"], "login fix", 100)
    other = _pr("b", ["ui/button.tsx"], "button color", 100)
    assert similarity(target, same) > similarity(target, other)
    assert similarity(target, same) == 1.0  # identical files+title+size


def test_rank_excludes_self_and_zero_overlap():
    target = _pr("t", ["auth/login.py"], "login")
    corpus = [
        target,
        _pr("a", ["auth/login.py"], "login retry"),  # overlaps
        _pr("b", ["totally/unrelated.go"], "xyz"),   # zero overlap -> dropped
    ]
    ranked = rank_similar(target, corpus, k=5)
    ids = [n["pr_id"] for n in ranked]
    assert ids == ["a"]
    assert ranked[0]["similarity"] > 0


class _FakeRepo:
    def __init__(self, corpus):
        self._corpus = corpus

    def similarity_corpus(self, repo_id):
        return self._corpus


def test_service_summarizes_neighbor_outcomes():
    corpus = [
        _pr("t", ["a.py", "b.py"], "feature", health=80),
        _pr("1", ["a.py", "b.py"], "feature retry", health=60, reverted=True),
        _pr("2", ["a.py"], "feature tweak", health=90, reverted=False),
    ]
    out = similar_prs(_FakeRepo(corpus), "repo1", "t", k=5)
    assert out["pr_id"] == "t"
    assert {n["pr_id"] for n in out["neighbors"]} == {"1", "2"}
    assert out["summary"]["neighbor_count"] == 2
    assert out["summary"]["reverted_count"] == 1
    assert out["summary"]["reverted_rate"] == 50.0
    assert out["summary"]["avg_health_score"] == 75.0


def test_service_handles_unknown_pr():
    out = similar_prs(_FakeRepo([]), "repo1", "missing", k=5)
    assert out["neighbors"] == []
    assert out["summary"]["neighbor_count"] == 0
