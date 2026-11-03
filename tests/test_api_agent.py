"""End-to-end API + durable worker tests without network, cloud keys, or model credits."""
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import backend.api as server
from backend.agent import ResearchAgent
from backend.skill_loader import load_skills
from backend.tasks import ResearchTask
from backend.worker import run_task, execute_once
from research_workbench.core import get_profile, session_factory

PROFILE = {
    "goals":"Urban research and cross-disciplinary computation",
    "excluded_terms":[],
    "research_lines":[{
        "id":"city","name":"Urban science",
        "problem":"Improve urban classification with limited labels",
        "keywords":["urban","graph"],
        "search_queries":["urban graph"],
        "method_queries":["self-supervised graph"]
    }]
}
def work(paper_id="1"):
    return {"id":"https://openalex.org/W"+paper_id,
        "doi":"https://doi.org/10.9999/urban"+paper_id,
        "title":"Self-supervised graph learning for urban science",
        "abstract_inverted_index":{
            "urban":[0],"graph":[1],"self-supervised":[2],"learning":[3]},
        "publication_date":date.today().isoformat(),
        "primary_location":{"source":{"display_name":"Example Journal"}}
    }

@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKEN","test-api-token")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("WORKER_MODE","queue")
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    Factory=session_factory("sqlite:///"+str(tmp_path/"research.db"))
    monkeypatch.setattr(server,"get_factory",lambda: Factory)
    with TestClient(server.app) as client:
        yield client,Factory

def headers():
    return {"Authorization":"Bearer test-api-token"}

def mocked_openalex(request:httpx.Request):
    assert "/works" in str(request.url)
    return httpx.Response(200,json={"results":[work()]})

def test_api_auth_profile_tasks_and_evidence(setup):
    client,Factory=setup
    assert client.get("/api/health").status_code==200
    assert client.get("/api/overview").status_code==401
    assert client.get("/api/overview",headers=headers()).status_code==200
    assert client.put("/api/profile",headers=headers(),json=PROFILE).status_code==200
    assert client.get("/api/profile",headers=headers()).json()["profile"]["goals"].startswith("Urban")
    assert client.post("/api/tasks",headers=headers(),json={"kind":"explore","query":"no"}).status_code==422
    queued=client.post("/api/tasks",headers=headers(),json={"kind":"sync","query":""})
    assert queued.status_code==202
    task_id=queued.json()["id"]
    assert queued.json()["status"]=="queued"
    with httpx.Client(transport=httpx.MockTransport(mocked_openalex)) as http:
        assert run_task(Factory,task_id,client=http)
        detail=client.get("/api/tasks/"+task_id,headers=headers()).json()
        assert detail["status"]=="completed"
        assert detail["result"]["papers"]["new_papers"]==1
    papers=client.get("/api/papers",headers=headers()).json()["items"]
    assert papers and papers[0]["doi"]=="10.9999/urban1"
    ideas=client.get("/api/ideas",headers=headers()).json()["items"]
    assert ideas and any(item["papers"] for item in ideas)
    first=ideas[0]
    modified=client.post("/api/ideas/"+first["id"]+"/feedback",headers=headers(),
                         json={"status":"watch","note":"Check label availability"})
    assert modified.status_code==200 and modified.json()["version"]==2
    history=client.get("/api/ideas/"+first["id"]+"/history",headers=headers()).json()["items"]
    assert len(history)==2 and history[0]["action"]=="feedback"

def test_agent_preview_is_never_mislabeled_as_llm(setup):
    client,Factory=setup
    client.put("/api/profile",headers=headers(),json=PROFILE)
    task=client.post("/api/tasks",headers=headers(),
                     json={"kind":"explore","query":"Urban graph learning for sparse labels"})
    with httpx.Client(transport=httpx.MockTransport(mocked_openalex)) as http:
        assert run_task(Factory,task.json()["id"],client=http)
    result=client.get("/api/tasks/"+task.json()["id"],headers=headers()).json()
    assert result["status"]=="completed"
    assert result["result"]["mode"]=="bibliographic_preview"
    assert len(result["result"]["sources"])>0
    assert "无模型模式" in result["result"]["answer"]
    assert any(e["step"]=="done" for e in result["events"])

def test_skills_and_claiming(setup):
    client,Factory=setup
    content=load_skills()
    assert "Method Transfer" in content and "Idea Critic" in content
    with pytest.raises(ValueError):load_skills(["../../etc/passwd"])
    pending=client.post("/api/tasks",headers=headers(),
                        json={"kind":"explore","query":"Explore future applications of graph models"})
    with httpx.Client(transport=httpx.MockTransport(mocked_openalex)) as http:
        assert run_task(Factory,pending.json()["id"],client=http)
    assert not run_task(Factory,pending.json()["id"])
    assert client.get("/api/tasks",headers=headers()).json()["items"]

def test_nonexistent_idea_and_invalid_profile(setup):
    client,_=setup
    assert client.get("/api/ideas/not-found/history",headers=headers()).status_code==404
    bad={"research_lines":[{"id":"x","name":"N","problem":"P","keywords":[],
         "search_queries":[],"method_queries":[]}]}
    assert client.put("/api/profile",headers=headers(),json=bad).status_code==422
