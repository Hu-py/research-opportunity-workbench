"""Tests for member-private publications, reports and experiment records."""
import pytest
from fastapi.testclient import TestClient

import backend.api as server
from backend.team import create_member
from backend.tasks import ResearchTask
from research_workbench.core import session_factory, Paper


def headers(token=None):
    result={"Authorization":"Bearer personal-library-test-key"}
    if token:
        result["X-Research-Session"]=token
    return result


def sign_in(client,email,password):
    response=client.post("/api/auth/login",headers=headers(),json={
        "email":email,"password":password
    })
    assert response.status_code==200,response.text
    return response.json()["token"]


@pytest.fixture
def client_with_members(tmp_path,monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("API_BEARER_TOKEN","personal-library-test-key")
    monkeypatch.setenv("APP_ENV","development")
    factory=session_factory("sqlite:///"+str(tmp_path/"personal-library.db"))
    monkeypatch.setattr(server,"get_factory",lambda:factory)
    with factory() as db:
        create_member(db,"owner@example.org","Profile Owner",
                      "integration-test-owner-2026",role="admin",initial=True)
        create_member(db,"member@example.org","Second Member",
                      "integration-test-member-2026",role="researcher")
        db.add(Paper(
            id="https://openalex.org/W12345",
            title="Metro network resilience under extreme rainfall",
            abstract="A paper abstract for import testing.",
            doi="10.1234/metro.test",
            url="https://doi.org/10.1234/metro.test",
            published="2026-01-01",
            venue="Transportation Research Part D",
            line_ids="[]",
        ))
        db.add(ResearchTask(
            id="task_personal_import_01",
            kind="explore",
            query="Metro network resilience mechanisms",
            status="done",
            events_json="[]",
            result_json='{"answer":"A complete research report snapshot."}',
        ))
        db.commit()
    with TestClient(server.app) as client:
        yield client


def save_profile(client, token):
    payload={
        "goals":"Personal urban systems research",
        "methods":["network science","spatial analysis"],
        "excluded_terms":[],
        "research_lines":[{
            "id":"metro_resilience",
            "name":"Metro network resilience",
            "problem":"Understand extreme-weather disruption propagation",
            "keywords":["metro","resilience"],
            "search_queries":["metro network resilience"],
            "method_queries":["capacity constrained network flow"],
        }],
        "evidence":[],
    }
    response=client.put("/api/personal-profile",headers=headers(token),json={
        "profile":payload,"expected_version":0
    })
    assert response.status_code==200,response.text


def test_member_private_asset_crud_and_line_validation(client_with_members):
    client=client_with_members
    owner=sign_in(client,"owner@example.org","integration-test-owner-2026")
    member=sign_in(client,"member@example.org","integration-test-member-2026")
    save_profile(client,owner)

    created=client.post("/api/personal-assets",headers=headers(owner),json={
        "kind":"experiment_result",
        "title":"R6.4.5 Gate-On",
        "summary":"Blind review score 70/100; three candidate routes remain on hold.",
        "source_type":"sc05_run",
        "source_id":"sc05run_example_01",
        "metadata":{"gate":"on","blind_score":70,"status":"hold"},
        "line_ids":["metro_resilience"],
    })
    assert created.status_code==201,created.text
    asset_id=created.json()["id"]
    assert created.json()["line_ids"]==["metro_resilience"]

    assert len(client.get("/api/personal-assets",headers=headers(owner)).json()["items"])==1
    assert client.get("/api/personal-assets",headers=headers(member)).json()["items"]==[]
    assert client.delete("/api/personal-assets/"+asset_id,headers=headers(member)).status_code==404

    invalid=client.post("/api/personal-assets",headers=headers(owner),json={
        "kind":"agent_report","title":"Invalid association",
        "source_type":"manual","line_ids":["not_my_line"],
    })
    assert invalid.status_code==422,invalid.text

    updated=client.put("/api/personal-assets/"+asset_id,headers=headers(owner),json={
        "kind":"experiment_result",
        "title":"R6.4.5 Gate-On revised",
        "summary":"Updated note",
        "source_type":"sc05_run",
        "source_id":"sc05run_example_01",
        "metadata":{"gate":"on","blind_score":70,"status":"hold"},
        "line_ids":["metro_resilience"],
    })
    assert updated.status_code==200,updated.text
    assert updated.json()["title"]=="R6.4.5 Gate-On revised"

    archived=client.delete("/api/personal-assets/"+asset_id,headers=headers(owner))
    assert archived.status_code==200
    assert client.get("/api/personal-assets",headers=headers(owner)).json()["items"]==[]
    all_rows=client.get("/api/personal-assets?include_archived=true",headers=headers(owner)).json()["items"]
    assert len(all_rows)==1 and all_rows[0]["status"]=="archived"


def test_import_shared_paper_and_completed_research_task_as_private_snapshots(client_with_members):
    client=client_with_members
    owner=sign_in(client,"owner@example.org","integration-test-owner-2026")
    save_profile(client,owner)

    paper=client.post("/api/personal-assets/import-paper",headers=headers(owner),json={
        "doi":"10.1234/metro.test","line_ids":["metro_resilience"]
    })
    assert paper.status_code==201,paper.text
    assert paper.json()["kind"]=="publication"
    assert paper.json()["source_type"]=="openalex_work"
    assert paper.json()["metadata"]["venue"]=="Transportation Research Part D"

    report=client.post("/api/personal-assets/import-task",headers=headers(owner),json={
        "task_id":"task_personal_import_01","line_ids":["metro_resilience"]
    })
    assert report.status_code==201,report.text
    assert report.json()["kind"]=="agent_report"
    assert report.json()["source_type"]=="research_task"
    assert report.json()["summary"]=="A complete research report snapshot."

    items=client.get("/api/personal-assets?line_id=metro_resilience",headers=headers(owner)).json()["items"]
    assert {item["kind"] for item in items}=={"publication","agent_report"}
