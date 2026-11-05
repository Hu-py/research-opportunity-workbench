"""Role-safe autonomous research endpoints: no human paper gate, no early feedback."""
import json
import pytest
from fastapi.testclient import TestClient
import backend.api as api
import backend.research_evolution as evolution
import backend.research_evolution_api as evolution_api
from backend.model_vault import ModelCredential
from backend.team import create_member
from research_workbench.core import Profile, session_factory


@pytest.fixture
def hosted(tmp_path,monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("API_BEARER_TOKEN","autonomous-evo-service-token")
    monkeypatch.setenv("MODEL_VAULT_KEY","mock-vault-enabled")
    monkeypatch.setenv("APP_ENV","development")
    db_factory=session_factory("sqlite:///"+str(tmp_path/"api.db"))
    monkeypatch.setattr(api,"get_factory",lambda:db_factory)
    monkeypatch.setattr(evolution,"load_key",lambda db:"test-model-key")
    monkeypatch.setattr(evolution_api,"execute",lambda *args,**kwargs:None)
    with db_factory() as db:
        create_member(db,"admin@lab.test","Admin","secure-admin-pass-2026",
                      role="admin",initial=True)
        create_member(db,"researcher@lab.test","Researcher","secure-research-pass-2026",
                      role="researcher")
        create_member(db,"viewer@lab.test","Viewer","secure-viewer-pass-2026",
                      role="viewer")
        db.add(ModelCredential(provider="deepseek",encrypted_key="mock"))
        db.add(Profile(id=1,payload=json.dumps({"research_lines":[
            {"id":"city","name":"Urban graph science",
             "problem":"Cross-city spatial graph domain shifts",
             "keywords":[],"search_queries":[],"method_queries":[]}]})))
        db.commit()
    with TestClient(api.app) as client:yield client,db_factory


def head(token=None):
    h={"Authorization":"Bearer autonomous-evo-service-token"}
    if token:h["X-Research-Session"]=token
    return h


def login(client,email,password):
    r=client.post("/api/auth/login",headers=head(),json={
        "email":email,"password":password})
    assert r.status_code==200,r.text
    return r.json()["token"]


def test_permissions_and_evidence_first_entry(hosted):
    client,factory=hosted
    user=login(client,"researcher@lab.test","secure-research-pass-2026")
    viewer=login(client,"viewer@lab.test","secure-viewer-pass-2026")
    assert client.get("/api/research-evolution/readiness?line_id=city",
                      headers=head()).status_code==401
    check=client.get("/api/research-evolution/readiness?line_id=city",
                     headers=head(user))
    assert check.status_code==200,check.text
    assert check.json()["ready"] is True
    assert check.json()["paper_human_approval_required"] is False
    assert client.post("/api/research-evolution",
                       headers=head(viewer),json={"line_id":"city"}).status_code==403
    created=client.post("/api/research-evolution",
                        headers=head(user),json={"line_id":"city"})
    assert created.status_code==202,created.text
    rid=created.json()["id"]
    assert created.json()["human_review_stage"]=="final_package_only"
    assert len(client.get("/api/research-evolution",headers=head(user)).json()["items"])==1
    detail=client.get("/api/research-evolution/"+rid,headers=head(user)).json()
    assert detail["stage"]=="plan"
    assert detail["recommendation"] is None
    assert detail["novelty_verified"] is False
    assert client.post("/api/research-evolution/"+rid+"/feedback",
                       headers=head(user),json={
                         "decision":"adopt","scientific_value":5,
                         "novelty":5,"feasibility":5,"testability":5}).status_code==422
    report=client.get("/api/research-evolution/policy",headers=head(user)).json()
    assert report["model_weight_training"] is False
    assert sum(x["trials"] for x in report["policies"])==0
