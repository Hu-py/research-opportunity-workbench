"""Auth and manual-trigger API contract tests. No provider calls are made."""
import pytest
from fastapi.testclient import TestClient

import backend.api as api
import backend.scientific_agent as agent
from backend.team import create_member
from backend.model_vault import ModelCredential
from research_workbench.core import Profile, session_factory
import json


@pytest.fixture
def client_factory(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("API_BEARER_TOKEN","scientific-integration-key")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("WORKER_MODE","queue")
    factory=session_factory("sqlite:///"+str(tmp_path/"agent-api.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    monkeypatch.setattr(agent,"load_key",lambda db:"mock-key")
    # BackgroundTasks are invoked by TestClient; prevent any paid work in tests.
    monkeypatch.setattr(api,"execute_scientific_exploration",lambda *args,**kwargs:None)
    with factory() as db:
        create_member(db,"admin@lab.test","Test Admin",
                      "integration-admin-password",role="admin",initial=True)
        create_member(db,"viewer@lab.test","Test Viewer",
                      "integration-viewer-password",role="viewer")
        db.add(ModelCredential(provider="deepseek",encrypted_key="test-placeholder"))
        db.add(Profile(id=1,payload=json.dumps({"research_lines":[{
            "id":"urban","name":"Urban systems",
            "problem":"Study changing urban spatial patterns and transfer learning",
            "keywords":[],"search_queries":[],"method_queries":[]
        }]})))
        db.commit()
    with TestClient(api.app) as client:
        yield client,factory


def headers(token=None):
    result={"Authorization":"Bearer scientific-integration-key"}
    if token:result["X-Research-Session"]=token
    return result


def login(client,email,password):
    res=client.post("/api/auth/login",headers=headers(),json={
        "email":email,"password":password})
    assert res.status_code==200,res.text
    return res.json()["token"]


def test_manual_scientific_exploration_team_role_gates(client_factory):
    client,factory=client_factory
    admin=login(client,"admin@lab.test","integration-admin-password")
    viewer=login(client,"viewer@lab.test","integration-viewer-password")
    tools=client.get("/api/scientific-tools",headers=headers(admin))
    assert tools.status_code==200
    assert len(tools.json()["items"])==4
    assert client.get("/api/scientific-tools",headers=headers()).status_code==401
    payload={"line_id":"urban","question":"How do spatial networks fail under domain shift?"}
    assert client.post("/api/scientific-explorations",
                       headers=headers(viewer),json=payload).status_code==403
    started=client.post("/api/scientific-explorations",
                        headers=headers(admin),json=payload)
    assert started.status_code==202,started.text
    ident=started.json()["id"]
    assert started.json()["mode"]=="manual_only"
    detail=client.get("/api/scientific-explorations/"+ident,
                      headers=headers(viewer)).json()
    assert detail["status"]=="queued"
    assert detail["novelty_verified"] is False
    assert detail["human_review_required"] is True
    assert client.get("/api/scientific-explorations",
                      headers=headers(viewer)).json()["items"][0]["id"]==ident
    assert client.post("/api/scientific-explorations",
                       headers=headers(admin),json=payload).status_code==422
    assert client.post("/api/scientific-explorations/"+ident+"/resume",
                       headers=headers(admin)).status_code==422


def test_exploration_requires_known_profile_line(client_factory):
    client,_=client_factory
    admin=login(client,"admin@lab.test","integration-admin-password")
    payload={"line_id":"invalid-line",
             "question":"Can the unknown profile line generate science?"}
    out=client.post("/api/scientific-explorations",
                    headers=headers(admin),json=payload)
    assert out.status_code==422
    assert "不存在" in out.text
