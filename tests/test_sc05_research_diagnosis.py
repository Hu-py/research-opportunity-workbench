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




def test_inferred_epistemic_status_is_conservatively_normalized_and_preserved():
    raw=valid_response()
    raw["diagnoses"][0]["epistemic_status"]="inferred"
    result=validate_diagnosis(raw,snapshot())
    issue=result["diagnoses"][0]
    assert issue["epistemic_status"]=="hypothesis"
    assert issue["raw_epistemic_status"]=="inferred"
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
