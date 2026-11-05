"""Authenticated A/B tournament API smoke tests; paid model work mocked."""
import json
import pytest
from fastapi.testclient import TestClient

import backend.api as api
import backend.scientific_tournament as tour
from backend.discovery import PaperCandidate, candidate_id
from backend.model_vault import ModelCredential
from backend.team import create_member
from research_workbench.core import Paper, Profile, session_factory


@pytest.fixture
def client_factory(tmp_path,monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("API_BEARER_TOKEN","tournament-service-test-key")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("WORKER_MODE","queue")
    factory=session_factory("sqlite:///"+str(tmp_path/"tournament-api.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    monkeypatch.setattr(tour,"load_key",lambda db:"test-key")
    monkeypatch.setattr(api,"execute_scientific_tournament",lambda *args,**kwargs:None)
    with factory() as db:
        create_member(db,"admin@research.test","Research Admin",
                      "research-admin-secret-2026",role="admin",initial=True)
        create_member(db,"researcher@research.test","Researcher",
                      "research-team-secret-2026",role="researcher")
        create_member(db,"viewer@research.test","Viewer",
                      "research-viewer-secret-2026",role="viewer")
        db.add(ModelCredential(provider="deepseek",encrypted_key="mocked"))
        db.add(Profile(id=1,payload=json.dumps({"research_lines":[{
            "id":"city","name":"Urban Systems","problem":"Cross-domain validation",
            "keywords":[],"search_queries":[],"method_queries":[]
        }]})))
        db.add(Paper(id="doi:10.1234/test",title="Cross-domain urban prediction",
                     abstract="Benchmarking out-of-city accuracy",
                     doi="10.1234/test",url="https://doi.org/10.1234/test",
                     published="2025-01-01",venue="Journal of Test",
                     line_ids=json.dumps(["city"])))
        db.add(PaperCandidate(id=candidate_id("city","doi:10.1234/test"),
              line_id="city",paper_id="doi:10.1234/test",
              title="Cross-domain urban prediction",
              abstract="Benchmarking out-of-city accuracy",
              doi="10.1234/test",url="https://doi.org/10.1234/test",
              published="2025-01-01",venue="Journal of Test",
              score=80,score_reason="Reviewed",
              match_type="direct",status="relevant",matched_queries_json="[]"))
        db.commit()
    with TestClient(api.app) as client:
        yield client,factory


def headers(token=None):
    head={"Authorization":"Bearer tournament-service-test-key"}
    if token:head["X-Research-Session"]=token
    return head


def login(client,email,password):
    res=client.post("/api/auth/login",headers=headers(),json={
        "email":email,"password":password})
    assert res.status_code==200,res.text
    return res.json()["token"]


def test_tournament_roles_and_state(client_factory):
    client,factory=client_factory
    admin=login(client,"admin@research.test","research-admin-secret-2026")
    researcher=login(client,"researcher@research.test","research-team-secret-2026")
    viewer=login(client,"viewer@research.test","research-viewer-secret-2026")
    task={"line_id":"city","question":"Do spatial models generalize in a new city?"}
    assert client.post("/api/scientific-tournaments",
                       headers=headers(viewer),json=task).status_code==403
    assert client.post("/api/scientific-tournaments",
                       headers=headers(),json=task).status_code==401
    start=client.post("/api/scientific-tournaments",
                      headers=headers(researcher),json=task)
    assert start.status_code==202,start.text
    run_id=start.json()["id"]
    assert start.json()["paired_baseline"] is True
    detail=client.get("/api/scientific-tournaments/"+run_id,
                      headers=headers(viewer))
    assert detail.status_code==200
    assert detail.json()["novelty_verified"] is False
    assert detail.json()["stage"]=="baseline_planner"
    assert client.get("/api/scientific-tournaments/"+run_id+"/blind",
                      headers=headers(admin)).status_code==409
    assert client.post("/api/scientific-tournaments/"+run_id+"/ratings",
                       headers=headers(researcher),
                       json={"blind_id":"方案一","scientific_value":3,"novelty":3,
                             "feasibility":3,"testability":3,
                             "recommendation":"investigate"}).status_code==422
    feedback={"feedback_kind":"human_review","finding":"Out-of-city split is important",
              "supporting_reference":"internal-review","limitation":"Needs replication"}
    assert client.post("/api/scientific-tournaments/"+run_id+"/learning",
                       headers=headers(researcher),json=feedback).status_code==403
    assert client.post("/api/scientific-tournaments/"+run_id+"/learning",
                       headers=headers(admin),json=feedback).status_code==422
    assert client.get("/api/scientific-learning/city",
                      headers=headers(viewer)).json()["items"]==[]
