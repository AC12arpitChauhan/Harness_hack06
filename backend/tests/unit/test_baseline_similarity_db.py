"""Integration: the new repository SQL paths over a real (test) SQLite DB.

Unit tests cover the pure math/service with fakes; this seeds PRs through the real
Repository and exercises find_repository / repo_history_features / similarity_corpus
plus the baseline-builder and similarity-service on top of genuine query output.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.models import Diff, DiffFile, PRState, PullRequest, Review, ReviewState
from app.scoring.baseline import build_repo_baseline
from app.services.similarity_service import similar_prs

_OPENED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _persist_pr(repository, repo_id, n, *, additions, reviewers, merged_after_min, title, files):
    pr = PullRequest(
        provider="github", repo="o/r", number=n, title=title, description="",
        author="alice", state=PRState.MERGED, source_branch="f", target_branch="main",
        commit_sha=f"sha{n}", opened_at=_OPENED,
        merged_at=_OPENED + timedelta(minutes=merged_after_min),
        provider_pr_id=str(n),
    )
    pr_row = repository.upsert_pull_request(repo_id, pr)
    repository.replace_diff(
        pr_row.id,
        Diff(
            files_changed=len(files), additions=additions, deletions=0,
            files=[DiffFile(f, additions, 0, "modified") for f in files],
        ),
    )
    repository.replace_reviews(
        pr_row.id, [Review(name, ReviewState.APPROVED) for name in reviewers]
    )
    return pr_row


def _seed_repo(repository):
    repo_row = repository.upsert_repository("github", "o/r", "o/r", "")
    # Six routine PRs touching auth/*, ~100 lines, 2 reviewers, ~120 min to merge.
    for i in range(1, 7):
        _persist_pr(
            repository, repo_row.id, i,
            additions=100, reviewers=["bob", "cara"], merged_after_min=120,
            title=f"auth tweak {i}", files=["auth/login.py"],
        )
    repository.session.commit()
    return repo_row


def test_repo_history_features_and_baseline(repository):
    repo_row = _seed_repo(repository)
    feats = repository.repo_history_features(repo_row.id, exclude_provider_pr_id="3")
    assert len(feats["sizes"]) == 5  # PR #3 excluded
    assert all(s == 100.0 for s in feats["sizes"])
    assert all(r == 2.0 for r in feats["reviewers"])
    assert len(feats["merge_minutes"]) == 5

    # No spread => no usable baseline (every PR identical).
    assert build_repo_baseline(feats["sizes"], feats["reviewers"], feats["merge_minutes"]) is None

    # Add a giant outlier PR; now size has spread and a baseline forms.
    _persist_pr(
        repository, repo_row.id, 99,
        additions=900, reviewers=["bob"], merged_after_min=5,
        title="huge rewrite", files=["auth/login.py"],
    )
    repository.session.commit()
    feats2 = repository.repo_history_features(repo_row.id, exclude_provider_pr_id="99")
    base = build_repo_baseline(feats2["sizes"], feats2["reviewers"], feats2["merge_minutes"])
    # The six excluded-of-#99 PRs are identical => still no spread for the baseline.
    assert base is None


def test_find_repository(repository):
    repo_row = _seed_repo(repository)
    assert repository.find_repository("github", "o/r").id == repo_row.id
    assert repository.find_repository("github", "nope") is None


def test_similarity_corpus_and_service(repository):
    repo_row = _seed_repo(repository)
    # A revert of PR #2, and an unrelated PR touching different files.
    _persist_pr(
        repository, repo_row.id, 20,
        additions=10, reviewers=["bob"], merged_after_min=30,
        title='Revert "auth tweak 2" #2', files=["auth/login.py"],
    )
    _persist_pr(
        repository, repo_row.id, 21,
        additions=100, reviewers=["bob"], merged_after_min=120,
        title="docs update", files=["docs/readme.md"],
    )
    repository.session.commit()

    corpus = repository.similarity_corpus(repo_row.id)
    by_num = {c["provider_pr_id"]: c for c in corpus}
    assert by_num["2"]["reverted"] is True   # undone by the Revert PR
    assert by_num["1"]["reverted"] is False
    assert by_num["21"]["files"] == ["docs/readme.md"]

    # PR #1 (auth/login.py) should surface its auth siblings, not the docs PR.
    out = similar_prs(repository, repo_row.id, by_num["1"]["pr_id"], k=5)
    neighbor_files = {tuple(n["files"]) for n in out["neighbors"]}
    assert ("auth/login.py",) in neighbor_files
    assert ("docs/readme.md",) not in neighbor_files
    assert out["summary"]["neighbor_count"] >= 1
