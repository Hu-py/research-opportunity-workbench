"""Offline end-to-end SC05 tests; no actual model calls, no network."""
import json
from pathlib import Path

import pytest

from backend.sc05_research_diagnosis import EvidenceError
from backend.sc05_paper_only import (
    _chunks, critique, extract_ledger, literature_assessments, method_lineage,
    openalex_search, research_routes, run_paper,
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
    if stage=="evidence_questions":
        return {"queries":[{
            "diagnosis_ids":["D01"],"query":"early warning network vulnerability independent labels",
            "need":"validation",
            "assumption_to_test":"Independent outcomes contain information not contained by index construction",
        }]},{"input_tokens":120,"output_tokens":80}
    if stage=="literature_assessment":
        assert payload["papers"][0]["id"]==PAPER["id"]
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
            "id":"R01","title":"Validate failure warning against independent operations",
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
      model_call=model_mock,search_provider=search_mock,max_calls=7)
    assert record["version"].startswith("sc05-paper-only")
    assert record["source"]["sha256"]=="test-sha-123"
    assert len(record["snapshot"]["observations"])==4
    assert len(record["usage"])==7
    assert [x["stage"] for x in record["usage"]]==[
      "evidence_extraction","method_lineage","diagnosis","evidence_questions",
      "literature_assessment","research_redesign","independent_critic"]
    assert record["diagnosis"]["diagnoses"][0]["epistemic_status"]=="hypothesis"
    assert len(record["literature_assessments"])==1
    assert record["reviews"][0]["verdict"]=="hold"
    assert "PDF page_02" in report
    assert PAPER["url"] in report
    assert "研究结论与证据之间的缺口" in report
    assert "否决条件" in report
    assert "test-sha-123" in report
    assert "not-a-real-key" not in report and "not-a-real-key" not in json.dumps(record)


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
    with pytest.raises(EvidenceError,match="unverified"):
        extract_ledger(PAGES,"fake",bad_mock,[],max_calls=10)


def test_fake_literature_or_source_citation_is_blocked():
    diagnosis={"diagnoses":[{"id":"D01"}]}
    raw={"assessments":[{
        "paper_id":PAPER["id"],"diagnosis_ids":["D01"],
        "tested_problem":"Flow","method":"Network simulation",
        "relevance":"close","conditional_transfer":"Same setting needed",
        "unresolved":"Unknown operational response",
        "abstract_excerpt":"This abstract fragment was never published",
    }]}
    with pytest.raises(EvidenceError,match="does not match"):
        literature_assessments(raw,[PAPER],diagnosis)
    with pytest.raises(EvidenceError,match="Fabricated reference"):
        method_lineage({"links":[{
            "component":"Fake computation","fact_ids":["F999"],
            "input":"data","transformation":"algorithm","output":"prediction",
            "measurement_status":"observed","critical_assumption":"x",
            "conclusion_supported":"y",
        }],"claim_checks":[]},[{"fact_id":"F001"}])


def test_unsafe_cost_budget_is_refused_before_calls(monkeypatch,tmp_path):
    import backend.sc05_paper_only as p
    monkeypatch.setattr(p,"page_texts_from_pdf",lambda file:(PAGES,"hash"))
    with pytest.raises(EvidenceError,match="maximum authorized"):
        run_paper(tmp_path/"paper.pdf","not-a-real-key",
                  model_call=model_mock,search_provider=search_mock,max_calls=6)


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
