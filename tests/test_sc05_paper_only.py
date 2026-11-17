"""Offline end-to-end SC05 tests; no actual model calls, no network."""
import json
from pathlib import Path

import pytest

from backend.sc05_research_diagnosis import EvidenceError
from backend.sc05_paper_only import (
    _chunks, critique, extract_ledger, literature_assessments, method_lineage,
    limit_route_candidates, openalex_search, research_routes, run_paper,
)

PAGES = {
 "page_01": (
  "This paper examines time-dependent movement under simulated disruptions. "
  "The scientific objective is to quantify network vulnerability from actual observations "
  "and distinguish local node capacity from network flow redistribution. "
  "The study builds a station-level mobility assessment and compares disruptions."
 ),
 "page_02": (
  "We collected hourly origin destination counts for the study network. "
  "Observed mobility records represent demand, but actual edge-level routes "
  "are not available from the data provider. We simulate routes using "
  "the minimum generalized travel time and a fixed transfer penalty. "
  "The resulting segment counts are computed estimates rather than direct observations. "
  "The analysis compares pre-event baseline flows with estimated flows during disruption."
 ),
 "page_03": (
  "Our results show that several central corridors experience a marked load shift. "
  "Weighted connectivity is correlated with subsequent simulated index changes. "
  "The evaluation reports correlations at multiple time lags. "
  "Emergency closure simulations show sensitivity to assumed alternative links. "
  "No independent train/test split was reported for forecast accuracy."
 ),
}


PAPER={
 "id":"doi:10.1000/precedent",
 "title":"Transport network stress under stochastic mobility",
 "doi":"10.1000/precedent",
 "url":"https://doi.org/10.1000/precedent",
 "abstract":"We study dynamic disruption responses using agent-based transport routing and compare simulated traffic flows under closures. Independent operational records are not available.",
 "published":"2025-02-01",
 "venue":"Transportation Study",
}


