"""The real SC04 experiment is opt-in, safe on restarts, and transparent."""
import json
import pytest
import backend.api as api
from backend.account_onboarding import OwnerClaim
from backend.sc04_evolution import SC04Run, SC04Baseline, load
from backend.team import create_member
from backend.task_venue_radar import TaskVenuePaperRun
from research_workbench.core import session_factory
from scripts.sc04_one_shot_live_pilot import create_snapshot, run_once, RUN_ID, _valid_papers


def make_data(index):
    return {
      "id":"https://openalex.org/W9000"+str(index),
      "title":"Child health and built environment urban exposure "+str(index),
      "abstract":("This paper evaluates childhood environmental health in urban "
                  "neighborhoods, using built environment measures to examine "
                  "spatial exposure patterns. The results need independent "
                  "evaluation across different neighborhoods and cities. "
                  +str(index)),
      "url":"https://doi.org/10.1000/example."+str(index),
      "probe_group":"A", "venue":"Cities",
    }


@pytest.fixture
def db(tmp_path,monkeypatch):
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("TEAM_AUTH_ENABLED","true")
    monkeypatch.delenv("SC04_DEEPSEEK_API_KEY",raising=False)
    monkeypatch.delenv("SC04_R1_ONE_SHOT",raising=False)
    factory=session_factory("sqlite:///"+str(tmp_path/"sc04r1.db"))
    with factory() as session:
        owner=create_member(session,"test-owner@example.invalid","Test Owner",
                            "test-owner-password-123456",role="admin",initial=True)
        owner.role="owner"
        session.add(OwnerClaim(id=1,member_id=owner.id,claimed_at=1))
        session.add(TaskVenuePaperRun(id="real_source_test",member_id=owner.id,
           task_key="child_health_extrapolation",status="completed",
           source_ids_json=json.dumps({"A":["S900"],"B":[],"C":[]}),
           results_json=json.dumps([make_data(i) for i in range(1,6)] +
             [{**make_data(10),"probe_group":"C"},{**make_data(1),"id":"https://openalex.org/W90001"}])))
        session.commit()
        owner_id=owner.id
    return factory,owner_id


def test_one_shot_selection_only_from_approved_a_scan():
    from types import SimpleNamespace
    data=[make_data(1),make_data(2),make_data(3),
          {**make_data(5),"probe_group":"B"},
          {**make_data(1),"title":"Duplicated record"}]
    scan=SimpleNamespace(results_json=json.dumps(data))
    papers=_valid_papers(scan)
    assert len(papers)==3
    assert all(p["group"]=="A" for p in papers)
    assert len({p["id"] for p in papers})==3


def test_provisional_live_run_is_idempotent_preserves_unconfirmed_baseline(db):
    factory,owner_id=db
    result=create_snapshot(factory)
    assert result["status"]=="created"
    assert result["paper_count"]==5
    with factory() as session:
        row=session.get(SC04Run,RUN_ID)
        assert row.member_id==owner_id
        assert row.status=="queued"
        snap=load(row.snapshot_json,{})
        assert snap["baseline_confirmed"] is False
        assert snap["probes_present"]==["A"]
        assert snap["probes_missing"]==["B","C"]
        assert snap["trial_type"]=="first_real_LLM_exploratory_single_probe"
        assert not session.get(SC04Baseline,(owner_id,"child_health_extrapolation"))
    second=create_snapshot(factory)
    assert second["status"]=="already_exists"
    with factory() as session:
        assert session.query(SC04Run).count()==1


def test_explicit_render_user_request_and_key_are_required(db,monkeypatch,capsys):
    factory,_=db
    run_once(factory)
    with factory() as session:
        assert session.get(SC04Run,RUN_ID) is None
    monkeypatch.setenv("SC04_R1_ONE_SHOT","authorized-one-time-sc04-r1-20261115")
    monkeypatch.setenv("DEVSTUDIO_E2E_ISOLATED","1")
    monkeypatch.setenv("PGOPTIONS","-c search_path=atlas_devstudio_e2e_20261114")
    run_once(factory)
    output=capsys.readouterr().out
    assert "sc04_render_deepseek_key_missing" in output
    with factory() as session:
        assert session.get(SC04Run,RUN_ID) is None
