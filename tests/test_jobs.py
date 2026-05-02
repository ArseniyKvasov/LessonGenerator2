import asyncio

from app.services import jobs


def test_run_job_stores_success_result(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(jobs, "JOBS_DIR", tmp_path)

    job = jobs.create_job("test_generation")

    async def handler():
        return {"status": "ok", "value": 42}

    asyncio.run(jobs.run_job(job["job_id"], handler))

    stored_job = jobs.get_job(job["job_id"])
    assert stored_job is not None
    assert stored_job["status"] == "done"
    assert stored_job["result"] == {"status": "ok", "value": 42}
    assert stored_job["message"] is None


def test_run_job_stores_error_result(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(jobs, "JOBS_DIR", tmp_path)

    job = jobs.create_job("test_generation")

    async def handler():
        return {"status": "error", "message": "Generation failed"}

    asyncio.run(jobs.run_job(job["job_id"], handler))

    stored_job = jobs.get_job(job["job_id"])
    assert stored_job is not None
    assert stored_job["status"] == "error"
    assert stored_job["result"] == {"status": "error", "message": "Generation failed"}
    assert stored_job["message"] == "Generation failed"