def model_mock(key,model,system,payload,max_tokens=2400):
    assert key=="not-a-real-key"
    assert model=="deepseek-flash"
    stage=payload["sc05_stage"]
    if stage=="evidence_extraction":
        batch = payload["pages"]
        facts=[]
        for page in batch:
            if page["page"]=="page_01":
                facts.append({"page":"page_01","fact_type":"objective",
                     "statement":"The paper assesses network vulnerability and distinguishes node and flow vulnerability",
                     "verbatim_excerpt":"The scientific objective is to quantify network vulnerability from actual observations"})
            if page["page"]=="page_02":
                facts.extend([
                  {"page":"page_02","fact_type":"data",
                   "statement":"Hourly OD demand records were collected",
                   "verbatim_excerpt":"We collected hourly origin destination counts for the study network."},
                  {"page":"page_02","fact_type":"method",
                   "statement":"Routes were assigned with a fixed transfer penalty and minimum cost",
                   "verbatim_excerpt":"We simulate routes using the minimum generalized travel time and a fixed transfer penalty."}
                ])
            if page["page"]=="page_03":
                facts.append({"page":"page_03","fact_type":"evaluation",
                   "statement":"The authors report lag correlations rather than independent predictive validation",
                   "verbatim_excerpt":"The evaluation reports correlations at multiple time lags."})
        return {"facts":facts},{"input_tokens":200,"output_tokens":140}
    if stage=="method_lineage":
        return {"links":[{
            "component":"Flow assignment","fact_ids":["F002","F003"],
            "input":"Hourly observed OD demand",
            "transformation":"Static shortest paths with transfer penalty",
            "output":"Simulated edge flow estimates",
            "measurement_status":"simulated",
            "critical_assumption":"Route choices remain consistent with the fixed cost rule",
            "conclusion_supported":"Network stress patterns, not independently measured edge loads",
        }],"claim_checks":[{
            "claim":"Whether early changes truly forecast failures",
            "fact_ids":["F004"],
            "unverified_link":"No independent operational target",
            "smallest_check":"Use an independent set of observed operations",
        }]},{"input_tokens":120,"output_tokens":140}
    if stage=="diagnosis":
        return {
         "study_reconstruction":{
            "question":"Does observed and simulated transit flow characterize network disruption?",
            "evidence_fact_ids":["F001","F002","F004"],
            "claimed_contribution":"Network resilience assessment",
            "what_is_actually_tested":"Descriptive associations and stylized simulation",
         },
         "diagnoses":[{
            "id":"D01","issue_class":"validation",
            "problem":"Early warning may be confused with correlated derived outcomes",
            "fact_ids":["F004"],"epistemic_status":"hypothesis",
            "rival_explanations":["Correlations may still contain genuine new future information"],
            "verification_tests":["Compare to independent outcome under chronological holdout"],
            "research_consequence":"Forecasting claims require a different outcome",
            "confidence":"medium",
         }],
         "open_questions":["Are independent disruption event logs available?"],
        },{"input_tokens":180,"output_tokens":130}
    if stage=="scientific_value_triage":
        return {"issue_classifications":[{
            "diagnosis_id":"D01","lane":"quality_review",
            "scope_status":"unknown",
            "reason":"The original study asks about diagnostic description, not operational forecasting.",
        }],"scientific_questions":[{
            "id":"Q01","fact_ids":["F001","F002"],
            "related_diagnosis_ids":[],
            "motivating_observation":"The study separates local station load from propagated network stress.",
            "scientific_question":"How do infrastructure systems redistribute demand across interdependent components under disruption?",
            "mechanism_hypothesis":"Flow substitution may produce nonlinear load transfer between subsystems.",
            "scope_change":"From descriptive network indicators to coupled system behavior and intervention decisions.",
            "why_not_just_a_quality_fix":"The question examines feedback and system-level adaptation beyond improved validation.",
            "discriminating_test":"Compare dynamic redistribution and static loading across intervention policies.",
            "narrative_arc":"Localized load -> network adaptation -> new congestion -> system-level intervention tradeoff.",
        }]},{"input_tokens":170,"output_tokens":145}
    if stage=="evidence_questions":
        return {"queries":[{
            "diagnosis_ids":["D01"],"query":"early warning network vulnerability independent labels",
            "need":"validation",
            "assumption_to_test":"Independent outcomes contain information not contained by index construction",
        }]},{"input_tokens":120,"output_tokens":80}
    if stage=="literature_assessment":
        assert payload["papers"][0]["id"]==PAPER["id"]
        assert "diagnosis_links" in payload["required_json_shape"]["assessments"][0]
        assert "unlinked_reason" in payload["required_json_shape"]["assessments"][0]
        return {"assessments":[{
            "paper_id":PAPER["id"],"diagnosis_ids":["D01"],
            "tested_problem":"Response of transport flow to closure",
            "method":"Agent-based routing",
            "relevance":"partial",
            "conditional_transfer":"Route behavior must be validated for the target event",
            "unresolved":"No observed operational labels to validate alerts",
            "abstract_excerpt":"We study dynamic disruption responses using agent-based transport routing",
        }]},{"input_tokens":200,"output_tokens":130}
    if stage=="research_redesign":
        assert payload["literature_assessments"]
        return {"routes":[{
            "id":"R01","frontier_ids":["Q01"],"title":"Dynamic load transfers between infrastructure subsystems",
            "change_kind":"evaluation","diagnosis_ids":["D01"],
            "research_question":"Does traffic-derived stress forecast externally measured shutdowns?",
            "new_mechanism":"Out-of-sample independent operational validation",
            "why_previous_study_cannot_answer":"Reported lag correlations do not independently measure errors",
            "closest_paper_ids":[PAPER["id"]],
            "difference_from_prior_work":"Tests observed events rather than simulated congestion only",
            "feasibility":"Need time-stamped fault observations; otherwise hold",
            "minimal_experiment":"Chronological or leave-event-out train and test; compare persistence and rainfall baselines",
            "negative_result":"No gain versus strong persistence baseline",
            "unknowns":["Operations labels not in supplied article"],
        }]},{"input_tokens":170,"output_tokens":180}
    if stage=="independent_critic":
        return {"reviews":[{
            "route_id":"R01","verdict":"hold",
            "reason":"Independent labels not available from supplied PDF",
            "existing_work_risk":"Another paper already studies dynamic routing",
            "data_blocker":"No station-specific observed failures",
            "minimum_test_revision":"Request only an aggregated event log if available",
        }]},{"input_tokens":90,"output_tokens":100}
    raise AssertionError("Unexpected stage: "+stage)


