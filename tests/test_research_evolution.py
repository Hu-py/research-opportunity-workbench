"""No prior human paper approval: mocked full scientific search/evolution/feedback tests."""
import json
import pytest

from research_workbench.core import Profile, session_factory
from backend.model_vault import ModelCredential
from backend.research_evolution import (
    EvolutionRun, EvolutionPolicy, create_run, feedback, view, readiness,
    policy_report, MAX_PAPERS)
import backend.research_evolution as evo
import backend.research_evolution_runner as runner


def make_factory(tmp_path,monkeypatch):
    monkeypatch.setenv("MODEL_VAULT_KEY","test-vault-is-present")
    monkeypatch.delenv("RESEARCH_DAILY_MODEL_CALL_LIMIT",raising=False)
    monkeypatch.delenv("RESEARCH_DAILY_TOKEN_ALLOWANCE",raising=False)
    factory=session_factory("sqlite:///"+str(tmp_path/"evolution.db"))
    monkeypatch.setattr(evo,"load_key",lambda db:"unit-test-key")
    monkeypatch.setattr(runner,"load_key",lambda db:"unit-test-key")
    with factory() as db:
        db.add(ModelCredential(provider="deepseek",encrypted_key="mock-key"))
        db.add(Profile(id=1,payload=json.dumps({
            "research_lines":[{"id":"city","name":"Urban graph learning",
            "problem":"Can learned spatial graph structures transfer between cities?",
            "keywords":["graph learning"],"search_queries":[],
            "method_queries":[]}]})))
        db.commit()
    return factory


PAPERS=[
    {"id":"doi:10.1000/a","title":"Graph transfer across regions",
     "abstract":"A transfer and ablation experiment","doi":"10.1000/a",
     "url":"https://doi.org/10.1000/a","published":"2025-01-01","venue":"Journal A"},
    {"id":"doi:10.1000/b","title":"Spatial domain shifts",
     "abstract":"Counterfactual benchmarks for spatial distribution shift",
     "doi":"10.1000/b","url":"https://doi.org/10.1000/b",
     "published":"2024-01-01","venue":"Journal B"},
    {"id":"doi:10.1000/c","title":"Novelty challenge reference",
     "abstract":"Prior work reporting a failure mechanism","doi":"10.1000/c",
     "url":"https://doi.org/10.1000/c","published":"2023-01-01","venue":"Journal C"},
]


def fake_network(name,args,*,session,client=None):
    assert name=="openalex.search_papers"
    assert session.calls<session.max_calls
    session.calls+=1
    result=PAPERS[2:] if "challenge" in args["query"] else PAPERS[:2]
    return {"tool":name,"data":{"papers":result,
        "source_url":"https://api.openalex.org/works"}}


