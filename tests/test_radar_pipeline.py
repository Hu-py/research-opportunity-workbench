"""Research Radar integration tests: real SQLite, no model calls or API quota."""
import json
from sqlalchemy import select,func

from research_workbench.core import Paper,session_factory
from backend.ai_lab import AIOpportunity
from backend.radar_pipeline import (
    RadarTopic,RadarTopicEvent,RadarReport,
    assess,sync_ai_opportunities,generate_weekly,get_report,list_topics,
)

PAPER_ID="doi:10.1000/radar.test"

def card(id,title="Road-network access and cooling-service equity",data=True,status="draft"):
    return AIOpportunity(
        id=id,run_id="run-"+id,line_id="urban",
        title=title,
        question="Do network travel times change urban cooling accessibility equity judgments?",
        method="Street network accessibility under multiple fairness principles",
        why_now="Transfer distributional justice metrics to cooling access",
        paper_ids_json=json.dumps([PAPER_ID]),
        dataset_ids_json=json.dumps(["registry-dataset-1"] if data else []),
        baselines_json=json.dumps(["Euclidean accessibility"]),
        experiment="One city, compare network time versus straight-line distance",
        risks_json=json.dumps(["Road data completeness unknown"]),
        critic_json=json.dumps({
            "verdict":"需要补充证据","novelty_status":"未核验",
            "fatal_gaps":["Verify entrances and actual access to population data"],
            "minimum_data":["Street network, park entrances, population grid"],
            "stop_conditions":["Insufficient entrance or network coverage"],
        }),
        status=status,
    )

def prepare_db():
    factory=session_factory("sqlite:///:memory:")
    db=factory()
    db.add(Paper(id=PAPER_ID,title="Transport equity frameworks",abstract="Network justice analysis",
                 doi="10.1000/radar.test",url="https://doi.org/10.1000/radar.test",
                 published="2026-10-01",venue="Test journal",line_ids='["urban"]'))
    db.commit()
    return db

def test_five_gates_do_not_claim_novelty_or_unearned_a():
    x=assess(card("one"))
    assert x["grade"]=="B"
    assert x["gates"]["data_access"]["status"]=="待预检"
    assert x["gates"]["prior_art"]["status"]=="未核验"
    assert x["minimum_data"]
    assert assess(card("two",data=False))["grade"]=="C"
    assert assess(card("three",status="rejected"))["grade"]=="D"

def test_radar_persists_and_merges_evidence_idempotently():
    with prepare_db() as db:
        db.add(card("one"))
        db.commit()
        assert sync_ai_opportunities(db)=={
            "new_topics":1,"revised_topics":0,"skipped_cards":0
        }
        assert sync_ai_opportunities(db)["revised_topics"]==0
        topic=db.scalars(select(RadarTopic)).one()
        assert topic.grade=="B" and topic.version==1
        assert json.loads(topic.paper_ids_json)==[PAPER_ID]
        db.add(card("two",title="Road-network access and cooling-service equity"))
        db.commit()
        second=sync_ai_opportunities(db)
        assert second["new_topics"]==0
        assert second["revised_topics"]==1
        assert topic.version==2
        assert len(json.loads(topic.ai_card_ids_json))==2
        assert db.scalar(select(func.count()).select_from(RadarTopicEvent))==2
        report=generate_weekly(db,period="2026-W45")
        assert "五道评审门" in report
        assert "10.1000/radar.test" in report
        assert "未核验" in report
        assert db.get(RadarReport,"2026-W45") is not None
        assert get_report(db,"2026-W45")==report
        assert list_topics(db)[0]["version"]==2
        assert len(list_topics(db)[0]["papers"])==1

def test_missing_source_not_accepted_as_evidence():
    with prepare_db() as db:
        db.add(card("missing"))
        db.commit()
        db.delete(db.get(Paper,PAPER_ID))
        db.commit()
        result=sync_ai_opportunities(db)
        assert result["new_topics"]==0
        assert result["skipped_cards"]==1
        assert db.scalar(select(func.count()).select_from(RadarTopic))==0

def test_no_ai_cards_no_hallucinated_report():
    with prepare_db() as db:
        report=generate_weekly(db,period="2026-W45")
        assert "尚无已完成 AI 分析" in report
        assert db.scalar(select(func.count()).select_from(RadarTopic))==0
