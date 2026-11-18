"""SC05 is tested on an unrelated neutral study, never on the expected answer."""
import copy
import pytest

from backend.sc05_research_diagnosis import (
    EvidenceError, freeze_blind_input, model_payload, validate_diagnosis,
)

DOC = {
    "anonymous-study-v1": {
        "Introduction": "This study examines predictions in multiple sampling windows with a shared set of measurements.",
        "Methods": "We collected eight observation batches under the same protocol and evaluated predictions with a random split.",
        "Results": "Prediction errors varied substantially across test windows and across the independent measurement devices.",
        "Discussion": "Future studies should use a new continental dataset and a new network architecture.",
    }
}
FACTS = [
    {"fact_id": "F001", "fact_type": "objective",
     "statement": "Prediction from repeated measurements is the stated goal.",
     "source_id": "anonymous-study-v1", "section": "Introduction",
     "verbatim_excerpt": "This study examines predictions in multiple sampling windows",
     "evidence_origin": "author_reported"},
    {"fact_id": "F002", "fact_type": "evaluation",
     "statement": "The authors used a random holdout.",
     "source_id": "anonymous-study-v1", "section": "Methods",
     "verbatim_excerpt": "evaluated predictions with a random split.",
     "evidence_origin": "author_reported"},
    {"fact_id": "F003", "fact_type": "result",
     "statement": "Reported error depends on windows and devices.",
     "source_id": "anonymous-study-v1", "section": "Results",
     "verbatim_excerpt": "Prediction errors varied substantially across test windows",
     "evidence_origin": "author_reported"},
]


def snapshot():
    return freeze_blind_input(
        DOC, research_question="Can the study predict repeated measurement outcomes?",
        study_unit="Observation window",
        facts=copy.deepcopy(FACTS),
        unknowns=["Whether device-specific errors are systematic"],
    )


def valid_response():
    return {
        "study_reconstruction": {
            "question": "How does the method predict repeated measurements?",
            "evidence_fact_ids": ["F001", "F002"],
            "claimed_contribution": "The study investigates a predictive method",
            "what_is_actually_tested": "Randomly split observations",
        },
        "diagnoses": [
            {
                "id": "D01", "issue_class": "validation",
                "problem": "Random holdout may not independently test windows",
                "fact_ids": ["F002", "F003"],
                "epistemic_status": "hypothesis",
                "rival_explanations": [
                    "Temporal differences rather than correlated split records",
                ],
                "verification_tests": [
                    "Compare blocked-window holdout and random holdout",
                ],
                "research_consequence": "The validation design may need revision",
                "confidence": "medium",
            }
        ],
        "open_questions": ["Were test devices used in training?"],
    }


def test_neutral_facts_are_anchored_to_actual_source():
    result = snapshot()
    assert result["snapshot_sha256"]
    assert len(result["observations"]) == 3
    assert result["observations"][1]["section"] == "Methods"


def test_blind_model_input_never_contains_evaluator_answer_or_future_plan():
    result = snapshot()
    prompt = str(model_payload(result))
    assert "continental dataset" not in prompt
    result["evaluator_holdout"] = "Use continental dataset as next study"
    with pytest.raises(EvidenceError, match="Modified"):
        model_payload(result)
    assert "new network architecture" not in prompt
    assert "D01" in prompt  # only an example JSON shape, not expected finding


def test_input_fails_when_quote_is_fake_or_section_is_missing():
    edited = copy.deepcopy(FACTS)
    edited[0]["verbatim_excerpt"] = "An entirely fabricated result from this source"
    with pytest.raises(EvidenceError, match="Unverifiable"):
        freeze_blind_input(
            DOC, research_question="Test predictions",
            study_unit="Observation window", facts=edited,
        )
    edited = copy.deepcopy(FACTS)
    edited[0]["section"] = "No such section"
    with pytest.raises(EvidenceError, match="Unverifiable"):
        freeze_blind_input(
            DOC, research_question="Test predictions",
            study_unit="Observation window", facts=edited,
        )


def test_diagnosis_validates_refs_hypotheses_and_preserves_uncertainty():
    data = validate_diagnosis(valid_response(), snapshot())
    assert len(data["diagnoses"]) == 1
    assert data["diagnoses"][0]["epistemic_status"] == "hypothesis"
    assert data["novelty_verified"] is False
    assert data["experimental_evaluation_executed"] is False


def test_invented_reference_and_unsupported_hypothesis_rejected():
    raw = valid_response()
    raw["diagnoses"][0]["fact_ids"] = ["F999"]
    with pytest.raises(EvidenceError, match="Invented"):
        validate_diagnosis(raw, snapshot())
    raw = valid_response()
    raw["diagnoses"][0]["verification_tests"] = []
    with pytest.raises(EvidenceError, match="Untested mechanism"):
        validate_diagnosis(raw, snapshot())


def test_no_forced_diagnoses_and_no_fictitious_results():
    raw = valid_response()
    raw["diagnoses"] = []
    result = validate_diagnosis(raw, snapshot())
    assert result["diagnoses"] == []
    modified = snapshot()
    modified["research_question"] = "I am replacing the facts after freezing"
    with pytest.raises(EvidenceError, match="Modified"):
        model_payload(modified)


