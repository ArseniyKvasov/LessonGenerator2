import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, Optional
from uuid import uuid4


JobStatus = Literal["queued", "running", "done", "error"]
JobHandler = Callable[[], Awaitable[dict[str, Any]]]

logger = logging.getLogger(__name__)

JOBS_DIR = Path("data/jobs")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _ensure_jobs_dir() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _write_job(job: dict[str, Any]) -> None:
    _ensure_jobs_dir()
    path = _job_path(job["job_id"])
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(job, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _update_job(job_id: str, **changes: Any) -> dict[str, Any]:
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job {job_id} does not exist")
    job.update(changes)
    job["updated_at"] = _utc_now()
    _write_job(job)
    return job


def create_job(job_type: str) -> dict[str, Any]:
    job = {
        "job_id": uuid4().hex,
        "job_type": job_type,
        "status": "queued",
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "result": None,
        "message": None,
    }
    _write_job(job)
    return job


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.exception("Could not read job file %s", path)
        return {
            "job_id": job_id,
            "status": "error",
            "message": "Job state is corrupted",
            "result": None,
        }


async def run_job(job_id: str, handler: JobHandler) -> None:
    _update_job(job_id, status="running")
    try:
        result = await handler()
    except asyncio.CancelledError:
        _update_job(job_id, status="error", message="Job was cancelled", result=None)
        raise
    except Exception as error:
        logger.exception("Job %s failed", job_id)
        _update_job(job_id, status="error", message=str(error), result=None)
        return

    if result.get("status") == "error":
        _update_job(
            job_id,
            status="error",
            message=result.get("message") or "Generation failed",
            result=result,
        )
        return

    _update_job(job_id, status="done", message=None, result=result)
