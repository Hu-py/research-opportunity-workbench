"""Offline end-to-end scientific Agent tests with real database checkpoints."""
import json

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from research_workbench.core import Base, Profile
from backend.model_vault import ModelCredential
from backend.scientific_agent import (
    ScientificExplorationRun, create_run, execute, as_dict, resume,
)
from backend.research_budget import ResearchDailyBudget
import backend.scientific_agent as agent


def setup(tmp_path, monkeypatch):
    engine=create_engine("sqlite:///"+str(tmp_path/"scientific-agent.db"))
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    profile={"research_lines":[{
        "id":"city", "name":"Urban science",
        "problem":"Does graph transfer learning generalize across urban contexts?",
        "keywords":[],"search_queries":[],"method_queries":[]
    }]}
    with factory() as db:
        db.add(Profile(id=1,payload=json.dumps(profile)))
        db.add(ModelCredential(provider="deepseek",encrypted_key="placeholder",
                               reason_model="deepseek-flash"))
        db.commit()
    monkeypatch.setattr(agent,"load_key",lambda db:"test-only-key")
    return factory


def mock_scholarly_api(request):
    if request.url.host=="api.openalex.org":
        assert request.method=="GET"
        return httpx.Response(200,json={"results":[{
            "id":"https://openalex.org/W7",
            "title":"Graph models and spatial transfer",
            "doi":"https://doi.org/10.1234/graphtransfer",
            "publication_date":"2025-01-01",
        }]})
    if request.url.host=="api.crossref.org":
        return httpx.Response(200,json={"message":{
            "DOI":"10.1234/graphtransfer",
            "title":["Graph models and spatial transfer"],
            "type":"journal-article","publisher":"Research"
        }})
    raise AssertionError("Unexpected endpoint: "+str(request.url))


def test_agent_selects_tools_and_generates_cited_hypothesis(tmp_path,monkeypatch):
    factory=setup(tmp_path,monkeypatch)
    decisions=[]
    def model_call(key,model,system,payload,client=None,max_tokens=1700):
        assert key=="test-only-key"
        decisions.append(payload)
        assert "tool_catalog" in payload
        n=len(decisions)
        if n==1:
            return ({"action":"call_tool","tool_name":"openalex.search_papers",
                "arguments":{"query":"graph generalization in cities",
                             "since":"2024-01-01","limit":2},
                "reason":"Search candidate evidence"}, {"input_tokens":40,"output_tokens":20})
        if n==2:
            assert payload["evidence"][0]["id"]=="E1"
            return ({"action":"call_tool","tool_name":"crossref.lookup_doi",
                "arguments":{"doi":"10.1234/graphtransfer"},
                "reason":"Verify DOI metadata"}, {"input_tokens":70,"output_tokens":25})
        assert n==3
        return ({"action":"finalize","hypothesis":{
            "research_question":"Does spatial domain shift invalidate graph transfer?",
            "mechanism":"Neighborhood graphs differ by spatial context",
            "falsifiable_prediction":"Cross-city accuracy drops after shift",
            "methods":"Cross-city graph learning with controls",
            "baselines":["Random forest","No-neighbor model"],
            "minimal_experiment":"Compare city-held-out MAE and transfer gap",
            "supporting_evidence_ids":["E1","E2"],
            "counter_evidence_ids":[],
            "limitations":["Metadata is insufficient for full novelty judgment"],
            "next_searches":["Find direct out-of-distribution tests"]
        }},{"input_tokens":80,"output_tokens":35})
    with factory() as db:
        run=create_run(db,"city","Research graph transfer outside its training domain","member-one")
        run_id=run.id
    with httpx.Client(transport=httpx.MockTransport(mock_scholarly_api)) as http:
        assert execute(factory,run_id,model_call=model_call,tool_client=http)
    with factory() as db:
        run=db.get(ScientificExplorationRun,run_id)
        result=as_dict(run)
        assert result["status"]=="completed"
        assert result["tool_calls"]==2
        assert result["model_calls"]==3
        assert result["steps"]==3
        assert [e["id"] for e in result["evidence"]]==["E1","E2"]
        assert result["hypothesis"]["novelty_status"]=="unverified"
        assert result["hypothesis"]["human_review_required"]
        assert result["hypothesis"]["data_access_verified"] is False
        budget=db.get(ResearchDailyBudget,agent.now().date().isoformat())
        assert budget.reserved_calls==3
        assert budget.actual_input_tokens==190
    assert not execute(factory,run_id,model_call=model_call)
    assert len(decisions)==3


