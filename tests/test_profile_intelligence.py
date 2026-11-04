"""Offline tests: curated research portrait seed, reusable Skill and LLM draft review."""
import base64
import json
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

import backend.api as api
import backend.profile_intelligence as studio
from backend.cusp import import_records
from backend.profile_intelligence import (
    ResearchProfileDraft,ResearchProfileDraftRevision,ProfileSynthesisRun,
    bootstrap_from_env,apply_draft,list_studio,initialize_database_draft,
)
from backend.team import create_member,current_profile_version
from research_workbench.core import get_profile,set_profile,session_factory
from backend.model_vault import save

def outline(name="建筑垂直功能与演化"):
    return {"profile":{
        "goals":"基于城市多源空间数据识别垂直功能与演变",
        "team":{"name":"个人/合作课题整理（待核）",
                "mission":"探索城市三维功能与计算方法的可验证问题",
                "priorities":["数据可信性","跨时空泛化"]},
        "methods":["图神经网络","空间统计"],
        "datasets":[{"name":"PRIVATE_should_not_duplicate"}],
        "excluded_terms":[],
        "research_lines":[{"id":"vertical_urban_function","name":name,
            "problem":"建筑楼层标签稀疏，多期演变验证困难",
            "keywords":["building","vertical","graph"],
            "search_queries":["urban building vertical function"],
            "method_queries":["graph representation learning"]}]},
        "analysis":{
            "positioning":"城市三维功能识别与跨期推断",
            "method_capabilities":["图学习","多模态特征融合"],
            "line_insights":[{"line_id":"vertical_urban_function",
                "bottleneck":"楼层真值稀疏",
                "next_experiment":"空间留出验证与 GraphSAGE/XGBoost 对照",
                "data_requirements":["合法的楼层标签","建筑多期空间对齐"],
                "evidence_status":"described"}],
            "cross_line_opportunities":["结构化楼层信息可支撑社会空间分异讨论（待验证）"],
            "evidence_gaps":["缺少多期楼层真值"],
            "scope_cautions":["个人研究不能自动归属团队成果"]}
    }

@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setenv("API_BEARER_TOKEN","protected-profile-api-token")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("MODEL_VAULT_KEY",Fernet.generate_key().decode())
    monkeypatch.setenv("TEAM_BOOTSTRAP_ENABLED","false")
    monkeypatch.delenv("RESEARCH_PROFILE_BOOTSTRAP_B64",raising=False)
    factory=session_factory("sqlite:///"+str(tmp_path/"portrait.db"))
    monkeypatch.setattr(api,"get_factory",lambda:factory)
    with factory() as db:
        create_member(db,"admin@example.net","Profile Admin",
            "local-profile-admin-password",role="admin",initial=True)
        create_member(db,"viewer@example.net","Team Reader",
            "local-profile-viewer-password",role="viewer")
        set_profile(db,outline()["profile"])
        import_records(db,[{"数据类型":"城市功能与设施",
            "名称":"上海_建筑与POI属性","格式":"csv","范围":"上海","时间":"2022",
            "数据来源":"内部","基本信息":"已登记功能标签",
            "用于的研究（关键结果）":"功能分类","数据持有人":"Private Custodian",
            "F盘":"✅","是否备份":""},
            {"数据类型":"公共事件","名称":"个人隐私轨迹","格式":"csv",
             "范围":"上海","时间":"2025","数据来源":"敏感源",
             "基本信息":"个体位置数据","用于的研究（关键结果）":"",
             "数据持有人":"Sensitive Holder","F盘":"✅","是否备份":""}])
    with TestClient(api.app) as client:
        def login(email,password):
            response=client.post("/api/auth/login",
                headers={"Authorization":"Bearer protected-profile-api-token"},
                json={"email":email,"password":password})
            assert response.status_code==200,response.text
            return {"Authorization":"Bearer protected-profile-api-token",
                    "X-Research-Session":response.json()["token"]}
        admin=login("admin@example.net","local-profile-admin-password")
        reader=login("viewer@example.net","local-profile-viewer-password")
        yield factory,client,admin,reader,monkeypatch

