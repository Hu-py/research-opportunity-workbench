"""FastAPI tests for shared-team role boundaries and versioned profile changes."""
import pytest
from fastapi.testclient import TestClient
import backend.api as server
from backend.team import create_member
from research_workbench.core import session_factory

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