def search_mock(query,since,limit=7):
    assert "early warning" in query
    assert since=="2020-01-01"
    return [PAPER]


def test_paper_only_full_pipeline_and_audit(monkeypatch,tmp_path):
    import backend.sc05_paper_only as p
    monkeypatch.setattr(p,"page_texts_from_pdf",lambda file:(PAGES,"test-sha-123"))
    report,record=run_paper(tmp_path/"demo.pdf","not-a-real-key",
      model_call=model_mock,search_provider=search_mock,max_calls=8)
    assert record["version"].startswith("sc05-paper-only")
    assert record["source"]["sha256"]=="test-sha-123"
    assert len(record["snapshot"]["observations"])==4
    assert len(record["usage"])==8
    assert [x["stage"] for x in record["usage"]]==[
      "evidence_extraction","method_lineage","diagnosis","scientific_value_triage","evidence_questions",
      "literature_assessment","research_redesign","independent_critic"]
    assert record["diagnosis"]["diagnoses"][0]["epistemic_status"]=="hypothesis"
    assert len(record["literature_assessments"])==1
    assert record["literature_assessments"][0]["diagnosis_link_status"]=="linked"
    assert record["literature_assessments"][0]["relation_types"]==["direct"]
    assert record["reviews"][0]["verdict"]=="hold"
    assert record["scientific_triage"]["issue_classifications"][0]["lane"]=="quality_review"
    assert record["routes"][0]["frontier_ids"]==["Q01"]
    assert "PDF page_02" in report
    assert PAPER["url"] in report
    assert "研究结论与证据之间的缺口" in report
    assert "严谨性审查与新科学问题分流" in report
    assert "否决条件" in report
    assert "test-sha-123" in report
    assert "not-a-real-key" not in report and "not-a-real-key" not in json.dumps(record)



def test_route_candidates_are_capped_and_overflow_is_audited():
    raw={"routes":[{"id":f"R{i:02d}"} for i in range(1,7)]}
    normalized,audit=limit_route_candidates(raw)
    assert [x["id"] for x in normalized["routes"]]==["R01","R02","R03","R04","R05"]
    assert audit["model_returned_route_count"]==6
    assert audit["accepted_route_count"]==5
    assert audit["truncated_route_count"]==1
    with pytest.raises(EvidenceError,match="must be a list"):
        limit_route_candidates({"routes":"not-a-list"})




def test_independent_critic_accepts_empty_route_set_without_reviews():
    assert critique({"reviews":[]},[])==[]
    with pytest.raises(EvidenceError,match="Critic must cover each route"):
        critique({"reviews":[{"route_id":"R01"}]},[])



def test_no_llm_when_key_is_missing(monkeypatch,tmp_path):
    import backend.sc05_paper_only as p
    monkeypatch.setattr(p,"page_texts_from_pdf",lambda file:(PAGES,"hash"))
    with pytest.raises(EvidenceError,match="key unavailable"):
        run_paper(tmp_path/"paper.pdf","",model_call=model_mock,
                  search_provider=search_mock)


def test_fabricated_source_fact_is_blocked():
    def bad_mock(key,model,system,payload,max_tokens=3000):
        return {"facts":[{
            "page":"page_01","fact_type":"result",
            "statement":"The model proves a 99% performance improvement",
            "verbatim_excerpt":"This fabricated number never occurred in the original paper.",
        }]},{"input_tokens":1,"output_tokens":1}
    with pytest.raises(EvidenceError,match="No factual excerpts passed page verification"):
        extract_ledger(PAGES,"fake",bad_mock,[],max_calls=10)