def test_research_profile_skill_is_loadable():
    from backend.skill_loader import load_skills
    raw=load_skills(("research_profile",))
    assert "Research Profile" in raw
    assert "database" in raw.lower()
    assert "datasets" in raw
    with pytest.raises(ValueError):load_skills(("nonexistent_skill",))

def test_chat_draft_is_discarded_and_database_only_draft_is_not_auto_published(env):
    factory,client,admin,reader,monkeypatch=env
    blob=base64.b64encode(json.dumps(outline(),ensure_ascii=False).encode()).decode()
    monkeypatch.setenv("RESEARCH_PROFILE_BOOTSTRAP_B64",blob)
    with factory() as db: before=get_profile(db)
    old=bootstrap_from_env(factory)
    assert old["imported"]
    monkeypatch.delenv("RESEARCH_PROFILE_BOOTSTRAP_B64")
    update=initialize_database_draft(factory)
    assert update["discarded_chat_drafts"]==1
    assert update["new"]
    again=initialize_database_draft(factory)
    assert not again["new"] and again["discarded_chat_drafts"]==0
    response=client.get("/api/profile-intelligence",headers=reader)
    assert response.status_code==200
    payload=response.json()
    assert len(payload["drafts"])==1
    data=payload["drafts"][0]
    assert data["source"]=="database_snapshot"
    assert data["scope"]=="team"
    assert data["profile"]["datasets"]==[]
    assert payload["evidence"]["counts"]["data_assets_total"]==2
    assert payload["evidence"]["counts"]["data_assets_eligible"]==1
    assert payload["evidence"]["source"]=="postgresql_only"
    assert not any("个人隐私轨迹" in x.get("name","")
                   for x in payload["evidence"]["dataset_examples"])
    assert "PRIVATE_should_not_duplicate" not in json.dumps(data)
    with factory() as db:
        old_draft=db.get(ResearchProfileDraft,old["id"])
        assert old_draft.status=="discarded"
        assert get_profile(db)==before
        assert current_profile_version(db)==0
    # Old drafts cannot be promoted even by an admin knowing the ID.
    assert client.post("/api/profile-intelligence/drafts/"+old["id"]+"/apply",
        headers=admin,json={"expected_version":0}).status_code in (409,422)
    assert client.post("/api/profile-intelligence/drafts/"+data["id"]+"/apply",
        headers=reader,json={"expected_version":0}).status_code==403
    applied=client.post("/api/profile-intelligence/drafts/"+data["id"]+"/apply",
        headers=admin,json={"expected_version":0})
    assert applied.status_code==200,applied.text
    with factory() as db:
        assert current_profile_version(db)==1
        assert len(db.scalars(select(ResearchProfileDraftRevision)).all())==2


def test_draft_editor_tracks_version_and_requires_admin(env):
    factory,client,admin,reader,monkeypatch=env
    monkeypatch.setenv("RESEARCH_PROFILE_BOOTSTRAP_B64",
        base64.b64encode(json.dumps(outline(),ensure_ascii=False).encode()).decode())
    bootstrap_from_env(factory)
    monkeypatch.delenv("RESEARCH_PROFILE_BOOTSTRAP_B64")
    ident=initialize_database_draft(factory)["id"]
    p=outline()["profile"]
    p["research_lines"][0]["name"]="精细化建筑楼层语义识别"
    assert client.put("/api/profile-intelligence/drafts/"+ident,headers=reader,
        json={"profile":p,"expected_revision":1}).status_code==403
    response=client.put("/api/profile-intelligence/drafts/"+ident,headers=admin,
        json={"profile":p,"expected_revision":1})
    assert response.status_code==200,response.text
    assert response.json()["revision"]==2
    assert client.put("/api/profile-intelligence/drafts/"+ident,headers=admin,
        json={"profile":p,"expected_revision":1}).status_code==409
    with factory() as db:
        rows=db.scalars(select(ResearchProfileDraftRevision).where(
            ResearchProfileDraftRevision.draft_id==ident)).all()
        assert len(rows)==2
        assert get_profile(db)["research_lines"][0]["name"]!="精细化建筑楼层语义识别"

