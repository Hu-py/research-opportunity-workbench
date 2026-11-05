"""Offline P0/P1 integration tests: no paid services or live OpenAlex calls."""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
from backend.cusp import import_records
from backend.discovery import (
    PaperCandidate,DiscoveryRun,SearchStrategy,
    create_run,save_strategy,review_candidate,candidates,strategies,
)
from backend.discovery_links import list_links,review_link
from backend.discovery_runner import execute_discovery
from backend.team import create_member
from research_workbench.core import Paper,get_profile,set_profile,session_factory
from backend.model_vault import ModelCredential
from backend.research_sources import ResearchSource

PROFILE={"research_lines":[
    {"id":"vertical","name":"建筑垂直功能与城市形态",
     "problem":"识别建筑楼层功能",
     "keywords":["building","vertical","function"],
     "search_queries":["urban building functional mapping","vertical land use mapping"],
     "method_queries":["self supervised graph learning","temporal graph classification"]},
    {"id":"resilience","name":"城市网络韧性","problem":"路网洪涝风险",
     "keywords":["network","resilience"],
     "search_queries":["urban flood network resilience"],
     "method_queries":["percolation road network"]},
 ],"excluded_terms":["forbidden paper"],"datasets":[],"methods":[]}
ROWS=[{
    "数据类型":"城市功能与设施","名称":"上海_建筑与POI楼层数据",
    "格式":"csv","范围":"上海","时间":"2022",
    "数据来源":"公开示例","基本信息":"建筑和楼层功能信息",
    "用于的研究（关键结果）":"楼层功能识别","数据持有人":"团队",
    "F盘":"✅","是否备份":"",
 }]
HEADERS={"Authorization":"Bearer dev-test-api-token"}