def test_agent_rejects_unknown_tool_without_dispatch(tmp_path,monkeypatch):
    factory=setup(tmp_path,monkeypatch)
    with factory() as db:
        ident=create_run(db,"city","Explore graph generalization hypotheses","member-one").id
    def mock_model(*args,**kwargs):
        return ({"action":"call_tool","tool_name":"shell.exec",
                 "arguments":{"command":"rm -rf /"},"reason":"test"},
                {"input_tokens":12,"output_tokens":5})
    assert not execute(factory,ident,model_call=mock_model)
    with factory() as db:
        run=db.get(ScientificExplorationRun,ident)
        assert run.status=="failed"
        assert run.tool_calls==0
        assert "未授权工具" in run.error
        assert run.model_calls==1


def test_agent_does_not_accept_fabricated_evidence_id(tmp_path,monkeypatch):
    factory=setup(tmp_path,monkeypatch)
    with factory() as db:
        ident=create_run(db,"city","Explore graph generalization hypotheses","member-one").id
    def model(*args,**kwargs):
        return ({"action":"finalize","hypothesis":{
            "research_question":"Check model invariance",
            "mechanism":"Spatial interaction changes",
            "falsifiable_prediction":"Observed accuracy falls",
            "methods":"Matched evaluation",
            "baselines":["Naive baseline"],
            "minimal_experiment":"Held-out evaluation",
            "supporting_evidence_ids":["E999"],
            "counter_evidence_ids":[],
            "limitations":["Unknown inputs"],"next_searches":[]
        }},{"input_tokens":10,"output_tokens":20})
    assert not execute(factory,ident,model_call=model)
    with factory() as db:
        run=db.get(ScientificExplorationRun,ident)
        assert run.status=="failed"
        assert "不存在" in run.error
        assert json.loads(run.result_json)=={}


def test_agent_missing_evidence_is_not_marked_complete(tmp_path,monkeypatch):
    factory=setup(tmp_path,monkeypatch)
    with factory() as db:
        ident=create_run(db,"city","Explore graph generalization hypotheses","member-one").id
    def model(*args,**kwargs):
        return ({"action":"finalize","hypothesis":{
            "research_question":"Check model invariance",
            "mechanism":"Spatial interaction changes",
            "falsifiable_prediction":"Observed accuracy falls",
            "methods":"Matched evaluation",
            "baselines":["Naive baseline"],
            "minimal_experiment":"Held-out evaluation",
            "supporting_evidence_ids":[],
            "counter_evidence_ids":[],
            "limitations":["No external evidence"],"next_searches":["Run search"]
        }},{"input_tokens":10,"output_tokens":20})
    assert not execute(factory,ident,model_call=model)
    with factory() as db:
        run=db.get(ScientificExplorationRun,ident)
        assert run.status=="insufficient_evidence"
        assert as_dict(run)["novelty_verified"] is False


def test_failed_run_can_resume_with_checkpoint(tmp_path,monkeypatch):
    factory=setup(tmp_path,monkeypatch)
    with factory() as db:
        ident=create_run(db,"city","Explore graph generalization hypotheses","member-one").id
    calls=0
    def model(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==1:
            return ({"action":"call_tool","tool_name":"crossref.lookup_doi",
                     "arguments":{"doi":"10.1234/graphtransfer"},
                     "reason":"Retrieve DOI"}, {"input_tokens":10,"output_tokens":10})
        if calls==2:
            return ({"action":"call_tool","tool_name":"dangerous.run",
                     "arguments":{},"reason":"Invalid"}, {"input_tokens":10,"output_tokens":10})
        return ({"action":"finalize","hypothesis":{
            "research_question":"Check spatial external validation",
            "mechanism":"Space changes transferability",
            "falsifiable_prediction":"Generalization is worse cross-city",
            "methods":"Cross-city evaluation",
            "baselines":["City baseline"],
            "minimal_experiment":"Cross-city holdout comparison",
            "supporting_evidence_ids":["E1"],
            "counter_evidence_ids":[],
            "limitations":["Metadata only"],"next_searches":[]
        }},{"input_tokens":10,"output_tokens":10})
    with httpx.Client(transport=httpx.MockTransport(mock_scholarly_api)) as http:
        assert not execute(factory,ident,model_call=model,tool_client=http)
        with factory() as db:
            run=db.get(ScientificExplorationRun,ident)
            assert run.status=="failed"
            assert run.steps==1
            assert run.tool_calls==1
            resume(db,ident,"member-one")
        assert execute(factory,ident,model_call=model,tool_client=http)
    with factory() as db:
        run=db.get(ScientificExplorationRun,ident)
        assert run.status=="completed"
        assert run.tool_calls==1
        assert len(json.loads(run.evidence_json))==1
