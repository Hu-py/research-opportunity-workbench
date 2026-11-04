"""Live-database-free tests for the headless research portrait audit.

These use synthetic database records only; never need Vercel, DeepSeek,
OpenAlex, user credentials, raw datasets or an external Postgres connection.
"""
import json
import logging

import backend.api  # register all SQLAlchemy tables
from backend.cusp import import_records
from backend.profile_audit import audit,emit_log_report
from backend.profile_intelligence import initialize_database_draft
from backend.repository import TeamAchievement
from backend.team import current_profile_version
from research_workbench.core import get_profile,set_profile,session_factory

def _database(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"headless.db"))
    with factory() as db:
        set_profile(db,{"team":{"name":"Test research group","mission":"",
                "priorities":[]},"goals":"Documented research scope",
            "methods":["Network analysis"],"excluded_terms":[],"datasets":[],
            "research_lines":[{"id":"urban_network","name":"Urban networks",
                "problem":"Scale limitations","keywords":["network"],
                "search_queries":["urban network resilience"],
                "method_queries":["graph representation learning"]}]})
        for i,title,tags in [
            (1,"Urban street resilience",["resilience","network"]),
            (2,"Urban mobility resilience",["resilience","network"]),
            (3,"Mobility access inequalities",["inequality","mobility"]),
            (4,"Urban digital space and perception",["social sensing","mobility"])
        ]:
            db.add(TeamAchievement(id="ach_synthetic_"+str(i),title=title,
               year=2025,kind="paper",status="verified",tags_json=json.dumps(tags)))
        db.commit()
        import_records(db,[
            {"数据类型":"城市功能与设施","名称":"Street network data","格式":"shp",
             "范围":"Shanghai","时间":"2022","数据来源":"internal",
             "基本信息":"Network geometry","用于的研究（关键结果）":"",
             "数据持有人":"Private Custodian","F盘":"✅","是否备份":""},
            {"数据类型":"公共事件","名称":"个人隐私轨迹 2025","格式":"csv",
             "范围":"Shanghai","时间":"2025","数据来源":"secure",
             "基本信息":"Individual trajectories","用于的研究（关键结果）":"",
             "数据持有人":"Restricted Person","F盘":"✅","是否备份":""}
        ])
    initialize_database_draft(factory)
    return factory

def test_end_to_end_headless_profile_audit_is_evidence_based(tmp_path):
    factory=_database(tmp_path)
    with factory() as db:
        before=get_profile(db)
        version=current_profile_version(db)
        report=audit(db)
        assert report["source"]=="live-render-postgresql"
        assert report["counts"]["achievements_verified"]==4
        assert report["counts"]["data_assets_total"]==2
        assert report["counts"]["data_assets_eligible"]==1
        assert report["counts"]["approved_papers"]==0
        assert report["checks"]["review_draft_present"] is True
        assert report["checks"]["evidence_refs_exist"]=="pass"
        assert report["checks"]["official_version_unchanged"] is True
        assert report["checks"]["llm_invoked"] is False
        assert len(report["proposed_lines"])>=2
        assert any(x["type"]=="verified_output_topic_cluster"
                   for x in report["proposed_lines"])
        as_text=json.dumps(report,ensure_ascii=False)
        assert "Private Custodian" not in as_text
        assert "Restricted Person" not in as_text
        assert "个人隐私轨迹" not in as_text
        assert get_profile(db)==before
        assert current_profile_version(db)==version

def test_log_mode_only_includes_nonrestricted_metadata(tmp_path):
    factory=_database(tmp_path)
    messages=[]
    class Collector(logging.Handler):
        def emit(self,record):
            messages.append(record.getMessage())
    logger=logging.getLogger("test_headless_profile_audit")
    logger.setLevel(logging.INFO)
    handler=Collector()
    logger.addHandler(handler)
    try:
        with factory() as db:
            output=emit_log_report(db,logger)
        assert output["checks"]["report_has_raw_dataset_files"] is False
        assert any(s.startswith("PROFILE_AUDIT_META") for s in messages)
        assert any(s.startswith("PROFILE_AUDIT_ACHIEVEMENT") for s in messages)
        assert any(s.startswith("PROFILE_AUDIT_DATASET") for s in messages)
        assert any(s.startswith("PROFILE_AUDIT_LINE") for s in messages)
        assert any(s.startswith("PROFILE_AUDIT_COMPLETE") for s in messages)
        assert "Restricted Person" not in "\n".join(messages)
        assert "个人隐私轨迹" not in "\n".join(messages)
        assert "Private Custodian" not in "\n".join(messages)
        assert "Street network data" in "\n".join(messages)
    finally:
        logger.removeHandler(handler)
