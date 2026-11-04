"""Offline watchlist regression checks; never call live scholarly APIs."""
from datetime import date
import json
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
import backend.interests as interests
from research_workbench.core import Paper, get_profile, set_profile, session_factory, weekly_report

PROFILE = {
    "research_lines":[{
        "id":"trusted","name":"Verified research line","problem":"Grounded research question",
        "keywords":["urban","graph"],"search_queries":["urban graph"],
        "method_queries":["graph learning"],
    }],"excluded_terms":[],"datasets":[],"methods":[],
}
HEADERS={"Authorization":"Bearer dev-test-api-token"}

def payload():
    return {"title":"Graph foundation models","focus":"cs_frontier",
            "problem":"Learn new computer science methods",
            "keywords":["graph","representation"],"queries":["graph foundation model","graph foundation model"],
            "venues":["NeurIPS","ICLR"],"enabled":True}

def sample():
    return {
      "id":"https://openalex.org/W56789999",
      "title":"Graph models for cross-domain urban learning",
      "doi":"https://doi.org/10.1234/example-watchlist",
      "publication_date":date.today().isoformat(),
      "abstract_inverted_index":{"graph":[0],"urban":[1],"learning":[2]},
      "primary_location":{"source":{"display_name":"Unverified example venue"}},
    }

def test_interest_is_separate_from_team_profile_and_weekly_report(tmp_path, monkeypatch):
    factory=session_factory("sqlite:///"+str(tmp_path/"watchlist.db"))
    with factory() as db:
        set_profile(db,PROFILE)
        row=interests.create_interest(db,payload(),actor="test")
        interest_id=row["id"]
        assert row["queries"]==["graph foundation model"]
        assert all(line["id"]!="interest:"+interest_id for line in get_profile(db)["research_lines"])
        monkeypatch.setattr(interests,"query_openalex",lambda *args,**kwargs:[sample()])
        stats=interests.ingest_interests(db,days=14)
        assert stats["interests"]==1 and stats["requests"]==1
        assert stats["new_papers"]==1
        again=interests.ingest_interests(db,days=14)
        assert again["new_papers"]==0
        stored=db.scalars(select(Paper)).all()
        assert len(stored)==1
        assert json.loads(stored[0].line_ids)==["interest:"+interest_id]
        assert interests.recent_papers(db,interest_id)[0]["title"]==sample()["title"]
        brief=weekly_report(db,get_profile(db))
        assert "手动关注的研究兴趣" in brief
        assert sample()["title"] in brief
        assert "Verified research line" not in row["title"]

def test_interest_api_create_list_toggle_and_scan_auth(tmp_path,monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKEN","dev-test-api-token")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","false")
    factory=session_factory("sqlite:///"+str(tmp_path/"api.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    client=TestClient(api.app)
    assert client.get("/api/research-interests").status_code==401
    invalid=client.post("/api/research-interests",headers=HEADERS,json={**payload(),"queries":[]})
    assert invalid.status_code==422
    created=client.post("/api/research-interests",headers=HEADERS,json=payload())
    assert created.status_code==201,created.text
    item=created.json()
    assert item["focus"]=="cs_frontier"
    out=client.get("/api/research-interests",headers=HEADERS)
    assert out.status_code==200 and out.json()["items"][0]["title"]==item["title"]
    paused=client.patch("/api/research-interests/"+item["id"],headers=HEADERS,json={"enabled":False})
    assert paused.status_code==200 and paused.json()["enabled"] is False
    no_scan=client.post("/api/research-interests/"+item["id"]+"/scan",headers=HEADERS,json={})
    assert no_scan.status_code==409

def test_failed_scan_never_persists_external_request_or_key(tmp_path,monkeypatch):
    import httpx
    factory=session_factory("sqlite:///"+str(tmp_path/"private-error.db"))
    with factory() as db:
        row=interests.create_interest(db,payload())
        def fail(*args,**kwargs):
            raise httpx.HTTPStatusError("https://api.openalex.org/works?api_key=SECRET",
                   request=httpx.Request("GET","https://api.openalex.org/works"),
                   response=httpx.Response(409,request=httpx.Request("GET","https://api.openalex.org/works")))
        monkeypatch.setattr(interests,"query_openalex",fail)
        result=interests.ingest_interests(db,days=7)
        assert result["errors"]==1
        assert db.get(interests.ResearchInterest,row["id"]).last_status=="failed"
        assert "SECRET" not in json.dumps(interests.as_dict(db.get(interests.ResearchInterest,row["id"])))
