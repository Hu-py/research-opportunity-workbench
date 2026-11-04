"""Free-instance inline Research Agent execution: genuine database-backed round trip."""
import pytest
from fastapi.testclient import TestClient

import backend.api as api
from backend.team import create_member
from research_workbench.core import Paper, session_factory

HEADERS={"Authorization":"Bearer free-worker-integration-test"}

@pytest.fixture
def lab(tmp_path,monkeypatch):
    monkeypatch.setenv("APP_ENV","production")
    monkeypatch.setenv("WORKER_MODE","background")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("API_BEARER_TOKEN","free-worker-integration-test")
    monkeypatch.setenv("TEAM_BOOTSTRAP_ENABLED","false")
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    factory=session_factory("sqlite:///"+str(tmp_path/"research-lab.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    with factory() as db:
        create_member(db,"admin@example.org","Research Admin",
                      "free-test-only-password-2026",role="admin",initial=True)
        for idx in range(3):
            db.add(Paper(
                id="doi:10.0001/example"+str(idx),
                title=f"Urban graph learning and spatial analysis {idx}",
                abstract="Urban graph learning and network science",
                doi="10.0001/example"+str(idx),
                url="https://doi.org/10.0001/example"+str(idx),
                published="2026-05-01",venue="Example Research Journal",
                line_ids='["urban"]'))
        db.commit()
    with TestClient(api.app) as client:
        response=client.post("/api/auth/login",headers=HEADERS,json={
            "email":"admin@example.org","password":"free-test-only-password-2026"})
        assert response.status_code==200,response.text
        token=response.json()["token"]
        yield client,{**HEADERS,"X-Research-Session":token},monkeypatch


def test_free_inline_agent_completes_and_persists(lab):
    client,headers,_=lab
    task=client.post("/api/tasks",headers=headers,json={
        "kind":"explore","query":"urban graph learning research"})
    assert task.status_code==202,task.text
    task_id=task.json()["id"]
    detail=client.get("/api/tasks/"+task_id,headers=headers)
    assert detail.status_code==200
    data=detail.json()
    assert data["status"]=="completed"
    assert data["result"]["mode"]=="bibliographic_preview"
    assert len(data["result"]["sources"])==3
    assert any(event["step"]=="done" for event in data["events"])
    assert client.get("/api/tasks",headers=headers).json()["items"][0]["id"]==task_id


def test_queued_tasks_require_explicit_re_dispatch(lab):
    client,headers,monkeypatch=lab
    monkeypatch.setenv("WORKER_MODE","queue")
    task=client.post("/api/tasks",headers=headers,json={
        "kind":"explore","query":"urban graph learning research"})
    task_id=task.json()["id"]
    assert client.get("/api/tasks/"+task_id,headers=headers).json()["status"]=="queued"
    no=client.post("/api/tasks/"+task_id+"/dispatch",headers=headers)
    assert no.status_code==409
    monkeypatch.setenv("WORKER_MODE","background")
    dispatched=client.post("/api/tasks/"+task_id+"/dispatch",headers=headers)
    assert dispatched.status_code==200,dispatched.text
    assert client.get("/api/tasks/"+task_id,headers=headers).json()["status"]=="completed"
    again=client.post("/api/tasks/"+task_id+"/dispatch",headers=headers)
    assert again.status_code==409
