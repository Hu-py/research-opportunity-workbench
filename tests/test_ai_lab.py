"""P2 offline integration: no DeepSeek calls, no billing, no sensitive uploads."""
import json
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
from backend.ai_lab import (
    AIAnalysisRun,AIOpportunity,PaperUnderstanding,
    create_run,create_scheduled_run,execute,review_card,list_cards,
)
from backend.cusp import import_records
from backend.discovery import PaperCandidate,candidate_id
from backend.model_gateway import DEEPSEEK_URL
from backend.model_vault import ModelCredential,load_key,status as vault_status
from backend.team import create_member
from research_workbench.core import Paper,set_profile,session_factory

PROFILE={"research_lines":[{
    "id":"vertical","name":"建筑垂直功能",
    "problem":"在有限楼层真值条件下推断建筑功能并验证时空泛化",
    "keywords":["building","vertical","function"],
    "search_queries":["urban vertical building function"],
    "method_queries":["self supervised graph learning"],
 }],"goals":"利用非受限数据属性寻找可验证的城市计算新课题"}
REGISTER=[
    {"数据类型":"城市功能与设施","名称":"上海_建筑功能POI","格式":"CSV",
     "范围":"上海","时间":"2022","数据来源":"研究记录","基本信息":"建筑点和功能属性",
     "用于的研究（关键结果）":"功能识别","数据持有人":"内部人员","F盘":"✅","是否备份":""},
    {"数据类型":"公共事件","名称":"个人隐私轨迹_2025","格式":"CSV",
     "范围":"上海","时间":"2025","数据来源":"私人合作方","基本信息":"个人移动记录",
     "用于的研究（关键结果）":"","数据持有人":"敏感账户","F盘":"✅","是否备份":""},
]
HEADERS={"Authorization":"Bearer protected-backend-token"}
PAPER_ID="doi:10.4321/test.graph"

def backend_response(kind,payload):
    if kind=="planner":
        return {"bottleneck":"缺乏高质量楼层功能真值",
                "research_gap_questions":["图表征能否减少真值需求"],
                "data_assumptions":["核实功能标注完整性"]}
    if kind=="reader":
        return {"papers":[{"paper_id":p["id"],"problem":"有限标注下的功能推断",
                "method":"自监督图学习","limitations":"没有城市尺度基线对照",
                "evidence_level":"abstract"} for p in payload["papers"]]}
    if kind=="generator":
        dataset=payload["datasets"][0]["id"]
        paper=payload["paper_readings"]["papers"][0]["paper_id"]
        return {"ideas":[{"title":"面向楼层功能的低标注图迁移试验",
               "question":"图迁移能否提高跨区域验证性能",
               "method":"对照图学习与非图基线","why_now":"比现有功能识别多跨域评估",
               "paper_ids":[paper],"dataset_ids":[dataset],
               "baselines":["XGBoost","GraphSAGE"],
               "minimal_experiment":"空间留出测试，比较 QWK 和 MAE",
               "risks":["楼层标签数量不充分"]}]}
    if kind=="critic":
        return {"reviews":[{"title":p["title"],"verdict":"需要补充证据",
                "novelty_status":"未核实","fatal_gaps":["缺少独立标注"],
                "revised_experiment":"先开展空间外推留出实验"} for p in payload["ideas"]]}
    raise AssertionError(kind)

def transport_handler(request,fail_on=None,malicious=False):
    assert str(request.url)==DEEPSEEK_URL
    assert request.headers.get("authorization")=="Bearer ds-TEST-very-secret-value"
    data=json.loads(request.content)
    context=data["messages"][0]["content"]
    prompt=json.loads(data["messages"][1]["content"])
    assert data["response_format"]=={"type":"json_object"}
    assert "F盘" not in data["messages"][1]["content"]
    assert "敏感账户" not in data["messages"][1]["content"]
    if "研究规划阶段" in context:stage="planner"
    elif "论文阅读阶段" in context:stage="reader"
    elif "迁移及候选选题生成" in context:stage="generator"
    elif "审稿人" in context:stage="critic"
    else:raise AssertionError("Unknown model stage")
    if fail_on==stage:return httpx.Response(402,json={"error":"Insufficient balance"})
    result=backend_response(stage,prompt)
    if malicious and stage=="generator":
        result["ideas"][0]["paper_ids"]=["invented-unverified-paper"]
    return httpx.Response(200,json={
        "choices":[{"finish_reason":"stop","message":{"content":json.dumps(result,ensure_ascii=False)}}],
        "usage":{"prompt_tokens":100,"completion_tokens":80}
    })

