"""Offline guardrail and weekly synthesis tests. No paid API requests."""
from datetime import datetime, timezone
from sqlalchemy import select

from research_workbench.core import session_factory, set_profile, Paper
from backend.model_vault import ModelCredential
from backend.research_budget import reserve, status, record_usage
from backend.discovery import PaperCandidate
from backend.preanalysis import PaperPreanalysis
from backend.radar_pipeline import RadarReport
import backend.weekly_synthesis as weekly


def test_daily_limits_are_durable_across_requests(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_DAILY_TOKEN_ALLOWANCE","350000")
    factory=session_factory("sqlite:///"+str(tmp_path/"budget.sqlite"))
    day="2026-11-05"
    for _ in range(5):
        assert reserve(factory,calls=1,tokens=12000,day=day)
    for _ in range(10):
        assert reserve(factory,calls=1,tokens=21000,papers=8,day=day)
    with factory() as db:
        view=status(db,day=day)
        assert view["used"]["papers"]==80
        assert view["used"]["model_calls"]==15
        assert view["used"]["token_reservation"]==270000
    assert not reserve(factory,calls=1,tokens=21000,papers=1,day=day)
    assert reserve(factory,calls=1,tokens=12000,day="2026-11-06")
    record_usage(factory,{"input_tokens":100,"output_tokens":60},day=day)
    with factory() as db:
        assert status(db,day=day)["used"]["output_tokens"]==60


def test_weekly_report_is_llm_generated_private_and_review_gated(tmp_path,monkeypatch):
    factory=session_factory("sqlite:///"+str(tmp_path/"weekly.sqlite"))
    with factory() as db:
        set_profile(db,{"research_lines":[{
            "id":"urban","name":"Vertical urban functions",
            "problem":"How to infer building floor use using graph learning",
            "keywords":["buildings"],"search_queries":[],"method_queries":[],
        }]})
        db.add(ModelCredential(provider="deepseek",encrypted_key="mock-key",
                               daily_enabled=True))
        db.add(PaperCandidate(id="cand_test",line_id="urban",paper_id="W123",
            title="Graph transfer across urban systems",abstract="We investigate graph transfer.",
            doi="",url="https://openalex.org/W123",venue="Urban Journal",
            published="2026-11-03",score=90,status="pending",
            last_seen=datetime(2026,11,5,tzinfo=timezone.utc)))
        db.add(PaperPreanalysis(candidate_id="cand_test",paper_id="W123",
            abstract_hash="test",model="deepseek-flash",status="completed",
            fit_score=90,priority="high_priority",
            analysis_json='{"method":"graph transfer","relevance_type":"method_transfer","reason":"cross-domain"}'))
        db.commit()
    monkeypatch.setattr(weekly,"load_key",lambda db:"test-key")
    calls=[]
    def fake(key,model,system,payload,client=None,max_tokens=3500):
        calls.append(payload)
        return ({"week_overview":"图迁移方法可能启发跨城市建筑功能推断。",
          "trends":[{"name":"跨域图学习","interpretation":"需要多城市验证",
                     "paper_ids":["W123","fake"]}],
          "opportunities":[{"question":"跨城市楼层功能迁移是否可靠？",
                            "method":"图表示学习","data_fit":"需核实目标城市数据",
                            "minimal_experiment":"留一城市验证",
                            "unknowns":["完整标签规模未知"],
                            "candidate_ids":["cand_test","fake"],"review_required":True}],
          "gaps_and_next_searches":["空间外推评估"],"limitations":"摘要级证据。"},
          {"input_tokens":700,"output_tokens":250})
    monkeypatch.setattr(weekly,"request_json",fake)
    timestamp=datetime(2026,11,5,tzinfo=timezone.utc)
    result=weekly.synthesize(factory,today=timestamp)
    assert result["status"]=="completed"
    assert len(calls)==1
    with factory() as db:
        report=db.get(RadarReport,weekly.weekly_period(timestamp))
        assert "LLM 综合研判" in report.markdown
        assert "cand_test" in report.markdown
        assert "fake" not in report.markdown
        assert "人工审核" in report.markdown
        assert db.get(PaperCandidate,"cand_test").status=="pending"
        assert db.get(Paper,"W123") is None
    assert weekly.synthesize(factory,today=timestamp)["status"]=="already_completed"
    assert len(calls)==1
