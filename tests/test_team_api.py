"""FastAPI tests for shared-team role boundaries and versioned profile changes."""
import pytest
from fastapi.testclient import TestClient
import backend.api as server
from backend.team import create_member
from backend.tasks import ResearchTask
from research_workbench.core import session_factory, Paper

def service(token=None):
    result={"Authorization":"Bearer service-test-key"}
    if token:result["X-Research-Session"]=token
    return result

@pytest.fixture
def team_client(tmp_path,monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("API_BEARER_TOKEN","service-test-key")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("WORKER_MODE","queue")
    factory=session_factory("sqlite:///"+str(tmp_path/"team.db"))
    monkeypatch.setattr(server,"get_factory",lambda:factory)
    with factory() as db:
        create_member(db,"admin@example.org","Research Admin",
                      "integration-test-password-2026",role="admin",initial=True)
    with TestClient(server.app) as client:yield client

def sign_in(client,email,password):
    r=client.post("/api/auth/login",headers=service(),json={
        "email":email,"password":password})
    assert r.status_code==200,r.text
    return r.json()["token"]

def test_shared_profile_roles_and_history(team_client):
    client=team_client
    admin=sign_in(client,"admin@example.org","integration-test-password-2026")
    assert client.get("/api/profile",headers=service()).status_code==401
    member=client.post("/api/team/members",headers=service(admin),json={
        "email":"editor@example.org","name":"Team Researcher",
        "temporary_password":"integration-test-editor-2026","role":"researcher"})
    assert member.status_code==201,member.text
    researcher=sign_in(client,"editor@example.org","integration-test-editor-2026")
    profile={"goals":"Shared lab strategy","research_lines":[{
        "id":"urban","name":"Urban Research","problem":"Sparse labels",
        "keywords":["urban"],"search_queries":["urban learning"],
        "method_queries":["contrastive graph learning"]}],
        "team":{"name":"Urban Research Lab","mission":"Cross-disciplinary work"},
        "datasets":[{"name":"Building dataset"}],"methods":["graph learning"]}
    saved=client.put("/api/profile",headers=service(admin),
                     json={**profile,"expected_version":0})
    assert saved.status_code==200,saved.text
    assert saved.json()["version"]==1
    assert client.get("/api/profile",headers=service(researcher)).json()["profile"]==saved.json()["profile"]
    assert client.put("/api/profile",headers=service(researcher),json=profile).status_code==403
    assert client.put("/api/profile",headers=service(admin),
                      json={**profile,"expected_version":0}).status_code==409
    history=client.get("/api/team/profile-history",headers=service(researcher))
    assert history.status_code==200 and history.json()["items"][0]["version"]==1
    task=client.post("/api/tasks",headers=service(researcher),json={
        "kind":"explore","query":"Find graph methods for urban data"})
    assert task.status_code==202
    audit=client.get("/api/team/audit",headers=service(admin)).json()["items"]
    assert any(item["action"]=="task.created" for item in audit)
    assert client.get("/api/team/audit",headers=service(researcher)).status_code==403

def test_member_revocation_blocks_session(team_client):
    client=team_client
    admin=sign_in(client,"admin@example.org","integration-test-password-2026")
    created=client.post("/api/team/members",headers=service(admin),json={
        "email":"viewer@example.org","name":"Team Viewer",
        "temporary_password":"integration-test-viewer-2026","role":"viewer"}).json()
    viewer=sign_in(client,"viewer@example.org","integration-test-viewer-2026")
    assert client.get("/api/overview",headers=service(viewer)).status_code==200
    assert client.post("/api/tasks",headers=service(viewer),json={
        "kind":"explore","query":"Explore urban research methods"}).status_code==403
    disabled=client.patch("/api/team/members/"+created["id"],
        headers=service(admin),json={"active":False})
    assert disabled.status_code==200
    assert client.get("/api/overview",headers=service(viewer)).status_code==401
    current=client.get("/api/auth/me",headers=service(admin)).json()["member"]
    assert client.patch("/api/team/members/"+current["id"],
        headers=service(admin),json={"active":False}).status_code==422


def test_personal_profile_is_private_to_each_member_and_versioned(team_client):
    client=team_client
    admin=sign_in(client,"admin@example.org","integration-test-password-2026")
    assert client.get("/api/personal-profile",headers=service()).status_code==401

    created=client.post("/api/team/members",headers=service(admin),json={
        "email":"personal@example.org","name":"Personal Researcher",
        "temporary_password":"integration-test-personal-2026","role":"researcher"})
    assert created.status_code==201,created.text
    researcher=sign_in(client,"personal@example.org","integration-test-personal-2026")

    assert client.get("/api/personal-profile",headers=service(admin)).json()=={
        "profile":None,"version":0,"updated_at":None
    }
    admin_profile={
        "goals":"Three personal research lines",
        "methods":["network science","spatial transfer"],
        "excluded_terms":[],
        "research_lines":[{
            "id":"metro_resilience","name":"Metro resilience",
            "problem":"Understand coupled station and segment resilience",
            "keywords":["metro","extreme rainfall"],
            "search_queries":["metro resilience extreme rainfall"],
            "method_queries":["capacity-constrained flow simulation"],
        }],
        "evidence":[{
            "id":"shen_trd_2026","line_id":"metro_resilience",
            "kind":"publication","title":"How metro networks respond to extreme rainfall",
            "url":"https://doi.org/10.1016/j.trd.2026.105654",
            "note":"Representative published work",
        }],
    }
    saved=client.put("/api/personal-profile",headers=service(admin),json={
        "profile":admin_profile,"expected_version":0})
    assert saved.status_code==200,saved.text
    assert saved.json()["version"]==1
    expected_profile={key:value for key,value in admin_profile.items() if key!="evidence"}
    assert saved.json()["profile"]==expected_profile
    seeded=client.get("/api/personal-assets",headers=service(admin))
    assert seeded.status_code==200
    assert len(seeded.json()["items"])==1
    assert seeded.json()["items"][0]["kind"]=="publication"
    assert seeded.json()["items"][0]["line_ids"]==["metro_resilience"]
    assert seeded.json()["items"][0]["source_type"]=="doi"

    # A different authenticated member has a separate empty profile.
    assert client.get("/api/personal-profile",headers=service(researcher)).json()=={
        "profile":None,"version":0,"updated_at":None
    }
    researcher_profile={
        "goals":"My own line",
        "research_lines":[{
            "id":"health_transfer","name":"Health transfer",
            "problem":"Study transferability across cities",
            "keywords":["child health"],"search_queries":["child health transfer"],
            "method_queries":["domain adaptation"],
        }],
        "methods":[],"excluded_terms":[],"evidence":[],
    }
    own=client.put("/api/personal-profile",headers=service(researcher),json={
        "profile":researcher_profile,"expected_version":0})
    assert own.status_code==200,own.text
    assert own.json()["profile"]["research_lines"][0]["id"]=="health_transfer"

    # Member A cannot read or overwrite member B's private profile by guessing IDs.
    assert client.get("/api/personal-profile",headers=service(admin)).json()["profile"]==expected_profile
    stale=client.put("/api/personal-profile",headers=service(admin),json={
        "profile":admin_profile,"expected_version":0})
    assert stale.status_code==409,stale.text

    invalid={**admin_profile,"evidence":[{
        "id":"orphan_report","line_id":"not_a_line","kind":"agent_report",
        "title":"Orphan","url":"https://example.org/report","note":"",
    }]}
    rejected=client.put("/api/personal-profile",headers=service(admin),json={
        "profile":invalid,"expected_version":1})
    assert rejected.status_code==422,rejected.text