@pytest.fixture
def lab(tmp_path,monkeypatch):
    monkeypatch.setenv("MODEL_VAULT_KEY",Fernet.generate_key().decode())
    monkeypatch.setenv("API_BEARER_TOKEN","protected-backend-token")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("TEAM_BOOTSTRAP_ENABLED","false")
    monkeypatch.delenv("CUSP_DATA_BOOTSTRAP_ZB64",raising=False)
    factory=session_factory("sqlite:///"+str(tmp_path/"p2.sqlite"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    with factory() as db:
        create_member(db,"admin@example.org","System Admin",
            "local-p2-admin-password",role="admin",initial=True)
        create_member(db,"member@example.org","Researcher",
            "local-p2-member-password",role="researcher")
        set_profile(db,PROFILE)
        import_records(db,REGISTER)
        db.add(Paper(id=PAPER_ID,title="Self-supervised graph transfer for urban functions",
            abstract="Building graphs can transfer function labels between districts.",
            doi="10.4321/test.graph",url="https://doi.org/10.4321/test.graph",
            venue="Example Journal",published="2026-09-01",line_ids='["vertical"]'))
        db.add(PaperCandidate(id=candidate_id("vertical",PAPER_ID),
            line_id="vertical",paper_id=PAPER_ID,
            title="Self-supervised graph transfer for urban functions",
            abstract="Building graphs can transfer function labels between districts.",
            url="https://doi.org/10.4321/test.graph",doi="10.4321/test.graph",
            score=83,status="relevant",match_type="method"))
        db.commit()
    with TestClient(api.app) as client:
        login=client.post("/api/auth/login",headers=HEADERS,json={
            "email":"admin@example.org","password":"local-p2-admin-password"})
        assert login.status_code==200,login.text
        editor=client.post("/api/auth/login",headers=HEADERS,json={
            "email":"member@example.org","password":"local-p2-member-password"})
        assert editor.status_code==200
        yield factory,client,{**HEADERS,"X-Research-Session":login.json()["token"]},\
             {**HEADERS,"X-Research-Session":editor.json()["token"]},monkeypatch

def save_key(client,headers):
    r=client.put("/api/ai-lab/config",headers=headers,json={
        "key":"ds-TEST-very-secret-value","reason_model":"deepseek-flash"})
    assert r.status_code==200,r.text
    assert r.json()["configured"]
    assert "ds-TEST" not in r.text
    return r

def test_admin_key_is_encrypted_not_returned_and_daily_is_opt_in(lab):
    factory,client,admin,member,_=lab
    assert client.get("/api/ai-lab",headers=admin).json()["config"]["configured"] is False
    assert client.post("/api/ai-lab/run",headers=admin,json={"line_id":"vertical"}).status_code==422
    assert client.put("/api/ai-lab/config",headers=member,
        json={"key":"ds-TEST-very-secret-value"}).status_code==403
    save_key(client,admin)
    with factory() as db:
        encrypted=db.get(ModelCredential,"deepseek").encrypted_key
        assert "ds-TEST" not in encrypted
        assert load_key(db)=="ds-TEST-very-secret-value"
        assert create_scheduled_run(db) is None
    result=client.get("/api/ai-lab",headers=member)
    assert result.status_code==200
    assert "ds-TEST" not in result.text
    assert "encrypted_key" not in result.text
    enabled=client.put("/api/ai-lab/config",headers=admin,json={"daily_enabled":True})
    assert enabled.status_code==200
    with factory() as db:
        assert db.get(ModelCredential,"deepseek").daily_enabled
    removed=client.delete("/api/ai-lab/key",headers=admin)
    assert removed.status_code==200
    assert not removed.json()["configured"] and not removed.json()["daily_enabled"]

def test_four_stage_mock_analysis_and_cited_cards(lab):
    factory,client,admin,member,monkeypatch=lab
    save_key(client,admin)
    def mock_execution(factory,id):
        with httpx.Client(transport=httpx.MockTransport(transport_handler)) as http:
            return execute(factory,id,client=http)
    monkeypatch.setattr(api,"execute_ai_analysis",mock_execution)
    done=client.post("/api/ai-lab/run",headers=member,json={"line_id":"vertical"})
    assert done.status_code==202,done.text
    with factory() as db:
        run=db.get(AIAnalysisRun,done.json()["id"])
        assert run.status=="completed" and run.stage=="done", (run.stage,run.error)
        assert run.model_calls==4
        assert run.input_tokens==400 and run.output_tokens==320
        assert len(db.scalars(select(PaperUnderstanding)).all())==1
        cards=list_cards(db)
        assert len(cards)==1
        assert cards[0]["papers"][0]["id"]==PAPER_ID
        assert cards[0]["critic"]["novelty_status"].startswith("尚未完成")
        assert "敏感" not in run.snapshot_json
        assert "个人隐私轨迹" not in run.snapshot_json
        assert "内部人员" not in run.snapshot_json
        assert "ds-TEST" not in run.snapshot_json
    item=client.get("/api/ai-lab",headers=member).json()
    assert item["runs"][0]["status"]=="completed"
    draft=item["cards"][0]
    accepted=client.patch("/api/ai-lab/cards/"+draft["id"],headers=member,
        json={"status":"shortlist"})
    assert accepted.status_code==200
    assert accepted.json()["status"]=="shortlist"

def test_failure_resume_and_invalid_paper_citation_rejected(lab):
    factory,client,admin,member,monkeypatch=lab
    save_key(client,admin)
    def fail_first(factory,id):
        with httpx.Client(transport=httpx.MockTransport(
            lambda req:transport_handler(req,fail_on="generator"))) as http:
            return execute(factory,id,client=http)
    monkeypatch.setattr(api,"execute_ai_analysis",fail_first)
    run=client.post("/api/ai-lab/run",headers=member,json={"line_id":"vertical"})
    assert run.status_code==202
    rid=run.json()["id"]
    with factory() as db:
        state=db.get(AIAnalysisRun,rid)
        assert state.status=="failed" and state.stage=="generator"
        assert state.model_calls==2
        assert state.error.startswith("DeepSeek HTTP 402")
    def recover(factory,id):
        with httpx.Client(transport=httpx.MockTransport(transport_handler)) as http:
            return execute(factory,id,client=http)
    monkeypatch.setattr(api,"execute_ai_analysis",recover)
    resumed=client.post("/api/ai-lab/runs/"+rid+"/resume",headers=member,json={})
    assert resumed.status_code==202
    with factory() as db:
        state=db.get(AIAnalysisRun,rid)
        assert state.status=="completed" and state.model_calls==4, (state.stage,state.error)
        assert len(db.scalars(select(AIOpportunity)).all())==1
    def harmful(factory,id):
        with httpx.Client(transport=httpx.MockTransport(
            lambda req:transport_handler(req,malicious=True))) as http:
            return execute(factory,id,client=http)
    monkeypatch.setattr(api,"execute_ai_analysis",harmful)
    second=client.post("/api/ai-lab/run",headers=member,json={"line_id":"vertical"})
    assert second.status_code==202
    with factory() as db:
        failed=db.get(AIAnalysisRun,second.json()["id"])
        assert failed.status=="failed" and "未知论文" in failed.error
        assert len(db.scalars(select(AIOpportunity)).all())==1

def test_one_scheduled_run_per_day_and_no_key_after_removal(lab):
    factory,client,admin,_,_=lab
    save_key(client,admin)
    with factory() as db:
        assert create_scheduled_run(db) is None
    enabled=client.put("/api/ai-lab/config",headers=admin,json={"daily_enabled":True})
    assert enabled.status_code==200
    with factory() as db:
        task=create_scheduled_run(db)
        assert task is not None and task.source=="scheduled"
        assert create_scheduled_run(db) is None
    client.delete("/api/ai-lab/key",headers=admin)
    with factory() as db:
        assert create_scheduled_run(db) is None