def test_llm_generates_separate_draft_and_redacts_sensitive_context(env):
    factory,client,admin,reader,monkeypatch=env
    monkeypatch.setenv("RESEARCH_PROFILE_BOOTSTRAP_B64",
        base64.b64encode(json.dumps(outline(),ensure_ascii=False).encode()).decode())
    bootstrap_from_env(factory)
    monkeypatch.delenv("RESEARCH_PROFILE_BOOTSTRAP_B64")
    initialize_database_draft(factory)  # invalidates chat example
    with factory() as db:
        save(db,"admin","ds-TEST-PROFILE-secret-key",reason_model="deepseek-flash")
    def stub_model(key,model,system,payload,client=None,max_tokens=4200):
        assert key=="ds-TEST-PROFILE-secret-key"
        assert model=="deepseek-flash"
        assert "Research Profile" in system
        assert "Private Custodian" not in json.dumps(payload)
        assert "Sensitive Holder" not in json.dumps(payload)
        assert "个人隐私轨迹" not in json.dumps(payload,ensure_ascii=False)
        assert "PRIVATE_should_not_duplicate" not in json.dumps(payload)
        assert "curated_example" not in payload
        assert payload["source_policy"]=="strict_postgresql_only"
        assert payload["non_restricted_data_metadata"][0]["ref"].startswith("cusp_datasets:")
        assert "PRIVATE_should_not_duplicate" not in json.dumps(payload)
        return outline("LLM 归纳的建筑垂直功能研究"),{
            "input_tokens":180,"output_tokens":300}
    monkeypatch.setattr(studio,"request_json",stub_model)
    assert client.post("/api/profile-intelligence/generate",headers=reader,
        json={"notes":"优先考虑图方法"}).status_code==403
    result=client.post("/api/profile-intelligence/generate",headers=admin,
        json={"notes":"优先考虑图方法"})
    assert result.status_code==202,result.text
    response=client.get("/api/profile-intelligence",headers=admin).json()
    assert response["runs"][0]["status"]=="completed",response["runs"][0]["error"]
    draft=response["drafts"][0]
    assert draft["source"]=="llm"
    assert draft["profile"]["research_lines"][0]["name"]=="LLM 归纳的建筑垂直功能研究"
    assert draft["analysis"]["evidence_gaps"]
    assert "ds-TEST-PROFILE" not in json.dumps(response)
    with factory() as db:
        assert get_profile(db)["research_lines"][0]["name"]=="建筑垂直功能与演化"

def test_llm_invalid_line_rejected_and_old_official_version_cannot_be_overwritten(env):
    factory,client,admin,_,monkeypatch=env
    with factory() as db:
        save(db,"admin","ds-TEST-PROFILE-secret-key",reason_model="deepseek-flash")
    def hallucination(*args,**kwargs):
        wrong=outline();wrong["analysis"]["line_insights"][0]["line_id"]="fake_line"
        return wrong,{"input_tokens":1,"output_tokens":1}
    monkeypatch.setattr(studio,"request_json",hallucination)
    result=client.post("/api/profile-intelligence/generate",headers=admin,json={})
    assert result.status_code==202
    with factory() as db:
        run=db.scalars(select(ProfileSynthesisRun)).first()
        assert run.status=="failed" and "不存在" in run.error
    monkeypatch.setenv("RESEARCH_PROFILE_BOOTSTRAP_B64",
        base64.b64encode(json.dumps(outline(),ensure_ascii=False).encode()).decode())
    bootstrap_from_env(factory)
    monkeypatch.delenv("RESEARCH_PROFILE_BOOTSTRAP_B64")
    seeded=initialize_database_draft(factory)
    with factory() as db:
        before=get_profile(db)
        before["goals"]="其他管理员新近更新了正式科研画像"
        from backend.team import save_team_profile
        save_team_profile(db,before,"admin",expected_version=0)
    out=client.post("/api/profile-intelligence/drafts/"+seeded["id"]+"/apply",
        headers=admin,json={"expected_version":1})
    assert out.status_code==409
    with factory() as db:
        assert get_profile(db)["goals"]=="其他管理员新近更新了正式科研画像"
