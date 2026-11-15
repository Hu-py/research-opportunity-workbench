"""Offline SC05 MCP + OAuth PKCE security and queue integration tests.

No real provider requests, external logins, browser automation or billable calls.
"""
import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import backend.api as api
from backend.sc05_agent_bridge import CLIENT, REDIRECT
from backend.team import create_member
from backend.sc05_eval_api import SC05Run
from research_workbench.core import session_factory

ORIGIN="https://research-atlas-devstudio-e2e-ejmh.onrender.com"
MCP=ORIGIN+"/mcp"
VERIFIER="v"*64
CHALLENGE=base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
SERVICE="testing-sc05-service-token"


@pytest.fixture
def workspace(tmp_path,monkeypatch):
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("API_BEARER_TOKEN",SERVICE)
    monkeypatch.setenv("SC05_MCP_ENABLED","true")
    monkeypatch.setenv("SC05_MCP_PUBLIC_URL",ORIGIN)
    monkeypatch.setenv("SC05_EXECUTION_MODE","worker")
    monkeypatch.setenv("SC04_DEEPSEEK_API_KEY","fake-provider-key-never-paid")
    factory=session_factory("sqlite:///"+str(tmp_path/"mcp.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    with factory() as db:
        owner=create_member(db,"owner@example.invalid","Owner",
                            "test-verified-owner-222222",role="admin",initial=True)
        create_member(db,"viewer@example.invalid","Viewer",
                      "test-verified-viewer-333333",role="viewer")
        owner.role="owner"
        db.commit()
    with TestClient(api.app) as client:
        yield client,factory


def oauth_form(scope="experiments:read experiments:run"):
    return {"response_type":"code","client_id":CLIENT,"redirect_uri":REDIRECT,
            "resource":MCP,"code_challenge":CHALLENGE,
            "code_challenge_method":"S256","scope":scope,"state":"mcp-state-1234"}


def connect(client,scope="experiments:read experiments:run",email="owner@example.invalid",
            password="test-verified-owner-222222"):
    data={**oauth_form(scope),"email":email,"password":password}
    response=client.post("/oauth/authorize",data=data,follow_redirects=False)
    assert response.status_code==303,response.text
    url=urlparse(response.headers["location"])
    assert url.scheme=="https" and url.netloc=="chatgpt.com"
    assert url.path=="/connector_platform_oauth_redirect"
    parsed=parse_qs(url.query)
    assert parsed["state"]==["mcp-state-1234"]
    assert parsed["iss"]==[ORIGIN]
    code=parsed["code"][0]
    token_data={"grant_type":"authorization_code","client_id":CLIENT,
                "redirect_uri":REDIRECT,"resource":MCP,
                "code_verifier":VERIFIER,"code":code}
    result=client.post("/oauth/token",data=token_data)
    assert result.status_code==200,result.text
    return result.json(),token_data


def call(client,token,method,params=None,identifier=1):
    return client.post("/mcp",headers={"Authorization":"Bearer "+token},
       json={"jsonrpc":"2.0","id":identifier,"method":method,
             "params":params or {}})


def api_session(client):
    response=client.post("/api/auth/login",headers={"Authorization":"Bearer "+SERVICE},
       json={"email":"owner@example.invalid","password":"test-verified-owner-222222"})
    assert response.status_code==200
    return {"Authorization":"Bearer "+SERVICE,
            "X-Research-Session":response.json()["token"]}


def test_discovery_pkce_and_replay_protection(workspace):
    client,_=workspace
    resource=client.get("/.well-known/oauth-protected-resource")
    assert resource.status_code==200
    assert resource.json()["resource"]==MCP
    assert client.get("/.well-known/oauth-authorization-server").json()[
        "code_challenge_methods_supported"]==["S256"]
    assert client.get("/mcp").status_code==401
    assert "resource_metadata" in client.get("/mcp").headers["www-authenticate"]
    assert client.get("/oauth/authorize",params={**oauth_form(),"redirect_uri":"https://evil.invalid"}).status_code==400
    assert client.get("/oauth/authorize",params={**oauth_form(),"code_challenge_method":"plain"}).status_code==400
    page=client.get("/oauth/authorize",params=oauth_form())
    assert page.status_code==200
    assert "Authorize ChatGPT" in page.text
    tokens,data=connect(client)
    assert client.post("/oauth/token",data=data).status_code==400
    init=call(client,tokens["access_token"],"initialize")
    assert init.status_code==200
    assert init.json()["result"]["serverInfo"]["name"]=="research-atlas-sc05"
    names=call(client,tokens["access_token"],"tools/list").json()["result"]["tools"]
    assert {"list_experiments","prepare_experiment","start_experiment",
            "get_experiment_status","get_experiment_result"}=={x["name"] for x in names}
    assert call(client,tokens["access_token"],"tools/call",{
        "name":"list_experiments","arguments":{}}).json()["result"]["isError"] is False
    assert call(client,tokens["access_token"],"tools/list").status_code==200
    assert client.post("/mcp",headers={"Authorization":"Bearer "+tokens["access_token"],
                       "Origin":"https://evil.invalid"},json={"jsonrpc":"2.0","id":5,
                        "method":"tools/list"}).status_code==403
    new=client.post("/oauth/token",data={"grant_type":"refresh_token",
        "refresh_token":tokens["refresh_token"],"resource":MCP,"client_id":CLIENT})
    assert new.status_code==200
    assert call(client,tokens["access_token"],"tools/list").status_code==401
    assert call(client,new.json()["access_token"],"tools/list").status_code==200


def test_read_only_token_cannot_run_paid_and_disabled_switch(workspace):
    client,_=workspace
    tokens,_=connect(client,scope="experiments:read")
    reply=call(client,tokens["access_token"],"tools/call",{
        "name":"start_experiment","arguments":{"run_id":"sc05run_"+"a"*28,"confirm_paid":True}})
    assert reply.status_code==200
    assert reply.json()["result"]["isError"] is True
    assert "disabled" in str(reply.json()["result"])


def test_owner_auth_required_and_activation_flag(workspace,monkeypatch):
    client,_=workspace
    unauth=client.post("/oauth/authorize",data={**oauth_form(),
        "email":"viewer@example.invalid","password":"test-verified-viewer-333333"})
    assert unauth.status_code==403
    monkeypatch.setenv("SC05_MCP_ENABLED","false")
    assert client.get("/.well-known/oauth-protected-resource").status_code==404
    assert client.get("/mcp").status_code==404


def test_owner_mcp_start_enqueues_once_and_registers_in_devstudio(workspace,monkeypatch):
    client,factory=workspace
    session=api_session(client)
    pages={"page_01":"This paper provides a long reproducible transportation network study. "*4}
    case=client.post("/api/personal-research/me/sc05/cases",headers=session,
        json={"title":"Published urban transport study","pages":pages})
    assert case.status_code==201,case.text
    pair=client.post("/api/personal-research/me/sc05/cases/"+case.json()["id"]+"/ab",
                     headers=session)
    assert pair.status_code==201,pair.text
    run=next(x for x in pair.json()["runs"] if x["variant"]=="science_gate_off")
    tokens,_=connect(client)
    access=tokens["access_token"]
    ready=call(client,access,"tools/call",{"name":"prepare_experiment",
        "arguments":{"run_id":run["id"]}})
    assert ready.json()["result"]["isError"] is False
    denied=call(client,access,"tools/call",{"name":"start_experiment",
        "arguments":{"run_id":run["id"],"confirm_paid":False}})
    assert denied.json()["result"]["isError"] is True
    monkeypatch.setenv("SC05_MCP_PAID_ENABLED","true")
    routes=[(getattr(r,"path",""),sorted(getattr(r,"methods",[]) or []))
            for r in api.app.routes if "sc05" in getattr(r,"path","")]
    assert any("/runs/{run_id}/start" in route for route,_ in routes),[
        (getattr(r,"path",None),getattr(r,"name",None)) for r in api.app.routes]
    paid=call(client,access,"tools/call",{"name":"start_experiment",
        "arguments":{"run_id":run["id"],"confirm_paid":True}})
    assert paid.json()["result"]["isError"] is False,paid.text
    with factory() as db:
        assert db.get(SC05Run,run["id"]).status=="queued"
        assert db.get(SC05Run,run["id"]).calls==0
    again=call(client,access,"tools/call",{"name":"start_experiment",
        "arguments":{"run_id":run["id"],"confirm_paid":True}})
    assert again.json()["result"]["isError"] is True
    status=call(client,access,"tools/call",{"name":"get_experiment_status",
        "arguments":{"run_id":run["id"]}})
    assert status.json()["result"]["isError"] is False
    devstudio=client.get("/api/devstudio/experiments",headers=session)
    assert devstudio.status_code==200
    assert any("SC05" in x["title"] for x in devstudio.json()["items"])
