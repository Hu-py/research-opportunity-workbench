"""SC05 authenticated paper-based A/B API integration (offline fake LLM).

All model calls and source PDFs are synthetic test fixtures: these tests
validate authorization, source freezing, budget reservation, audit and privacy.
Passing does NOT mean DeepSeek's scientific quality was tested.
"""
from __future__ import annotations

import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
import backend.sc05_eval_api as ev
from backend.sc05_eval_api import SC05Case, SC05Run, SC05Rating
from backend.team import TeamMember, create_member
from research_workbench.core import session_factory

TOKEN="sc05-testing-backend-service-token"
BASE="/api/personal-research/me/sc05"
PAGE=(
 "This independent paper investigates what happens to a transportation "
 "network when severe rainfall changes passenger demand. "
 "We report multi-stage analysis and compare generated transport scenarios."
)
METH=(
 "We observe hourly station demand and compute segment flow using generalized "
 "travel-time minimum paths. Several results come from simulated network "
 "closure experiments, rather than observed additional events."
)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("API_BEARER_TOKEN",TOKEN)
    monkeypatch.setenv("SC04_DEEPSEEK_API_KEY","mock-only-key-never-real")
    factory=session_factory("sqlite:///"+str(tmp_path/"sc05.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    with factory() as db:
        owner=create_member(db,"owner@example.invalid","Owner",
                      "sc05-test-password-222222",role="admin",initial=True)
        other=create_member(db,"member@example.invalid","Member",
                      "sc05-test-password-333333",role="researcher")
        owner.role="owner"
        db.commit()
    with TestClient(api.app) as client:
        def login(email,password):
            result=client.post("/api/auth/login",
                headers={"Authorization":"Bearer "+TOKEN},
                json={"email":email,"password":password})
            assert result.status_code==200,result.text
            return result.json()["token"]
        yield (client,factory,login("owner@example.invalid","sc05-test-password-222222"),
             login("member@example.invalid","sc05-test-password-333333"))


def auth(token):
    return {"Authorization":"Bearer "+TOKEN, "X-Research-Session":token}


def upload(client,token):
    response=client.post(BASE+"/cases",headers=auth(token),
         json={"title":"Original published research article",
               "pages":{"page_01":PAGE,"page_02":METH}})
    assert response.status_code==201,response.text
    return response.json()["id"]


def fake_run_paper(pdf,key,*,model_call,pages_override,source_sha,
                   frozen_snapshot,scientific_value_gate,**kwargs):
    assert pdf is None
    assert key=="mock-only-key-never-real"
    assert "page_01" in pages_override
    first=not scientific_value_gate
    assert (frozen_snapshot is not None)==(not first)
    answer,usage=model_call(key,"deepseek-flash","A bounded test prompt",
         {"sc05_stage":"fake_validation","facts":len(pages_override)},
         max_tokens=250)
    assert answer=={"mock":"real schema not sent","scientific":False}
    fact={"fact_id":"F001","fact_type":"objective",
          "statement":"Paper assesses network response",
          "source_id":"uploaded_paper","section":"page_01",
          "verbatim_excerpt":"This independent paper investigates what happens to a transportation",
          "evidence_origin":"author_reported"}
    from backend.sc05_research_diagnosis import freeze_blind_input
    frozen=frozen_snapshot or freeze_blind_input(
       {"uploaded_paper":pages_override},
       research_question="Assess network disruption mechanisms",
       study_unit="Transit network",facts=[fact])
    output={"snapshot":frozen,
            "quality":{"structural_status":"structurally_complete"},
            "usage":[{"input_tokens":usage["input_tokens"],
                      "output_tokens":usage["output_tokens"]}],
            "version":"test-double"}
    return "# Autonomous science analysis "+("B" if scientific_value_gate else "A"),output


def test_auth_consent_frozen_ab_checkpoint_audit_and_rating(workspace,monkeypatch):
    client,factory,owner,other=workspace
    assert client.get(BASE).status_code==401
    assert client.get(BASE,headers={"Authorization":"Bearer "+TOKEN}).status_code==401
    assert client.get(BASE,headers=auth(other)).status_code==403
    assert client.post(BASE+"/cases",headers=auth(other),
                       json={"title":"Some text","pages":{"page_01":PAGE}}).status_code==403
    calls=[]
    def fake_provider(key,model,system,payload,max_tokens=100):
        calls.append({"stage":payload["sc05_stage"],"model":model})
        return {"mock":"real schema not sent","scientific":False},{"input_tokens":51,"output_tokens":31}
    monkeypatch.setattr(ev,"request_json",fake_provider)
    monkeypatch.setattr(ev,"run_paper",fake_run_paper)
    case_id=upload(client,owner)
    pair=client.post(BASE+"/cases/"+case_id+"/ab",headers=auth(owner)).json()
    run_a,run_b=pair["runs"]
    assert len(pair["runs"])==2
    assert not calls
    assert client.post(BASE+"/runs/"+run_b["id"]+"/start",
        headers=auth(owner),json={"acknowledge_external_model":True}).status_code==409
    assert client.post(BASE+"/runs/"+run_a["id"]+"/start",
        headers=auth(owner),json={"acknowledge_external_model":False}).status_code==422
    assert client.post(BASE+"/runs/"+run_a["id"]+"/start",
        headers=auth(other),json={"acknowledge_external_model":True}).status_code==403
    assert not calls
    a=client.post(BASE+"/runs/"+run_a["id"]+"/start",
       headers=auth(owner),json={"acknowledge_external_model":True})
    assert a.status_code==202,a.text
    assert len(calls)==1
    detail=client.get(BASE+"/runs/"+run_a["id"],headers=auth(owner)).json()
    assert detail["status"]=="completed"
    assert "analysis A" in detail["report_md"]
    assert detail["model_calls"]==1
    assert detail["input_tokens"]==51
    audit=client.get(BASE+"/runs/"+run_a["id"]+"/audit",headers=auth(owner)).json()
    assert audit["variant"]=="science_gate_off"
    assert audit["checkpoints"][0]["response"]["mock"]=="real schema not sent"
    assert "mock-only-key-never-real" not in json.dumps(audit)
    assert client.get(BASE+"/runs/"+run_a["id"]+"/audit",headers=auth(other)).status_code==403
    b=client.post(BASE+"/runs/"+run_b["id"]+"/start",
       headers=auth(owner),json={"acknowledge_external_model":True})
    assert b.status_code==202,b.text
    assert len(calls)==2
    with factory() as db:
        case=db.get(SC05Case,case_id)
        assert case.shared_evidence_json
        runs=db.scalars(select(SC05Run).where(SC05Run.case_id==case_id)).all()
        assert len(runs)==2
    blind=client.get(BASE+"/pairs/"+pair["pair_id"]+"/blind",headers=auth(owner)).json()
    assert blind["ready"] is True
    assert len(blind["blind_reports"])==2
    assert all("variant" not in r for r in blind["blind_reports"])
    review=client.post(BASE+"/runs/"+run_b["id"]+"/review",
      headers=auth(owner),json={"accuracy":5,"science_value":4,
        "narrative":4,"literature":3,"feasibility":4,
        "hard_failure":False,"feedback":"Good new system mechanism"})
    assert review.status_code==201,review.text
    assert review.json()["score"]==79
    assert client.post(BASE+"/runs/"+run_b["id"]+"/review",headers=auth(owner),
       json={"accuracy":5,"science_value":4,"narrative":4,"literature":3,"feasibility":4}).status_code==409
    with factory() as db:
        assert db.query(SC05Rating).count()==1


def test_blind_future_recommendations_are_stripped_at_ingestion(workspace):
    client,_,owner,_=workspace
    response=client.post(BASE+"/cases",headers=auth(owner),json={
      "title":"A separate published methods study",
      "pages":{"page_01":PAGE,
               "page_02":METH+"\nDiscussion\nFuture work should explicitly test a specific system mechanism."},
    })
    assert response.status_code==201,response.text
    with workspace[1]() as db:
        case=db.get(SC05Case,response.json()["id"])
        assert "Future work should" not in case.pages_json
        assert "generalized" in case.pages_json


def test_pdf_binary_ingestion_is_owner_only_and_has_verified_hash(workspace,tmp_path):
    fitz=pytest.importorskip("fitz")
    client,factory,owner,other=workspace
    doc=fitz.open()
    for text in [PAGE,METH]:
        page=doc.new_page()
        page.insert_textbox(fitz.Rect(35,35,550,720),text,fontsize=10)
    pdf=doc.tobytes()
    doc.close()
    headers={**auth(owner),"Content-Type":"application/pdf",
             "X-Research-Paper-Title":"PDF source upload test"}
    assert client.post(BASE+"/cases/pdf",data=pdf,headers=auth(other)|{
       "Content-Type":"application/pdf"}).status_code==403
    r=client.post(BASE+"/cases/pdf",content=pdf,headers=headers)
    assert r.status_code==201,r.text
    assert r.json()["sha256"]==hashlib.sha256(pdf).hexdigest()
    with factory() as db:
        assert db.get(SC05Case,r.json()["id"]).source_type=="uploaded_pdf"


def test_no_side_effect_on_reads(workspace):
    client,factory,owner,_=workspace
    case=upload(client,owner)
    pair=client.post(BASE+"/cases/"+case+"/ab",headers=auth(owner)).json()
    for _ in range(2):
        assert client.get(BASE,headers=auth(owner)).status_code==200
        assert client.get(BASE+"/runs/"+pair["runs"][0]["id"],
            headers=auth(owner)).status_code==200
    with factory() as db:
        assert all(r.calls==0 and r.status=="prepared" for r in db.query(SC05Run).all())
