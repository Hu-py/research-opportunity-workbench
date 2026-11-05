"""Deterministic, offline integration tests for the paired scientific tournament."""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.scientific_tournament as tour
from backend.ai_lab import _validated as legacy_validated
from backend.model_vault import ModelCredential
from backend.research_budget import ResearchDailyBudget
from research_workbench.core import Base, Profile, Paper


def factory_for(tmp_path,monkeypatch):
    engine=create_engine("sqlite:///"+str(tmp_path/"tournament.db"))
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    profile={"goals":"Compare grounded scientific opportunities","research_lines":[{
        "id":"city","name":"Urban systems",
        "problem":"How do spatial models generalize across cities?",
        "keywords":[],"search_queries":[],"method_queries":[]
    }]}
    with factory() as db:
        db.add(Profile(id=1,payload=json.dumps(profile)))
        db.add(Paper(id="doi:10.1234/urban",
                     title="Graph learning in urban contexts",
                     abstract="Graph model with out-of-sample testing.",
                     doi="10.1234/urban",url="https://doi.org/10.1234/urban",
                     venue="Test journal",published="2025-01-01",
                     line_ids=json.dumps(["city"])))
        db.add(ModelCredential(provider="deepseek",encrypted_key="mock",
                               fast_model="deepseek-flash",
                               reason_model="deepseek-v4-pro"))
        db.commit()
    # The existing _snapshot requires manually accepted PaperCandidate rows.
    from backend.discovery import PaperCandidate, candidate_id
    with factory() as db:
        db.add(PaperCandidate(
            id=candidate_id("city","doi:10.1234/urban"),
            line_id="city",paper_id="doi:10.1234/urban",
            title="Graph learning in urban contexts",
            abstract="Graph model with out-of-sample testing.",
            doi="10.1234/urban",url="https://doi.org/10.1234/urban",
            published="2025-01-01",venue="Test journal",
            score=90,score_reason="Reviewed for paired test",
            match_type="direct",status="relevant",matched_queries_json="[]"))
        db.commit()
    monkeypatch.setattr(tour,"load_key",lambda db:"test-only-key")
    return factory


def candidate(title):
    return {"title":title,"question":"Can transport models generalize across cities?",
            "mechanism":"Spatial interaction changes with environment",
            "falsifiable_prediction":"Held-out-city validation loses accuracy",
            "method":"Spatial transfer diagnostic",
            "minimal_experiment":"Compare city holdout and random split",
            "baselines":["Non-spatial baseline"],
            "paper_ids":["doi:10.1234/urban"],
            "dataset_ids":[],"limitations":["No validated external outcomes"]}


def fake_model_factory():
    seen=[]
    def call(key,model,system,payload,client=None,max_tokens=1900):
        assert key=="test-only-key"
        seen.append({"system":system,"payload":payload})
        if "研究规划阶段" in system:
            return {"bottleneck":"Out of city evaluation","research_gap_questions":["Which domains fail?"],"data_assumptions":["Comparable spatial data"]},{"input_tokens":40,"output_tokens":25}
        if "论文阅读阶段" in system:
            return {"papers":[{"paper_id":"doi:10.1234/urban",
                "problem":"Graph urban transfer","method":"Graph learning",
                "limitations":"Cannot establish city transfer","evidence_level":"abstract"}]},{"input_tokens":40,"output_tokens":25}
        if "迁移及候选选题生成" in system:
            return {"ideas":[{"title":"Legacy graph approach",
                "question":"Does generalization improve?",
                "method":"Graph model comparison",
                "why_now":"Potential transfer gap",
                "paper_ids":["doi:10.1234/urban"],"dataset_ids":[],
                "baselines":["Nonspatial baseline"],
                "minimal_experiment":"Compare held-out city accuracy",
                "risks":["Unverified novelty"]}]},{"input_tokens":40,"output_tokens":25}
        if "你是审稿人" in system and "五道" not in system:
            return {"reviews":[{"title":"Legacy graph approach",
                "verdict":"需要补充证据",
                "novelty_status":"unverified",
                "fatal_gaps":["External labels missing"],
                "minimum_data":["Holdout city outcomes"],
                "stop_conditions":["No labels available"],
                "revised_experiment":"Assess feasibility first"}]},{"input_tokens":40,"output_tokens":25}
        if "现在只从你自己的科研视角" in system:
            lens=("problem" if "互相冲突" in system
                  else "method" if "跨学科方法迁移" in system else "data")
            return {"candidate":candidate("Independent "+lens)},{"input_tokens":40,"output_tokens":25}
        if "反方审稿人" in system:
            return {"target_id":payload["target"]["id"],
                    "stance":"revise","objections":["No independent validation"],
                    "counter_paper_ids":["doi:10.1234/urban"],
                    "tests":["Leave-city-out split"],"reason":"Existing study is incomplete"}, {"input_tokens":40,"output_tokens":25}
        if "原始研究方向的负责 Agent" in system:
            revised=dict(payload["original"])
            revised["title"]="Revised "+revised["title"]
            return {"change_type":"refine","material_change":True,
                    "response_to_challenge":"Explicitly test city transfer",
                    "candidate":revised},{"input_tokens":40,"output_tokens":25}
        if "竞赛仲裁者" in system:
            return {"outcome":"plural","selected_ids":["H_problem","H_data"],
                    "reason":"Different falsifiable mechanisms deserve separate testing",
                    "unresolved_disagreements":["Transfer may be data-dependent"],
                    "stopping_reason":"All proposed revisions reviewed"}, {"input_tokens":40,"output_tokens":25}
        raise AssertionError("Unexpected prompt")
    return call,seen


