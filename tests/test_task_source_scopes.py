"""Task-specific journal sets must remain isolated and enforceable.

No live OpenAlex or LLM requests are made in these tests.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
from backend.agent import ResearchAgent
from backend.task_source_scopes import (
    read_scope, write_scope, snapshot_task, task_source_context, TaskSourceSnapshot,
)
from backend.research_sources import ResearchSource
from research_workbench.core import Paper, session_factory, set_profile, ingest, weekly_report

HEADERS={"Authorization":"Bearer test-source-scope-token"}
PROFILE={
    "research_lines":[{
        "id":"planning","name":"Planning","problem":"Urban systems",
        "keywords":["urban"],"search_queries":["urban governance"],
        "method_queries":["graph transformer"],
    }],
    "excluded_terms":[],"datasets":[],"methods":[],
}


def names(db, *needles):
    entries=db.scalars(select(ResearchSource)).all()
    out={}
    for needle in needles:
        found=next((x for x in entries if x.name==needle or x.abbreviation==needle),None)
        assert found is not None, needle
        out[needle]=found
    return out


def test_independent_defaults_and_task_snapshots(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"source-scopes.db"))
    with factory() as db:
        t=read_scope(db,"team_weekly")
        p=read_scope(db,"personal_weekly","member_001")
        d=read_scope(db,"directed_research")
        assert t["configured"] is False
        assert p["groups"]=={"A":[],"B":[],"C":[]}
        assert t["groups"]["A"] and t["groups"]["B"]
        assert d["groups"]["A"] and d["groups"]["B"]
        rows=names(db,"Cities","SCS","EPB","CEUS")
        custom={"A":[rows["Cities"].id],"B":[rows["EPB"].id],"C":[]}
        saved=write_scope(db,"team_weekly",groups=custom,enforced=True,expected_version=0)
        assert saved["version"]==1 and saved["enforced"]
        assert read_scope(db,"directed_research")["version"]==0
        assert read_scope(db,"personal_weekly","member_001")["version"]==0
        assert read_scope(db,"personal_weekly","member_002")["version"]==0
        snapshot=snapshot_task(db,"new_task",kind="weekly")
        assert snapshot["groups"]==custom and snapshot["enforced"]
        updated={"A":[rows["SCS"].id],"B":[rows["CEUS"].id],"C":[]}
        write_scope(db,"team_weekly",groups=updated,enforced=True,expected_version=1)
        assert json.loads(db.get(TaskSourceSnapshot,"new_task").groups_json)==custom
        with pytest.raises(ValueError,match="refresh"):
            write_scope(db,"team_weekly",groups=updated,enforced=False,expected_version=1)
        with pytest.raises(ValueError,match="only one"):
            write_scope(db,"team_weekly",groups={"A":[rows["Cities"].id],"B":[rows["Cities"].id],"C":[]},
                        enforced=True,expected_version=2)


def test_strict_scope_fails_closed_if_sources_not_resolved(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"unresolved.db"))
    with factory() as db:
        rows=names(db,"Cities")
        custom={"A":[rows["Cities"].id],"B":[],"C":[]}
        snapshot_task(db,"strict_task",kind="explore",override=custom)
        with pytest.raises(ValueError,match="未核验"):
            task_source_context(db,"strict_task")
        rows["Cities"].resolution_status="resolved"
        rows["Cities"].openalex_source_id="S12345"
        db.commit()
        ctx=task_source_context(db,"strict_task")
        assert ctx["direct_ids"]==["S12345"]
        assert ctx["method_ids"]==[]
        assert "cities" in ctx["allowed_venues"]


def test_scoped_direct_and_method_queries_never_expand(tmp_path,monkeypatch):
    import research_workbench.core as core
    factory=session_factory("sqlite:///"+str(tmp_path/"query.db"))
    calls=[]
    def fake(query,since,limit=15,client=None,source_ids=None):
        calls.append((query,source_ids))
        return []
    monkeypatch.setattr(core,"query_openalex",fake)
    with factory() as db:
        set_profile(db,PROFILE)
        ingest(db,PROFILE,source_ids_by_mode={"direct":["S11"],"method":[]})
        assert calls==[("urban governance",["S11"])]
        calls.clear()
        ingest(db,PROFILE,source_ids_by_mode={"direct":[],"method":["S22"]})
        assert calls==[("graph transformer",["S22"])]
        calls.clear()
        ingest(db,PROFILE)
        assert [x[0] for x in calls]==["urban governance","graph transformer"]
        assert all(source_ids is None for _,source_ids in calls)


def test_agent_does_not_read_outside_saved_or_live_scope(tmp_path,monkeypatch):
    import backend.agent as agent_module
    factory=session_factory("sqlite:///"+str(tmp_path/"agent.db"))
    with factory() as db:
        for id,venue in [("A","Cities"),("B","Unknown Journal")]:
            db.add(Paper(id=id,title="urban graph application "+id,
                         abstract="urban graph",doi="",url="https://example.org/"+id,
                         published="2026-11-01",venue=venue,line_ids="[]"))
        db.commit()
        context={"all_ids":["S11"],"allowed_venues":{"cities"}}
        agent=ResearchAgent(db,source_context=context)
        saved=agent.dispatch("search_saved_papers",{"query":"urban graph"})
        assert [item["id"] for item in saved]==["A"]
        calls=[]
        def fake(query,since,limit=15,client=None,source_ids=None):
            calls.append(source_ids)
            return [{
                "id":"https://openalex.org/W111",
                "title":"urban graph contribution",
                "doi":"",
                "publication_date":"2026-11-01",
                "primary_location":{"source":{"id":"https://openalex.org/S99",
                                              "display_name":"Unknown Journal"}},
            }]
        monkeypatch.setattr(agent_module,"query_openalex",fake)
        live=agent.dispatch("search_live_papers",{"query":"urban graph"})
        assert live==[] and calls==[["S11"]]


def test_api_dedicated_scopes_and_single_run_override(tmp_path,monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKEN","test-source-scope-token")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","false")
    monkeypatch.setenv("WORKER_MODE","queue")
    factory=session_factory("sqlite:///"+str(tmp_path/"api.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    client=TestClient(api.app)
    assert client.get("/api/task-source-scopes").status_code==401
    listed=client.get("/api/task-source-scopes",headers=HEADERS)
    assert listed.status_code==200 and len(listed.json()["items"])==3
    assert listed.json()["personal_available"] is False
    with factory() as db:
        rows=names(db,"Cities","EPB")
        custom={"A":[rows["Cities"].id],"B":[rows["EPB"].id],"C":[]}
    saved=client.put("/api/task-source-scopes/team_weekly",headers=HEADERS,
                     json={"groups":custom,"enforced":True,"expected_version":0})
    assert saved.status_code==200,saved.text
    assert saved.json()["scene"]=="team_weekly"
    assert client.put("/api/task-source-scopes/personal_weekly",headers=HEADERS,
                      json={"groups":custom,"expected_version":0}).status_code==409
    assert client.put("/api/task-source-scopes/team_weekly",headers=HEADERS,
                      json={"groups":custom,"enforced":True,"expected_version":0}).status_code==409
    created=client.post("/api/tasks",headers=HEADERS,
                        json={"kind":"explore","query":"Explore interdisciplinary urban graph methods",
                              "source_override":custom})
    assert created.status_code==202,created.text
    ident=created.json()["id"]
    detail=client.get("/api/tasks/"+ident,headers=HEADERS)
    assert detail.status_code==200
    assert detail.json()["source_scope"]["groups"]==custom
    assert detail.json()["source_scope"]["enforced"] is True
    assert client.post("/api/tasks",headers=HEADERS,
                       json={"kind":"explore","query":"urban graph study",
                             "source_override":{"A":[],"B":[],"C":[]}}).status_code==422
