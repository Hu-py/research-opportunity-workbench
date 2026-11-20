"""R7.2.2: malformed narrative cannot invalidate already-paid paper evidence."""
from backend.sc05_paper_only import literature_assessments
from backend.sc05_research_diagnosis import EvidenceError
from backend.sc05_quality import inspect_report
import pytest


def paper():
    return [{
        "id":"doi:10.1000/verified",
        "title":"Urban rail resilience paper",
        "abstract":"Observed passenger path adaptation changes the network response under disruptions",
        "venue":"Transportation Research Part C",
    }]


def assessment():
    return {
        "paper_id":"doi:10.1000/verified",
        "diagnosis_links":[{"diagnosis_id":"D01","relation_type":"counterexample",
                            "relation_explanation":"The paper tests network disruption behavior with observed paths"}],
        "tested_problem":"Rail network response to disruptions",
        "method":"Observational mobility reconstruction",
        "relevance":"close",
        "conditional_transfer":"Comparable traveler behavior is necessary",
        "unresolved":"Unknown impact on planning interventions",
        "abstract_excerpt":"Observed passenger path adaptation changes the network response under disruptions",
    }


def test_one_missing_optional_scope_does_not_discard_verified_literature():
    raw=assessment()
    raw["unresolved"]=None
    rows=literature_assessments({"assessments":[raw]},paper(),{"diagnoses":[{"id":"D01"}]})
    assert len(rows)==1
    assert rows[0]["evidence_status"]=="abstract_quote_verified"
    assert rows[0]["diagnosis_link_status"]=="linked"
    assert rows[0]["invalid_scope_fields"]==["unresolved"]
    assert "未核实" in rows[0]["unresolved"] or "不足" in rows[0]["unresolved"]


def test_oversized_scope_is_not_silently_truncated_as_fact():
    raw=assessment()
    raw["unresolved"]="unverified "*500
    rows=literature_assessments({"assessments":[raw]},paper(),{"diagnoses":[{"id":"D01"}]})
    assert rows[0]["invalid_scope_fields"]==["unresolved"]
    assert "unverified "*500 not in rows[0]["unresolved"]


def test_invalid_paper_id_still_fails_closed():
    raw=assessment()
    raw["paper_id"]="doi:10.1000/hallucinated"
    raw["unresolved"]=None
    with pytest.raises(EvidenceError,match="unknown/duplicate paper"):
        literature_assessments({"assessments":[raw]},paper(),{"diagnoses":[{"id":"D01"}]})


def test_invalid_diagnosis_link_still_fails_closed():
    raw=assessment()
    raw["diagnosis_links"][0]["diagnosis_id"]="D99"
    raw["unresolved"]=None
    with pytest.raises(EvidenceError,match="Fabricated reference"):
        literature_assessments({"assessments":[raw]},paper(),{"diagnoses":[{"id":"D01"}]})


def test_unverified_quote_never_promoted_by_scope_repair():
    raw=assessment()
    raw["abstract_excerpt"]="A fabricated excerpt never present in the abstract"
    raw["unresolved"]=None
    rows=literature_assessments({"assessments":[raw]},paper(),{"diagnoses":[{"id":"D01"}]})
    assert rows[0]["evidence_status"]=="quote_unverified"
    assert rows[0]["abstract_excerpt"]==""


def test_quality_flag_marks_missing_scope_without_certifying_novelty():
    row=literature_assessments(
        {"assessments":[{**assessment(),"unresolved":None}]},
        paper(),{"diagnoses":[{"id":"D01"}]})[0]
    out=inspect_report({
        "snapshot":{"observations":[{"fact_id":"F001","fact_type":"objective","section":"page_01",
                                      "verbatim_excerpt":"A verified research paper statement."},
                                     {"fact_id":"F002","fact_type":"data","section":"page_01",
                                      "verbatim_excerpt":"A verified data source is present."},
                                     {"fact_id":"F003","fact_type":"method","section":"page_01",
                                      "verbatim_excerpt":"The described model uses path selection."},
                                     {"fact_id":"F004","fact_type":"result","section":"page_01",
                                      "verbatim_excerpt":"The model reports a network disruption change."}]},
        "diagnosis":{"diagnoses":[{"id":"D01","fact_ids":["F001"],
                                   "rival_explanations":["A","B"],
                                   "verification_tests":["Compare results"]}]},
        "method_lineage":{"links":[{"measurement_status":"derived"},{"measurement_status":"observed"}]},
        "literature_assessments":[row],
        "external_papers":paper(),
        "routes":[],"reviews":[],
    })
    assert out["invalid_literature_scope_fields"]==1
    assert out["scientific_quality_certified"] is False
    assert any("模型文献描述字段无效" in x for x in out["warnings"])
