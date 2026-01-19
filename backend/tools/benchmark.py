from __future__ import annotations

import argparse
import time
from pathlib import Path

from app.services.analysis import run_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Run analysis benchmark")
    parser.add_argument("repo_path", help="Path to repository")
    parser.add_argument("--repo-id", default="bench_repo", help="Repo id")
    args = parser.parse_args()

    repo_root = Path(args.repo_path).resolve()
    if not repo_root.exists():
        raise SystemExit(f"repo not found: {repo_root}")

    start = time.time()
    run_analysis(args.repo_id, str(repo_root), include=None, exclude=None)
    elapsed = time.time() - start
    print(f"analysis_seconds={elapsed:.2f}")


if __name__ == "__main__":
    main()