def test_unverified_literature_quote_is_downgraded_not_fabricated():
    diagnosis={"diagnoses":[{"id":"D01"}]}
    raw={"assessments":[{
        "paper_id":PAPER["id"],"diagnosis_ids":["D01"],
        "tested_problem":"Flow","method":"Network simulation",
        "relevance":"close","conditional_transfer":"Same setting needed",
        "unresolved":"Unknown operational response",
        "abstract_excerpt":"This abstract fragment was never published",
    }]}
    parsed=literature_assessments(raw,[PAPER],diagnosis)[0]
    assert parsed["diagnosis_link_status"]=="linked"
    assert parsed["diagnosis_links"][0]["relation_type"]=="direct"
    assert parsed["abstract_quote_status"]=="rejected"
    assert parsed["evidence_status"]=="quote_unverified"
    assert parsed["abstract_excerpt"]==""
    with pytest.raises(EvidenceError,match="unknown/duplicate paper"):
        literature_assessments({"assessments":[{
            **raw["assessments"][0],"paper_id":"doi:10.1000/fabricated"
        }]},[PAPER],diagnosis)
    with pytest.raises(EvidenceError,match="Fabricated reference"):
        method_lineage({"links":[{
            "component":"Fake computation","fact_ids":["F999"],
            "input":"data","transformation":"algorithm","output":"prediction",
            "measurement_status":"observed","critical_assumption":"x",
            "conclusion_supported":"y",
        }],"claim_checks":[]},[{"fact_id":"F001"}])


def test_literature_can_link_different_diagnoses_with_different_relation_types():
    diagnosis={"diagnoses":[{"id":"D01"},{"id":"D02"},{"id":"D03"}]}
    raw={"assessments":[{
        "paper_id":PAPER["id"],
        "diagnosis_links":[
            {"diagnosis_id":"D01","relation_type":"direct",
             "relation_explanation":"It studies the same network stress outcome."},
            {"diagnosis_id":"D02","relation_type":"indirect",
             "relation_explanation":"The transfer mechanism links local route substitution to system-level load redistribution."},
            {"diagnosis_id":"D03","relation_type":"counterexample",
             "relation_explanation":"Its independent event records contradict the assumption that no external validation is possible."},
        ],
        "tested_problem":"Flow","method":"Network simulation",
        "relevance":"partial","conditional_transfer":"Comparable network structure is required",
        "unresolved":"Transfer to other transport systems remains unknown",
        "abstract_excerpt":"We study dynamic disruption responses using agent-based transport routing",
    }]}
    parsed=literature_assessments(raw,[PAPER],diagnosis)[0]
    assert parsed["diagnosis_ids"]==["D01","D02","D03"]
    assert parsed["relation_types"]==["direct","indirect","counterexample"]
    assert parsed["diagnosis_link_status"]=="linked"
    assert parsed["evidence_status"]=="abstract_quote_verified"


def test_missing_diagnosis_links_are_explicitly_unlinked():
    diagnosis={"diagnoses":[{"id":"D01"}]}
    raw={"assessments":[{
        "paper_id":PAPER["id"],"diagnosis_links":[],
        "unlinked_reason":"The abstract concerns a different outcome and no mechanism bridge is supported.",
        "tested_problem":"A different topic","method":"Survey",
        "relevance":"low","conditional_transfer":"No justified transfer",
        "unresolved":"No relation to the current diagnosis can be established",
        "abstract_excerpt":"We study dynamic disruption responses using agent-based transport routing",
    }]}
    parsed=literature_assessments(raw,[PAPER],diagnosis)[0]
    assert parsed["diagnosis_link_status"]=="unlinked"
    assert parsed["diagnosis_ids"]==[]
    assert parsed["unlinked_reason"].startswith("The abstract concerns")


def test_unsafe_cost_budget_is_refused_before_calls(monkeypatch,tmp_path):
    import backend.sc05_paper_only as p
    monkeypatch.setattr(p,"page_texts_from_pdf",lambda file:(PAGES,"hash"))
    with pytest.raises(EvidenceError,match="maximum authorized"):
        run_paper(tmp_path/"paper.pdf","not-a-real-key",
                  model_call=model_mock,search_provider=search_mock,max_calls=7)