def fake_model(low_score=False,bad_reference=False):
    def call(key,model,system,payload,client=None,max_tokens=0):
        role=payload["role"]
        used={"input_tokens":125,"output_tokens":90}
        if role=="Literature Scout":
            return {"queries":[{"query":"urban graph transfer"},{"query":"graph urban validation"},
                               {"query":"spatial transfer learning"}],"rationale":"Competing scholarly perspectives"},used
        if role=="Paper Analyst":
            return {"assessments":[{"paper_id":p["id"],"priority":"keep",
                "evidence_role":"Empirical research","contribution":"Transfer learning tests",
                "limitations":"Limited external validation","confidence":"medium"}
                for p in payload["papers"]]},used
        if role=="Independent Evidence Critic":
            return {"selected_ids":[p["id"] for p in payload["papers"][:2]],
                "reason":"Independent coverage of evidence and counterclaims",
                "contradictions":["External validity needs testing"]},used
        if role in ("problem","method","data","Scientific Evolver"):
            parent=["H_seed_problem_0"] if role=="Scientific Evolver" else []
            return {"candidates":[{"title":"Cross-city graph transfer",
                 "question":"Can spatial feature graph edges transfer across cities?",
                 "method":"Spatial domain shift ablation",
                 "prediction":"Generalization decreases with edge shift",
                 "experiment":"Leave-one-city-out evaluation",
                 "paper_ids":["madeup-doi" if bad_reference else PAPERS[0]["id"],PAPERS[1]["id"]],
                 "dataset_ids":[],"baselines":["No-graph spatial model"],
                 "parent_ids":parent,"limitations":["Causal mechanism uncertain"]}]},used
        if role in ("Independent Hypothesis Judge","Independent Final Judge"):
            pool=payload.get("candidates") or payload.get("revisions")
            return {"ratings":[{"id":x["id"],
                "score":42 if (low_score and role=="Independent Final Judge") else 91,
                "evidence_ok":True,"feasible":True,"falsifiable":True,
                "prior_art_checked":role=="Independent Final Judge",
                "reason":"Benchmark and cited evidence are specified"} for x in pool]},used
        if role=="Adversarial Prior-Art Challenger":
            return {"target_ids":["H_seed_problem_0"],
                    "objections":["Closest previous paper may already explain mechanism"],
                    "queries":["challenge urban transfer"]},used
        if role=="Independent Counter-evidence Referee":
            return {"paper_ids":[PAPERS[2]["id"]],
                    "prior_art_risk":"manageable",
                    "counterclaims":["The closest existing method lacks an out-of-city benchmark"],
                    "reason":"A possible novelty gap remains to test"},used
        if role=="Research Recommendation Synthesizer":
            return {"selected_ids":["H_revise_0"],
                    "selection_reason":"Evidence-backed, falsifiable hypothesis",
                    "research_path":["Construct held-out city benchmarks",
                                     "Run graph-domain-shift ablations"],
                    "risks":["External replication missing"]},used
        raise AssertionError("Unexpected role "+role)
    return call


@pytest.mark.parametrize("score_low,expected_status",[(False,"review_ready"),(True,"held")])
def test_full_autonomous_pipeline_without_manual_paper_review(tmp_path,monkeypatch,
                                                                score_low,expected_status):
    factory=make_factory(tmp_path,monkeypatch)
    monkeypatch.setattr(runner.REGISTRY,"invoke",fake_network)
    with factory() as db:
        assert readiness(db,"city")["ready"] is True
        run=create_run(db,"city","researcher-one")
        run_id=run.id
    assert runner.execute(factory,run_id,model_call=fake_model(score_low))
    with factory() as db:
        item=db.get(EvolutionRun,run_id)
        assert item.status==expected_status
        assert item.stage=="done"
        assert item.tool_calls>0
        assert item.model_calls>=9
        full=view(item,True)
        assert len(full["papers"])>=2
        assert any(x["stage"]=="challenge" for x in full["versions"])
        assert len(full["paper_assessments"])>=2
        if score_low:
            assert full["recommendation"] is None
            with pytest.raises(ValueError):
                feedback(db,run_id,"human","adopt",{
                    "scientific_value":5,"novelty":5,
                    "feasibility":5,"testability":5})
        else:
            package=full["recommendation"]
            assert package["items"][0]["novelty_verified"] is False
            assert len(package["items"][0]["papers"])>=2
            assert package["items"][0]["parent_ids"]==["H_seed_problem_0"]
            out=feedback(db,run_id,"human","adopt",{
                "scientific_value":5,"novelty":4,"feasibility":4,"testability":5},
                "This is testable")
            assert out["model_weight_training"] is False
            assert sum(x["trials"] for x in policy_report(db))==1
            with pytest.raises(ValueError):
                feedback(db,run_id,"human","adopt",{
                    "scientific_value":5,"novelty":4,"feasibility":4,"testability":5})


def test_fabricated_paper_id_is_rejected_before_recommendation(tmp_path,monkeypatch):
    factory=make_factory(tmp_path,monkeypatch)
    monkeypatch.setattr(runner.REGISTRY,"invoke",fake_network)
    with factory() as db:
        run=create_run(db,"city","researcher-one")
        rid=run.id
    assert not runner.execute(factory,rid,model_call=fake_model(bad_reference=True))
    with factory() as db:
        item=db.get(EvolutionRun,rid)
        assert item.status=="failed"
        assert "真实" in item.error
        assert view(item,True)["recommendation"] is None
        assert len(view(item,True)["paper_assessments"])==2
