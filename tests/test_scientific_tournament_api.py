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


def test_blind_review_does_not_leak_arm_identity_before_both_ratings(client_factory):
    client,factory=client_factory
    researcher=login(client,"researcher@research.test","research-team-secret-2026")
    body={"line_id":"city","question":"Can model accuracy transfer between cities?"}
    response=client.post("/api/scientific-tournaments",headers=headers(researcher),json=body)
    assert response.status_code==202
    run_id=response.json()["id"]
    with factory() as db:
        item=db.get(tour.ScientificTournamentRun,run_id)
        item.status="completed"
        item.stage="done"
        item.outputs_json=json.dumps({
            "baseline_generator":{"ideas":[{
                "title":"Baseline title","question":"Can city models transfer?",
                "method":"Basic transfer","baselines":["No-graph"],
                "minimal_experiment":"Held-out city check","paper_ids":["p1"]
            }]},
            "seed_problem":{"id":"H_problem","title":"Agent title",
                "question":"Can city models transfer?",
                "method":"Spatial ablation",
                "falsifiable_prediction":"Domain shift worsens accuracy",
                "baselines":["No-graph"],"minimal_experiment":"Held-out city check"},
            "arbitrate":{"outcome":"single","selected_ids":["H_problem"],
                "reason":"Some evidence","stopping_reason":"Budget","unresolved_disagreements":[]}
        })
        item.trace_json=json.dumps([{"stage":"seed_problem","arm":"B","status":"completed"}])
        db.commit()
    detail=client.get("/api/scientific-tournaments/"+run_id,
                      headers=headers(researcher)).json()
    assert detail["status"]=="completed"
    assert detail["review_unblinded"] is False
    assert detail["baseline"]==[]
    assert detail["round0"]==[]
    assert detail["decision"] is None
    assert detail["trace"]==[]
    blind=client.get("/api/scientific-tournaments/"+run_id+"/blind",
                     headers=headers(researcher)).json()
    assert len(blind["cards"])==2
    assert all(len(card["ideas"])==1 for card in blind["cards"])
    assert all("id" not in card["ideas"][0] for card in blind["cards"])
    assert all("falsifiable_prediction" not in card["ideas"][0] for card in blind["cards"])
    rating={"scientific_value":3,"novelty":3,"feasibility":4,"testability":4,
            "recommendation":"investigate"}
    for label in ("方案一","方案二"):
        result=client.post("/api/scientific-tournaments/"+run_id+"/ratings",
                           headers=headers(researcher),json={**rating,"blind_id":label})
        assert result.status_code==200,result.text
    revealed=client.get("/api/scientific-tournaments/"+run_id,
                        headers=headers(researcher)).json()
    assert revealed["review_unblinded"] is True
    assert revealed["baseline"][0]["title"]=="Baseline title"
    assert revealed["round0"][0]["id"]=="H_problem"
    assert revealed["decision"]["outcome"]=="single"


def test_trial_preflight_is_read_only_and_requires_valid_line(client_factory,monkeypatch):
    monkeypatch.setenv("MODEL_VAULT_KEY","fake-nonempty-key-for-status-test")
    client,factory=client_factory
    token=login(client,"researcher@research.test","research-team-secret-2026")
    path="/api/scientific-tournaments/preflight?line_id=city"
    out=client.get(path,headers=headers(token))
    assert out.status_code==200,out.text
    data=out.json()
    assert data["does_not_invoke_model"] is True
    assert data["approved_papers"]>=1
    assert data["maximum_trial_calls"]==14
    assert data["ready"] is True
    assert client.get("/api/scientific-tournaments/preflight?line_id=missing",
                      headers=headers(token)).json()["ready"] is False
    assert client.get(path,headers=headers()).status_code==401
    with factory() as db:
        from backend.scientific_tournament import ScientificTournamentRun
        from sqlalchemy import select
        assert db.scalar(select(ScientificTournamentRun.id).limit(1)) is None


def test_pilot_guard_blocks_ephemeral_storage_for_paid_runs(client_factory,monkeypatch):
    """A read-only status check must report missing persistent storage."""
    client,factory=client_factory
    admin=login(client,"admin@research.test","research-admin-secret-2026")
    monkeypatch.setenv("SCIENTIFIC_PILOT_REQUIRE_POSTGRES","true")
    check=client.get("/api/scientific-tournaments/preflight?line_id=city",
                     headers=headers(admin))
    assert check.status_code==200
    status=check.json()
    assert status["ready"] is False
    assert status["persistent_database"] is False
    assert any("PostgreSQL" in note for note in status["notes"])
    started=client.post("/api/scientific-tournaments",
                       headers=headers(admin),
                       json={"line_id":"city",
                             "question":"Can spatial graphs transfer to new cities?"})
    assert started.status_code==422
    assert "PostgreSQL" in started.text