def test_pdf_holdout_discussion_and_references(monkeypatch,tmp_path):
    fitz=pytest.importorskip("fitz")
    import backend.sc05_paper_only as p
    path=tmp_path/"paper.pdf"
    d=fitz.open()
    first=d.new_page();first.insert_text((50,70),
          "Research question and methods. Data were collected using hourly origin counts. "+
          "Results show differences between networks.",fontsize=9)
    second=d.new_page()
    second.insert_text((50,70),
          "6.1. Conclusion\nThe observed changes are larger than routine variability.\n"
          "6.2. Discussion\nFuture work should use the exact answer blueprint.",
          fontsize=9)
    d.save(path);d.close()
    pages,sha=p.page_texts_from_pdf(path)
    assert pages["page_01"]
    assert "Conclusion" in pages["page_02"]
    assert "exact answer blueprint" not in str(pages)
    assert len(sha)==64

def test_whitespace_only_pdf_quote_normalization_is_traced_to_literal_source():
    from backend.sc05_paper_only import _verified_excerpt
    source="We observe that the model uses a data-driven\n route allocation.\nAny other result is unverified."
    matched=_verified_excerpt(source,"model uses a data-driven route allocation.")
    assert matched=="model uses a data-driven\n route allocation."
    with pytest.raises(EvidenceError,match="source fragment"):
        _verified_excerpt(source,"the model guarantees no failures")

def test_quality_only_route_is_rejected():
    from backend.sc05_science_gate import enforce_route_frontiers, validate_scientific_triage
    from backend.sc05_paper_only import research_routes
    diagnoses=[{"id":"D01"}]
    facts=[{"fact_id":"F001"}]
    triage=validate_scientific_triage({
      "issue_classifications":[{
        "diagnosis_id":"D01","lane":"quality_review",
        "scope_status":"acknowledged",
        "reason":"This is a sensitivity review, not a scientific finding.",
      }],"scientific_questions":[]
    },diagnoses,facts)
    raw={"routes":[{
        "frontier_ids":[],"title":"Add more sensitivity analysis",
        "change_kind":"evaluation","diagnosis_ids":["D01"],
    }]}
    with pytest.raises(EvidenceError,match="quality-only"):
        research_routes(raw,{"diagnoses":diagnoses},[],triage)



def test_unknown_paper_scope_label_is_preserved_and_conservatively_normalized():
    from backend.sc05_science_gate import validate_scientific_triage
    result=validate_scientific_triage({
      "issue_classifications":[{
        "diagnosis_id":"D01","lane":"scientific_frontier",
        "scope_status":"not_explicitly_addressed",
        "reason":"The model used unfamiliar wording for the scope status.",
      }],"scientific_questions":[]
    },[{"id":"D01"}],[])
    row=result["issue_classifications"][0]
    assert row["scope_status"]=="unknown"
    assert row["raw_scope_status"]=="not_explicitly_addressed"
    assert row["scope_status_normalized"] is True



def test_scientific_question_must_cite_real_paper_and_distinct_story():
    from backend.sc05_science_gate import validate_scientific_triage
    with pytest.raises(EvidenceError,match="Invented"):
        validate_scientific_triage({
            "issue_classifications":[],
            "scientific_questions":[{
                "id":"Q01","fact_ids":["F999"],"related_diagnosis_ids":[],
                "motivating_observation":"Observed effect",
                "scientific_question":"New question",
                "mechanism_hypothesis":"Competing process",
                "scope_change":"Cross system",
                "why_not_just_a_quality_fix":"New mechanism, not a test",
                "discriminating_test":"Compare two processes",
                "narrative_arc":"Observation to contradiction to explanation",
            }],
        },[],[{"fact_id":"F001"}])