def test_paired_run_reuses_legacy_prompts_same_snapshot_and_human_blinding(tmp_path,monkeypatch):
    factory=factory_for(tmp_path,monkeypatch)
    with factory() as db:
        item=tour.start_run(db,"city","Does spatial transfer generalize outside one city?","reviewer-a")
        run_id=item.id
    mock,calls=fake_model_factory()
    assert tour.execute(factory,run_id,model_call=mock)
    assert len(calls)==14  # 4 real legacy stages + 3 seeds + 3 critiques + 3 revisions + 1 judge
    baseline_reader=calls[1]["payload"]["papers"]
    seeds=calls[4:7]
    assert all(s["payload"]["papers"]==baseline_reader for s in seeds)
    assert all("other_hypotheses" not in s["payload"] for s in seeds)
    with factory() as db:
        item=db.get(tour.ScientificTournamentRun,run_id)
        output=tour.summary(item,True)
        assert item.stage=="done" and item.status=="completed"
        assert output["baseline"][0]["title"]=="Legacy graph approach"
        assert [x["id"] for x in output["round0"]]==["H_problem","H_method","H_data"]
        assert output["decision"]["outcome"]=="plural"
        assert len(output["decision"]["selected_ids"])==2
        assert output["novelty_verified"] is False
        budget=db.get(ResearchDailyBudget,tour.now().date().isoformat())
        assert budget.reserved_calls==14
        assert budget.actual_input_tokens==560
        blind=tour.blind_cards(item)
        assert len(blind["cards"])==2
        assert {blind["cards"][0]["blind_id"],blind["cards"][1]["blind_id"]}=={"方案一","方案二"}
        assert "origin" not in str(blind["cards"])
        label=blind["cards"][0]["blind_id"]
        rating=tour.submit_rating(db,run_id,"second-reviewer",label,
                                  4,3,4,5,"test","Need independent empirical evaluation")
        assert rating["status"]=="recorded"
        review=tour.review_summary(db,run_id)
        assert review["results"][label]["review_count"]==1
        with pytest.raises(ValueError,match="已评估"):
            tour.submit_rating(db,run_id,"second-reviewer",label,4,3,4,5,"test")
    assert not tour.execute(factory,run_id,model_call=mock)


def test_adjudication_can_retain_multiple_views_and_reject_fabricated_ids(tmp_path,monkeypatch):
    factory=factory_for(tmp_path,monkeypatch)
    with factory() as db:
        snapshot={"papers":[{"id":"p1"}],"datasets":[]}
    with pytest.raises(ValueError,match="不存在"):
        tour._validated("arbitrate",{
            "outcome":"single","selected_ids":["H_fabricated"],
            "reason":"Fabricated comparison",
            "stopping_reason":"No evidence"},snapshot,{})


def test_tournament_resume_preserves_prior_results(tmp_path,monkeypatch):
    factory=factory_for(tmp_path,monkeypatch)
    with factory() as db:
        run_id=tour.start_run(db,"city","Does domain shift undermine graph learning?","reviewer-a").id
    good,calls=fake_model_factory()
    first=True
    def flaky(*args,**kwargs):
        nonlocal first
        if len(calls)==1 and first:
            first=False
            raise ValueError("Synthetic model failure")
        return good(*args,**kwargs)
    assert not tour.execute(factory,run_id,model_call=flaky)
    with factory() as db:
        run=db.get(tour.ScientificTournamentRun,run_id)
        assert run.stage=="baseline_reader"
        assert run.status=="failed"
        assert "baseline_planner" in json.loads(run.outputs_json)
        tour.resume(db,run_id,"reviewer-a")
    assert tour.execute(factory,run_id,model_call=good)
    with factory() as db:
        run=db.get(tour.ScientificTournamentRun,run_id)
        assert run.status=="completed"
        assert run.model_calls==14
        # Failed provider call reserved budget, but isn't counted as successful model response.
        budget=db.get(ResearchDailyBudget,tour.now().date().isoformat())
        assert budget.reserved_calls==15


def test_early_exit_when_every_counter_review_rejects(tmp_path,monkeypatch):
    outputs={"challenge_"+role:{"stance":"reject"} for role in tour.LENSES}
    assert tour._advance(outputs,"challenge_data")=="arbitrate"
    assert tour._advance({},"revision_problem")=="revision_method"
