import threading
import uuid
from typing import Dict, Optional

from app.models.schemas import JobStatus
from app.services.jobs_db import upsert_job, read_job


_lock = threading.Lock()
_jobs: Dict[str, JobStatus] = {}


def create_job() -> str:
    job_id = f"job_{uuid.uuid4().hex}"
    with _lock:
        status = JobStatus(status="queued", progress=0, error=None, stage="初始化", detail="任务已创建，等待处理")
        _jobs[job_id] = status
    upsert_job(job_id, status.status, status.progress, status.error)
    return job_id


def set_job(
    job_id: str,
    status: str,
    progress: int,
    error: Optional[str] = None,
    stage: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    with _lock:
        _jobs[job_id] = JobStatus(status=status, progress=progress, error=error, stage=stage, detail=detail)
    upsert_job(job_id, status, progress, error)


def is_job_canceled(job_id: str) -> bool:
    job = get_job(job_id)
    return job.status == "canceled"


def get_job(job_id: str) -> JobStatus:
    with _lock:
        job = _jobs.get(job_id)
    if job:
        return job
    db_row = read_job(job_id)
    if not db_row:
        return JobStatus(status="failed", progress=0, error="job not found")
    return JobStatus(status=db_row["status"], progress=db_row["progress"], error=db_row["error"])