def test_unexpected_model_fact_label_preserves_verified_quote_and_records_alias():
    from backend.sc05_paper_only import extract_ledger, normalize_fact_kind
    page={"page_01":PAGES["page_01"]}
    assert normalize_fact_kind("finding")[0]=="result"
    assert normalize_fact_kind("research_question")[0]=="objective"
    assert normalize_fact_kind("unexpected_new_science_category")[0]=="other"
    quote="The scientific objective is to quantify network vulnerability from actual observations"
    def cached_model(key,model,system,payload,max_tokens=2700):
        assert payload["sc05_stage"]=="evidence_extraction"
        return {"facts":[{"page":"page_01",
                "fact_type":"unexpected_new_science_category",
                "statement":"This paper assesses network vulnerability",
                "verbatim_excerpt":quote}]},{"input_tokens":1013,"output_tokens":372}
    log=[]
    result=extract_ledger(page,"dummy-key",cached_model,log,max_calls=8)
    obs=result["snapshot"]["observations"][0]
    assert obs["fact_type"]=="other"
    assert obs["verbatim_excerpt"]==quote
    assert result["source_note"][0]["raw_type"]=="unexpected_new_science_category"
    assert result["source_note"][0]["normalized_type"]=="other"
    assert len(log)==1


def test_unclassified_model_label_still_cannot_fabricate_quotation():
    from backend.sc05_paper_only import extract_ledger
    def cached_model(key,model,system,payload,max_tokens=2700):
        return {"facts":[{"page":"page_01","fact_type":"some-new-type",
                          "statement":"Claim",
                          "verbatim_excerpt":"A fictitious experimental improvement of 900%"}]},{}
    with pytest.raises(EvidenceError,match="No factual excerpts passed page verification"):
        extract_ledger({"page_01":PAGES["page_01"]},"dummy-key",
                       cached_model,[],max_calls=8)


def test_mixed_extraction_drops_non_source_quote_but_retains_verified_fact():
    """A hallucinated quote is quarantined without discarding independently verified evidence."""
    from backend.sc05_paper_only import extract_ledger
    valid="The scientific objective is to quantify network vulnerability from actual observations"
    calls=[]
    def cached_response(key,model,system,payload,max_tokens=2700):
        calls.append(payload["sc05_stage"])
        return {"facts":[
            {"page":"page_01","fact_type":"objective",
             "statement":"Assesses vulnerability","verbatim_excerpt":valid},
            {"page":"page_01","fact_type":"result",
             "statement":"A fictional result","verbatim_excerpt":"The metro teleported all trains."},
        ]},{"input_tokens":100,"output_tokens":50}
    result=extract_ledger({"page_01":PAGES["page_01"]},"cached",cached_response,[],max_calls=8)
    assert len(calls)==1
    assert len(result["snapshot"]["observations"])==1
    assert result["snapshot"]["observations"][0]["verbatim_excerpt"]==valid
    assert any(x.get("rule")=="unverified_source_quote_rejected" for x in result["source_note"])


def test_search_plan_caps_excess_queries_in_model_priority_order():
    from backend.sc05_paper_only import search_plan
    diagnoses=[{"id":"D01"}]
    raw={"queries":[
      {"diagnosis_ids":["D01"],"query":f"query {i}","need":"validation"}
      for i in range(9)
    ]}
    result=search_plan(raw,diagnoses)
    assert len(result)==7
    assert [x["query"] for x in result]==[f"query {i}" for i in range(7)]


def test_search_plan_preserves_valid_queries_and_omits_unknown_needs():
    from backend.sc05_paper_only import search_plan
    diagnostics=[{"id":"D01"}]
    raw={"queries":[
       {"diagnosis_ids":["D01"],"query":"prior method comparison",
        "need":"methodology","assumption_to_test":"Compare techniques"},
       {"diagnosis_ids":["D01"],"query":"unclassified literature",
        "need":"general_background","assumption_to_test":"No ungrounded classification"},
       {"diagnosis_ids":["D01"],"query":"independent observational tests",
        "need":"empirical_validation","assumption_to_test":"Independent outcome"},
    ]}
    result=search_plan(raw,diagnostics)
    assert len(result)==2
    assert [x["need"] for x in result]==["method","validation"]
    assert [x["query"] for x in result]==[
        "prior method comparison","independent observational tests"]