@pytest.fixture
def setup_db(tmp_path,monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKEN","dev-test-api-token")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("TEAM_BOOTSTRAP_ENABLED","false")
    monkeypatch.delenv("CUSP_DATA_BOOTSTRAP_ZB64",raising=False)
    factory=session_factory("sqlite:///"+str(tmp_path/"research-discovery.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    with factory() as db:
        create_member(db,"admin@example.net","Test Admin",
                      "local-testing-password-2026",role="admin",initial=True)
        set_profile(db,PROFILE)
        import_records(db,ROWS)
        db.add(ModelCredential(provider='deepseek',encrypted_key='test-encrypted',daily_enabled=True))
        db.add(ResearchSource(id='src-urban',name='Urban Planning Journal',domain='urban_planning',enabled=True,openalex_source_id='S123',resolution_status='resolved'))
        db.add(ResearchSource(id='src-ai',name='AI Methods Conference',domain='ai_ml',enabled=True,openalex_source_id='S456',resolution_status='resolved'))
        db.commit()
    with TestClient(api.app) as client:
        login=client.post("/api/auth/login",headers=HEADERS,json={
            "email":"admin@example.net","password":"local-testing-password-2026"})
        assert login.status_code==200,login.text
        yield factory,client,{**HEADERS,"X-Research-Session":login.json()["token"]}

def work(ident="W551"):
    return {"id":"https://openalex.org/"+ident,
            "title":"Building vertical function graph learning",
            "doi":"https://doi.org/10.7777/graph."+ident.lower(),
            "publication_date":"2026-09-30",
            "abstract_inverted_index":{"urban":[0],"building":[1],"vertical":[2],"function":[3],"graph":[4]},
            "primary_location":{"source":{"display_name":"Verified example venue"}}}

def test_links_are_suggested_but_never_confirmed_automatically(setup_db):
    factory,client,headers=setup_db
    dashboard=client.get("/api/opportunity-engine",headers=headers)
    assert dashboard.status_code==200,dashboard.text
    data=dashboard.json()
    assert data["profile_ready"]
    matches=[x for x in data["relations"] if x["kind"]=="dataset" and x["line_id"]=="vertical"]
    assert matches
    assert all(x["status"]=="suggested" for x in matches)
    rid=matches[0]["id"]
    result=client.patch("/api/opportunity-engine/relations/"+rid,headers=headers,
                        json={"status":"confirmed"})
    assert result.status_code==200,result.text
    assert result.json()["status"]=="confirmed"
    confirmed=client.get("/api/opportunity-engine",headers=headers).json()
    assert any(x["id"]==rid and x["status"]=="confirmed" for x in confirmed["relations"])
    assert client.patch("/api/opportunity-engine/relations/missing",headers=headers,
                        json={"status":"confirmed"}).status_code==404

def test_discovery_only_schedules_enabled_lines_and_preserves_reviews(setup_db):
    factory,client,headers=setup_db
    page=client.get("/api/opportunity-engine",headers=headers).json()
    assert all(not item["enabled"] for item in page["strategies"] if not item["line_id"].startswith(("db_theme_","db_data_topic_")))
    assert all(item["enabled"] for item in page["strategies"] if item["line_id"].startswith(("db_theme_","db_data_topic_")))
    s=page["strategies"][0]
    s.update({"enabled":True,"per_query":3,"min_score":70})
    response=client.put("/api/opportunity-engine/strategies/vertical",
                        headers=headers,json=s)
    assert response.status_code==200,response.text
    with factory() as db:
        run=create_run(db,get_profile(db),source="scheduled")
        assert run
        assert run.line_ids_json=='["vertical"]'
    request_params=[]
    def response(request):
        request_params.append(dict(request.url.params))
        return httpx.Response(200,json={"results":[work()]})
    with httpx.Client(transport=httpx.MockTransport(response)) as http:
        execute_discovery(factory,run.id,client=http)
    with factory() as db:
        done=db.get(DiscoveryRun,run.id)
        assert done.status=="completed",done.errors_json
        assert done.new_candidates==1
        assert done.queries==4
        assert all(p["per-page"]=="3" for p in request_params)
        assert "primary_location.source.id:S123" in request_params[0]["filter"]
        assert "primary_location.source.id:S456" in request_params[1]["filter"]
        found=candidates(db,line_id="vertical")
        assert len(found)==1
        assert found[0]["status"]=="pending"
        assert found[0]["matched_queries"]
        assert db.scalar(select(Paper).where(Paper.title==work()["title"])) is None
        target=found[0]["id"]
        reviewed=review_candidate(db,target,"method","method-transfer candidate","admin")
        assert reviewed["status"]=="method"
        assert db.get(Paper,"doi:10.7777/graph.w551")
        assert len(candidates(db,line_id="vertical"))==1
        next_run=create_run(db,get_profile(db),source="manual",line_id="vertical")
    with httpx.Client(transport=httpx.MockTransport(response)) as http:
        execute_discovery(factory,next_run.id,client=http)
    with factory() as db:
        assert len(candidates(db,line_id="vertical"))==1
        assert candidates(db,line_id="vertical")[0]["status"]=="method"
        assert db.get(DiscoveryRun,next_run.id).new_candidates==0
        with pytest.raises(ValueError):save_strategy(db,get_profile(db),"vertical",{
            "direct_queries":["one","two","three","four"],"method_queries":[],
            "enabled":False,"lookback_days":30,"per_query":5,"min_score":60
        },"admin")

def test_run_fails_visibly_on_external_api_error(setup_db):
    factory,_,_=setup_db
    with factory() as db:
        assert create_run(db,get_profile(db),source="scheduled") is None
        task=create_run(db,get_profile(db),source="manual",line_id="vertical")
    def failure(_):return httpx.Response(429,json={"error":"rate limit"})
    with httpx.Client(transport=httpx.MockTransport(failure)) as http:
        execute_discovery(factory,task.id,client=http)
    with factory() as db:
        run=db.get(DiscoveryRun,task.id)
        assert run.status=="failed"
        # Stop after the first provider failure instead of spending remaining queries.
        assert run.queries==1
        assert "429" in run.errors_json

def test_no_approval_from_read_only_requests(setup_db):
    factory,client,headers=setup_db
    with factory() as db:
        assert not db.scalars(select(PaperCandidate)).all()
        assert not db.scalars(select(SearchStrategy)).all()
    assert client.get("/api/opportunity-engine",headers=headers).status_code==200
    with factory() as db:
        assert not db.scalars(select(SearchStrategy)).all()


def test_openalex_errors_redact_credentials_in_new_and_legacy_runs():
    from backend.openalex_errors import safe_openalex_error
    from backend.discovery import safe_stored_error
    import httpx
    url="https://api.openalex.org/works?search=private-topic&api_key=SUPER_SECRET_TEST"
    request=httpx.Request("GET",url)
    response=httpx.Response(409,request=request)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        message=safe_openalex_error(exc)
        assert "HTTP 409" in message
        assert "SUPER_SECRET_TEST" not in message
        assert "private-topic" not in message
        old=safe_stored_error("line1 | query | "+str(exc))
        assert "HTTP 409" in old
        assert "SUPER_SECRET_TEST" not in old
        assert "private-topic" not in old
    assert "HTTP 429" in safe_openalex_error(httpx.HTTPStatusError(
        "failed",request=request,response=httpx.Response(429,request=request)))
    assert "HTTP 403" in safe_openalex_error(httpx.HTTPStatusError(
        "failed",request=request,response=httpx.Response(403,request=request)))
    assert "历史" in safe_stored_error("unexpected plugin failure?api_key=SUPER_SECRET_TEST")
    assert "SUPER_SECRET_TEST" not in safe_stored_error("unexpected plugin failure?api_key=SUPER_SECRET_TEST")


def test_discovery_logs_safe_message_for_http_409(setup_db):
    from backend.discovery import runs
    factory,_,_=setup_db
    with factory() as db:
        task=create_run(db,get_profile(db),source="manual",line_id="vertical")
    def reject(request):
        return httpx.Response(409,request=request,json={"error":"keyless budget reached"})
    with httpx.Client(transport=httpx.MockTransport(reject)) as http:
        execute_discovery(factory,task.id,client=http)
    with factory() as db:
        report=runs(db)[0]
        assert report["status"]=="failed"
        assert "HTTP 409" in report["errors"][0]
        assert "api.openalex.org" not in report["errors"][0]
        assert "keyless budget" not in report["errors"][0]

@pytest.fixture(autouse=True)
def mock_discovery_llm(monkeypatch):
    import backend.discovery_runner as runner
    monkeypatch.setattr(runner, "load_key", lambda db: "test-key")
    def plan(key, model, line, assets, prior_queries=None, search_preferences=None, client=None):
        return ({"concept_map":["building functions","graph learning"],
          "queries":[{"query":"LLM planned query "+str(i),"mode":m,"intent":"test"}
            for i,m in enumerate(["direct","method","adjacent","frontier"])],
          "blind_spots":[]},{"input_tokens":10,"output_tokens":10})
    def assess(key, model, line, assets, papers, skill_text=None, client=None):
        rows=[]
        for p in papers:
            rows.append({"paper_id":p["paper_id"],"relevance_type":"method_transfer",
              "relevance_score":88,"method_transfer_score":91,"evidence_confidence":"medium",
              "priority":"high_priority","research_problem":"building floor functions",
              "method":"graph learning","contribution_claim":"method contribution",
              "limitation_or_unknown":"transfer validation unknown","why_relevant":"semantic match",
              "data_fit":"registered building data may support validation","follow_up_query":"",
              "claimed_contribution":"method contribution","limitations_or_unknowns":"transfer validation unknown",
              "reason":"semantic match","evidence_quality":"abstract evidence","evidence_level":"abstract",
              "human_review_required":True,"novelty_verified":False})
        return rows,{"input_tokens":20,"output_tokens":20}
    monkeypatch.setattr(runner,"plan_queries",plan)
    monkeypatch.setattr(runner,"assess_papers",assess)
    monkeypatch.setattr(runner,"execute_preanalysis",lambda *a,**k:{"status":"skipped","processed":0})


def test_scheduled_portrait_themes_rotate_without_six_paper_total_cap(setup_db):
    factory,_,_=setup_db
    from backend.discovery import reads
    # One official line remains manually disabled. Five new DB-evidenced
    # themes can be explored after the administrator opts into daily AI runs.
    portrait={"research_lines":[PROFILE["research_lines"][0]]+[
        {"id":"db_theme_"+str(i),"name":"数据库研究主题 "+str(i),
         "problem":"由团队成果及数据目录提出的待验证研究问题",
         "keywords":["urban systems"],"search_queries":[],"method_queries":[]}
        for i in range(1,12)
    ]}
    with factory() as db:
        # An explicit team decision to turn a derived topic off takes priority.
        db.add(SearchStrategy(line_id="db_theme_11",enabled=False))
        db.commit()
        first=create_run(db,portrait,source="scheduled")
        second=create_run(db,portrait,source="scheduled")
        assert first is not None and second is not None
        ids1=reads(first.line_ids_json)
        ids2=reads(second.line_ids_json)
        assert len(ids1)==5
        assert "db_theme_11" not in ids1+ids2
        assert set(ids1+ids2)=={"db_theme_"+str(i) for i in range(1,11)}
        assert set(ids1)!=set(ids2)
