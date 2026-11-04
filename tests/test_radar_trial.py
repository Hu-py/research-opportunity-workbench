"""First-run Radar retrieval: real DB query provenance, fake external API offline."""
import json
from datetime import date,timedelta

from sqlalchemy import select

from research_workbench.core import Paper, session_factory, set_profile
from backend.profile_intelligence import ResearchProfileDraft
from backend import radar_trial


def profile(query="graph learning urban mobility"):
    return {"research_lines":[{
        "id":"actual_line","name":"Evidence-linked urban mobility",
        "problem":"Study evidence based network analysis",
        "keywords":["mobility","graph"],
        "search_queries":[query],"method_queries":["spatiotemporal graph learning"],
    }],"excluded_terms":[],"datasets":[],"methods":[]}


def mock_work():
    return {"id":"https://openalex.org/W12345678",
            "title":"Graph learning for urban mobility",
            "doi":"https://doi.org/10.9999/quality-check",
            "publication_date":date.today().isoformat(),
            "abstract_inverted_index":{"Graph":[0],"mobility":[1],"learning":[2]},
            "primary_location":{"source":{"display_name":"Test Venue"}}}


def test_trial_uses_real_db_draft_and_does_not_approve_papers(tmp_path,monkeypatch):
    factory=session_factory("sqlite:///"+str(tmp_path/"trial.db"))
    with factory() as db:
        set_profile(db,profile("official fallback query"))
        db.add(ResearchProfileDraft(
            id="db_studio_trial",source="database_snapshot",scope="team",
            status="draft",base_version=1,revision=1,
            profile_json=json.dumps(profile(),ensure_ascii=False),
            analysis_json="{}",provenance_json="[]",
        ))
        db.commit()
        source,queries=radar_trial.choose_queries(db)[1],radar_trial.choose_queries(db)[0]
        assert source.startswith("database_evidence_draft:")
        assert queries[0]["query"]=="graph learning urban mobility"
        future=dict(mock_work())
        future["id"]="https://openalex.org/WFUTURE"
        future["doi"]="https://doi.org/10.9999/future"
        future["publication_date"]=(date.today()+timedelta(days=120)).isoformat()
        monkeypatch.setattr(radar_trial,"query_openalex",
                            lambda query,since,limit,client=None:[mock_work(),future])
        ident=radar_trial.create_trial(db)
    assert radar_trial.execute_trial(factory,ident) is True
    with factory() as db:
        latest=radar_trial.latest_trial(db)
        report=latest["report"]
        assert latest["status"]=="completed"
        assert report["query_count"]==2
        assert report["matched"]==2 and report["unique_papers"]==1
        assert report["with_doi"]==1
        assert report["with_abstract"]==1
        assert report["lexically_relevant"]==1
        assert report["future_dated_skipped"]==2
        assert all(p["published"]<=date.today().isoformat() for p in report["papers"])
        assert report["papers"][0]["doi"]=="10.9999/quality-check"
        assert db.scalars(select(Paper)).all()==[]
        assert radar_trial.create_trial(db,startup=True) is None


def test_trial_without_profile_shows_real_failure(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"empty.db"))
    with factory() as db:
        ident=radar_trial.create_trial(db)
    assert radar_trial.execute_trial(factory,ident) is False
    with factory() as db:
        result=radar_trial.latest_trial(db)
        assert result["status"]=="failed"
        assert "数据库画像" in result["error"]
        assert not result["report"]


def test_trial_rejects_rapid_repeat(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"repeat.db"))
    with factory() as db:
        first=radar_trial.create_trial(db)
        row=db.get(radar_trial.RadarTrialRun,first)
        row.status="completed"
        db.commit()
        try:
            radar_trial.create_trial(db)
            assert False,"Must be rate limited"
        except ValueError as e:
            assert "五分钟" in str(e)
