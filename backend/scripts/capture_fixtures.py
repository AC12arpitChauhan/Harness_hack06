"""LAYER 1 — fixture capture.

Hits the REAL GitHub endpoints once for a known PR and saves each raw JSON
response verbatim into tests/fixtures/github/. That captured JSON is the ground
truth ("the exact data in the exact format the /pulls endpoint sends"); after
capture, unit tests never touch the network.

Usage:
    GITHUB_TOKEN=ghp_xxx python scripts/capture_fixtures.py --repo owner/name --pr 123
"""
from __future__ import annotations

import argparse
import json
import pathlib

import httpx

from app.config import get_settings

DEFAULT_OUT = pathlib.Path("tests/fixtures/github")


def _client(token: str, api_url: str) -> httpx.Client:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=api_url.rstrip("/"), headers=headers, timeout=30.0)


def _dump(out: pathlib.Path, name: str, payload: object) -> None:
    path = out / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2))
    print(f"  wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture raw GitHub PR JSON fixtures.")
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--pr", required=True, type=int, help="PR number")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    args = parser.parse_args()

    settings = get_settings()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with _client(settings.github_token, settings.github_api_url) as c:
        print(f"Capturing {args.repo}#{args.pr} -> {out}/")
        pull = c.get(f"/repos/{args.repo}/pulls/{args.pr}").json()
        _dump(out, "pull", pull)
        _dump(out, "files", c.get(f"/repos/{args.repo}/pulls/{args.pr}/files", params={"per_page": 100}).json())
        _dump(out, "reviews", c.get(f"/repos/{args.repo}/pulls/{args.pr}/reviews", params={"per_page": 100}).json())
        _dump(out, "commits", c.get(f"/repos/{args.repo}/pulls/{args.pr}/commits", params={"per_page": 100}).json())
        sha = (pull.get("head") or {}).get("sha", "")
        _dump(out, "check_runs", c.get(f"/repos/{args.repo}/commits/{sha}/check-runs", params={"per_page": 100}).json())
    print("Done.")


if __name__ == "__main__":
    main()
