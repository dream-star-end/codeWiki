from pathlib import Path
from typing import Optional

from git import Repo

from app.models.schemas import IngestRequest


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2] / "workspace"


def ingest_repo(request: IngestRequest, repo_id: str) -> Optional[Path]:
    workspace = _workspace_root()
    workspace.mkdir(parents=True, exist_ok=True)

    if request.local_path:
        local_path = Path(request.local_path).resolve()
        if not local_path.exists():
            raise FileNotFoundError(f"local path not found: {local_path}")
        return local_path

    if not request.url:
        raise ValueError("either url or local_path must be provided")

    target = workspace / repo_id
    Repo.clone_from(request.url, target, depth=1, branch=request.branch)

    if request.commit:
        repo = Repo(target)
        repo.git.checkout(request.commit)

    return target
