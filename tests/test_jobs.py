from app.jobs import JobStore


def test_job_store_lifecycle(tmp_path):
    store = JobStore(tmp_path / "status")
    created = store.create("job-1", "render_3d_views")
    assert created["status"] == "queued"

    running = store.update("job-1", status="running", stage="codex_running")
    assert running["status"] == "running"

    store.write_result("job-1", {"request_id": "job-1", "artifacts": []})
    store.update("job-1", status="completed", stage="result_ready")
    assert store.read("job-1")["status"] == "completed"
    assert store.read_result("job-1")["request_id"] == "job-1"
    assert store.read("missing") is None
