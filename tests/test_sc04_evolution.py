"""SC04: real database / API tests with mocked LLM (no external costs)."""
from __future__ import annotations

import json

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
from backend.model_vault import ModelCredential
from backend.sc04_evolution import (
    SC04Run, SC04Baseline, SC04Review, BASELINE_DRAFT,
    papers_from_strict_scan, evidence, run_view,
)
from backend.sc04_evolution_runner import execute, validate_reader, validate_transfer
from backend.task_venue_radar import TaskVenuePaperRun, TASK_KEY
from backend.team import create_member
from research_workbench.core import session_factory

TOKEN="sc04-integration-test-service-token"
ABSTRACT=("This paper examines the spatial transfer of urban environmental exposure "
          "and child health outcomes across different neighborhoods. "
          "We compare neighborhood aggregation with an inductive spatial model "
          "and report validation limits in held-out geographic districts. "
          "Independent external datasets remain necessary for generalization.")

def paper(num,group):
    return {"id":f"doi:10.55555/sc04.{num}",
       "title":f"Spatially grounded childhood environmental study number {num}",
       "abstract":ABSTRACT+f" Paper record {num}.",
       "url":f"https://doi.org/10.55555/sc04.{num}",
       "venue":f"Mock {group} Journal","doi":f"10.55555/sc04.{num}",
       "published":"2025-10-01","probe_group":group,"query":"child health external validation"}

