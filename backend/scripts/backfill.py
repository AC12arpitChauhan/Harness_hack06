"""Backfill a repo's recent PRs into the DB so dashboard GETs show real data.

Runs each PR through the SAME analyze->score->persist path (NO writeback, NO live
trigger), reusing services.backfill_service.

Usage:
    GITHUB_TOKEN=ghp_xxx python scripts/backfill.py --repo owner/name --since-days 30
"""
from __future__ import annotations

import argparse
import json

from app.config import get_settings
from app.persistence.db import init_db
from app.services.backfill_service import backfill_repo


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill PR analyses for a repository.")
    parser.add_argument("--provider", default="github")
    parser.add_argument("--repo", required=True, help="owner/name (or Harness repo ref)")
    parser.add_argument("--since-days", type=int, default=30)
    args = parser.parse_args()

    init_db()  # zero-setup: ensure tables exist
    summary = backfill_repo(args.provider, args.repo, args.since_days, get_settings())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