def test_model_omitted_confidence_is_not_invented_and_inference_is_preserved():
    raw = valid_response()
    row = raw["diagnoses"][0]
    row.pop("confidence")
    row["issue_class"] = "inference"
    data = validate_diagnosis(raw, snapshot())
    issue = data["diagnoses"][0]
    assert issue["issue_class"] == "inference"
    assert issue["confidence"] == "not_assessed"
    assert issue["confidence_provenance"] == "not_provided"



def test_optional_open_questions_accept_single_string_without_inventing_content():
    raw=valid_response()
    raw.pop("open_questions")
    result=validate_diagnosis(raw,snapshot())
    assert result["open_questions"]==[]
    raw=valid_response()
    raw["open_questions"]="One concise unresolved question?"
    result=validate_diagnosis(raw,snapshot())
    assert result["open_questions"]==["One concise unresolved question?"]
    raw=valid_response()
    raw["open_questions"]={"unexpected":"object"}
    with pytest.raises(EvidenceError,match="Expected list open_questions"):
        validate_diagnosis(raw,snapshot())




def test_inferred_and_unknown_fact_epistemic_statuses_are_normalized_and_preserved():
    for raw_status,expected in [("inferred","hypothesis"),("unknown_fact","unknown")]:
        raw=valid_response()
        raw["diagnoses"][0]["epistemic_status"]=raw_status
        result=validate_diagnosis(raw,snapshot())
        issue=result["diagnoses"][0]
        assert issue["epistemic_status"]==expected
        assert issue["raw_epistemic_status"]==raw_status
        assert issue["epistemic_status_normalized"] is True



def test_model_reported_confidence_provenance_is_explicit():
    result = validate_diagnosis(valid_response(), snapshot())
    assert result["diagnoses"][0]["confidence"] == "medium"
    assert result["diagnoses"][0]["confidence_provenance"] == "model_reported"


@pytest.mark.parametrize(("raw_label","canonical"),[
    ("causal_inference","identifiability"),
    ("inference_boundary","identifiability"),
    ("method_dependence","method"),
    ("confounding","identifiability"),
    ("identification","identifiability"),
    ("data","other"),
    ("design","method"),
    ("research_design","method"),
    ("experimental_design","method"),
])
def test_gated_diagnosis_taxonomy_aliases_preserve_raw_labels(raw_label,canonical):
    raw=valid_response()
    raw["diagnoses"][0]["issue_class"]=raw_label
    result=validate_diagnosis(raw,snapshot())
    issue=result["diagnoses"][0]
    assert issue["issue_class"]==canonical
    assert issue["raw_issue_class"]==raw_label
    assert issue["issue_class_normalized"] is True


def test_novel_epistemic_label_downgrades_to_unknown_without_claiming_observation():
    raw=valid_response()
    issue=raw["diagnoses"][0]
    issue["issue_class"]="validation"
    issue["epistemic_status"]="reported_claim_with_unverified_causal_link"
    issue["confidence"]="not_assessed"
    parsed=validate_diagnosis(raw,snapshot())["diagnoses"][0]
    assert parsed["epistemic_status"]=="unknown"
    assert parsed["raw_epistemic_status"]=="reported_claim_with_unverified_causal_link"
    assert parsed["epistemic_status_unrecognized"] is True
    assert parsed["epistemic_status_normalized"] is True
    assert parsed["issue_class"]=="validation"
    assert parsed["confidence"]=="not_assessed"
    assert parsed["fact_ids"]==issue["fact_ids"]
    assert parsed["rival_explanations"]==issue["rival_explanations"]
    assert parsed["verification_tests"]==issue["verification_tests"]


def test_unknown_taxonomy_and_confidence_never_invent_classification_or_certainty():
    raw=valid_response()
    issue=raw["diagnoses"][0]
    issue["issue_class"]="unreviewed_new_category"
    issue["epistemic_status"]={"unexpected":"object"}
    issue["confidence"]="95_percent_unverified"
    parsed=validate_diagnosis(raw,snapshot())["diagnoses"][0]
    assert parsed["issue_class"]=="other"
    assert parsed["issue_class_unrecognized"] is True
    assert parsed["epistemic_status"]=="unknown"
    assert parsed["epistemic_status_unrecognized"] is True
    assert parsed["confidence"]=="not_assessed"
    assert parsed["raw_confidence"]=="95_percent_unverified"
    assert parsed["confidence_label_unrecognized"] is True
    assert parsed["confidence_provenance"]=="model_label_unrecognized"


def test_taxonomy_downgrade_does_not_weaken_source_fact_id_validation():
    raw=valid_response()
    issue=raw["diagnoses"][0]
    issue["epistemic_status"]="reported_claim_with_unverified_causal_link"
    issue["fact_ids"]=["F999"]
    with pytest.raises(EvidenceError,match="Invented diagnosis fact reference"):
        validate_diagnosis(raw,snapshot())


def test_quality_flags_unknown_diagnosis_classifications():
    from backend.sc05_quality import inspect_report
    diag=validate_diagnosis({
        **valid_response(),
        "diagnoses":[{
            **valid_response()["diagnoses"][0],
            "epistemic_status":"reported_claim_with_unverified_causal_link"
        }],
    },snapshot())
    metrics=inspect_report({
        "snapshot":snapshot(),
        "diagnosis":diag,"method_lineage":{"links":[]},
        "external_papers":[],"literature_assessments":[],
        "routes":[],"reviews":[],
    })
    assert metrics["unknown_model_epistemic_statuses"]==1
    assert any("unknown" in item for item in metrics["warnings"])
    assert metrics["scientific_quality_certified"] is False