@pytest.fixture
def workspace(tmp_path,monkeypatch):
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("API_BEARER_TOKEN",TOKEN)
    monkeypatch.delenv("MODEL_VAULT_KEY",raising=False)
    monkeypatch.delenv("SC04_DEEPSEEK_API_KEY",raising=False)
    factory=session_factory("sqlite:///"+str(tmp_path/"sc04.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    with factory() as db:
        owner=create_member(db,"lead@example.invalid","Researcher",
                            "personal-test-secret-222222",role="admin",initial=True)
        other=create_member(db,"other@example.invalid","Other",
                            "personal-test-secret-333333",role="researcher")
        db.add(TaskVenuePaperRun(id="jpaper_test_owner",member_id=owner.id,
                task_key=TASK_KEY,status="completed",
                source_ids_json=json.dumps({"A":["S100"],"B":["S200"],"C":["S300"]}),
                results_json=json.dumps([paper(1,"A"),paper(2,"B"),
                                         paper(3,"C"),paper(4,"A")],ensure_ascii=False)))
        db.commit()
    with TestClient(api.app) as client:
        def login(email,password):
            r=client.post("/api/auth/login",
              headers={"Authorization":"Bearer "+TOKEN},
              json={"email":email,"password":password})
            assert r.status_code==200,r.text
            return r.json()["token"]
        yield client,factory,login("lead@example.invalid","personal-test-secret-222222"),login(
            "other@example.invalid","personal-test-secret-333333")

def auth(token):
    return {"Authorization":"Bearer "+TOKEN,"X-Research-Session":token}

def base():
    return "/api/personal-research/me/evolution"

def store_baseline(client,token):
    r=client.put(base()+"/baseline",headers=auth(token),
      json={**{k:v for k,v in BASELINE_DRAFT.items() if k!="provenance"},"confirmed":True})
    assert r.status_code==200,r.text
    return r.json()

def prepared(client,token):
    store_baseline(client,token)
    r=client.post(base()+"/prepare",headers=auth(token))
    assert r.status_code==201,r.text
    return r.json()

def fake_model(key,model,system,payload,max_tokens=2500):
    if "papers" in payload and "paper_readings" not in payload and "variants" not in payload:
        return {"papers":[{
            "paper_id":p["id"],"problem":"Child exposure and spatial transfer",
            "method":"Urban environmental indicator comparison",
            "validation":"Geographically held-out district validation",
            "limitations":"External child outcome records are sparse",
            "evidence_excerpt":p["abstract"][:80],
        } for p in payload["papers"]]}, {"input_tokens":245,"output_tokens":112}
    if "paper_readings" in payload:
        ids=[p["id"] for p in payload["available_papers"]]
        return {"matches":[{
            "method":"Local mean feature aggregation","paper_ids":ids[:2],
            "compatibility":"ready_for_test",
            "mechanism":"Use simple local features to test contextual signal",
            "assumptions":["Comparable neighborhood context"],
            "baseline_to_compare":"Environment only XGBoost",
            "failure_risk":"Noisy linkage will distort neighborhood statistics",
        },{
            "method":"Uncertainty-aware domain adaptation","paper_ids":ids[1:3],
            "compatibility":"needs_data",
            "mechanism":"Treat target domain label uncertainty separately",
            "assumptions":["Additional reliable target labels needed"],
            "baseline_to_compare":"Mean + XGBoost",
            "failure_risk":"No reliable external labels available",
        }],"variants":[{
            "title":"Spatial holdout recalibration",
            "paper_ids":ids[:2],"hypothesis":"Predictive transfer improves under explicit domain screening",
            "baseline_to_beat":"Local mean + XGBoost",
            "minimal_test":"Compare independent spatial blocks and untouched external sites",
            "data_needed":["Road exposures","Independent validation labels"],
            "stop_condition":"No improvement in external MAE",
            "risks":["Poor labels","Source-to-target shift"]
        }]},{"input_tokens":330,"output_tokens":175}
    if "variants" in payload:
        ids=[p["id"] for p in payload["papers"]]
        return {"reviews":[{
            "variant_id":"V1","verdict":"hold","nearest_paper_ids":ids[:2],
            "fatal_issues":["External labels have not been independently quality-checked"],
            "stop_condition":"Hold if independent labels cannot be secured",
            "revised_test":"First quantify error in road-linked child outcomes",
        }]},{"input_tokens":200,"output_tokens":140}
    raise AssertionError("Unknown simulated model call")

def test_researcher_must_confirm_baseline_and_own_approved_scan(workspace):
    client,factory,owner,other=workspace
    assert client.get(base()).status_code==401
    view=client.get(base(),headers=auth(owner)).json()
    assert view["baseline"]["confirmed"] is False
    assert view["evidence"]["ready"] is True
    assert {x["group"] for x in view["evidence"]["papers"]}>={"A","B"}
    assert client.post(base()+"/prepare",headers=auth(owner)).status_code==409
    assert client.get(base(),headers=auth(other)).json()["evidence"]["ready"] is False
    assert client.post(base()+"/prepare",headers=auth(other)).status_code==409
    result=prepared(client,owner)
    assert result["status"]=="prepared"
    assert result["snapshot_sha"] and result["paper_count"]==4
    assert result["snapshot"]["source_scan"]=="jpaper_test_owner"
    assert client.get(base()+"/runs/"+result["id"],headers=auth(other)).status_code==404
    with factory() as db:
        assert db.get(SC04Baseline,(db.scalar(select(SC04Run.member_id)),TASK_KEY)) is not None
        assert db.query(SC04Review).count()==0

def test_no_configured_model_no_paid_call_no_side_effect(workspace):
    client,factory,owner,other=workspace
    run=prepared(client,owner)
    reply=client.post(base()+"/runs/"+run["id"]+"/start",headers=auth(owner),
        json={"acknowledge_external_model":False})
    assert reply.status_code==422
    reply=client.post(base()+"/runs/"+run["id"]+"/start",headers=auth(owner),
        json={"acknowledge_external_model":True})
    assert reply.status_code==409
    assert "Key" in reply.json()["detail"]
    with factory() as db:
        assert db.get(SC04Run,run["id"]).status=="prepared"
        assert db.get(SC04Run,run["id"]).model_calls==0

def test_checkpointed_evidence_reader_transfer_critic_and_feedback(workspace,monkeypatch):
    client,factory,owner,other=workspace
    run=prepared(client,owner)
    vault_key=Fernet.generate_key().decode()
    monkeypatch.setenv("MODEL_VAULT_KEY",vault_key)
    with factory() as db:
        db.add(ModelCredential(provider="deepseek",
          encrypted_key=Fernet(vault_key.encode()).encrypt(b"test-mock-provider-token").decode(),
          fast_model="deepseek-flash",reason_model="deepseek-flash"))
        row=db.get(SC04Run,run["id"]);row.status="queued";db.commit()
    assert execute(factory,run["id"],model_call=fake_model)
    with factory() as db:
        item=db.get(SC04Run,run["id"])
        assert item.status=="completed"
        assert item.stage=="done"
        assert item.model_calls==3
        assert item.input_tokens>0 and item.output_tokens>0
    response=client.get(base()+"/runs/"+run["id"],headers=auth(owner))
    assert response.status_code==200
    result=response.json()["run"]
    assert len(result["readings"])==4
    assert len(result["matches"])==2
    assert len(result["variants"])==1
    assert result["critic"][0]["verdict"]=="hold"
    assert result["variants"][0]["novelty_status"]=="not_systematically_verified"
    assert result["novelty_verified"] is False
    assert client.get(base()+"/runs/"+run["id"],headers=auth(other)).status_code==404
    unauthorized=client.post(base()+"/runs/"+run["id"]+"/review",headers=auth(other),json={
      "paper_accuracy":4,"method_fit":3,"novelty_caution":5,
      "experiment_feasibility":2,"usefulness":4,
      "target":"reader","decision":"revise","comment":"Need actual full text"})
    assert unauthorized.status_code==404
    saved=client.post(base()+"/runs/"+run["id"]+"/review",headers=auth(owner),json={
      "paper_accuracy":4,"method_fit":3,"novelty_caution":5,
      "experiment_feasibility":2,"usefulness":4,
      "target":"reader","decision":"revise",
      "comment":"Reader still needs independent review of methods"})
    assert saved.status_code==201,saved.text
    assert client.get(base()+"/runs/"+run["id"],headers=auth(owner)).json()["feedback"][0]["decision"]=="revise"

def test_fake_evidence_or_unseen_reference_is_rejected():
    p=[{"id":"paper-A","abstract":ABSTRACT}]
    with pytest.raises(ValueError,match="逐字定位"):
        validate_reader({"papers":[{
          "paper_id":"paper-A","problem":"p","method":"m","validation":"v","limitations":"l",
          "evidence_excerpt":"This source definitely proved a new medical treatment"}]},p)
    with pytest.raises(ValueError,match="未收录"):
        validate_transfer({"matches":[{
          "method":"Spatial GNN","paper_ids":["fake-id"],
          "compatibility":"ready_for_test","mechanism":"m",
          "assumptions":["a"],"baseline_to_compare":"B1","failure_risk":"risk"
        },{
          "method":"Spatial XGB","paper_ids":["paper-A"],
          "compatibility":"unsuitable","mechanism":"m",
          "assumptions":["a"],"baseline_to_compare":"B2","failure_risk":"risk"
        }],
        "variants":[{"title":"var1","paper_ids":["paper-A"],"hypothesis":"h",
          "baseline_to_beat":"B2","minimal_test":"test",
          "data_needed":["data"],"stop_condition":"stop","risks":["risk"]}]},p)

def test_sc04_render_key_reused_securely_and_only_for_manual_member_run(workspace,monkeypatch):
    """Owner must still explicitly start; no vault, GitHub secrets or plaintext logs."""
    import backend.sc04_evolution_runner as runner
    client,factory,owner,other=workspace
    example_key="sc04-mocked-provider-key-not-a-real-secret"
    monkeypatch.setenv("SC04_DEEPSEEK_API_KEY",example_key)
    over=client.get(base(),headers=auth(owner))
    assert over.status_code==200
    model=over.json()["model"]
    assert model["configured"] is True and model["vault_ready"] is True
    assert model["key_storage"]=="render-environment-sc04-only"
    assert model["daily_enabled"] is False
    assert example_key not in over.text
    # No implied permission for other users to see the owner's papers.
    assert client.get(base(),headers=auth(other)).json()["evidence"]["ready"] is False
    run=prepared(client,owner)
    with factory() as db:
        assert db.get(SC04Run,run["id"]).model_calls == 0
    # Opt-in is mandatory even when the server key exists.
    denied=client.post(base()+"/runs/"+run["id"]+"/start",headers=auth(owner),
                       json={"acknowledge_external_model":False})
    assert denied.status_code==422
    def fake_paid_call(key,model,system,payload,max_tokens=2500):
        assert key==example_key
        assert model=="deepseek-flash"
        return fake_model(key,model,system,payload,max_tokens=max_tokens)
    monkeypatch.setattr(runner,"request_json",fake_paid_call)
    accepted=client.post(base()+"/runs/"+run["id"]+"/start",headers=auth(owner),
                         json={"acknowledge_external_model":True})
    assert accepted.status_code==202,accepted.text
    detail=client.get(base()+"/runs/"+run["id"],headers=auth(owner))
    assert detail.status_code==200 and detail.json()["run"]["status"]=="completed"
    assert detail.json()["run"]["model_calls"]==3
    assert len(detail.json()["run"]["variants"])==1
    assert example_key not in detail.text
    from backend.model_vault import status as legacy_model_status
    with factory() as db:
        assert legacy_model_status(db)["configured"] is False
