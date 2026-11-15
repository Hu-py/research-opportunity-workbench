"""Scientific-value gate separates study-quality review from next-paper discovery.

Study-scoped assumptions and missing tests are not automatically scientific
shortcomings. New research questions can emerge from a paper's *positive*
findings even if all its original experiments were rigorous for their goals.
"""
from __future__ import annotations

import re
from typing import Any

from backend.sc05_research_diagnosis import EvidenceError

FRONTIER_SCHEMA = {
    "issue_classifications": [{
        "diagnosis_id": "D01",
        "lane": "quality_review|scientific_frontier|both",
        "scope_status": "acknowledged|not_reported|unknown",
        "reason": "Why this is or is not a new scientific question, not a verdict on the paper's rigor",
    }],
    "scientific_questions": [{
        "id": "Q01",
        "fact_ids": ["F001"],
        "related_diagnosis_ids": [],
        "motivating_observation": "What the original study actually discovered",
        "scientific_question": "Unanswered relationship, mechanism or system law",
        "mechanism_hypothesis": "What could cause the new phenomenon",
        "scope_change": "New scale, interacting system, decision process or theoretical condition",
        "why_not_just_a_quality_fix": "How this goes beyond adding an ablation or more validation",
        "discriminating_test": "A test distinguishing meaningful competing mechanisms",
        "narrative_arc": "Observed phenomenon -> new tension -> unknown mechanism -> consequence",
    }],
}


def _text(x: Any, label: str, max_len: int = 1800) -> str:
    if not isinstance(x,str) or not x.strip() or len(x)>max_len:
        raise EvidenceError("Invalid scientific triage field: "+label)
    return x.strip()


def _ids(x: Any, valid: set[str], label: str, *, may_be_empty: bool = False) -> list[str]:
    if not isinstance(x,list) or (not x and not may_be_empty) or not all(isinstance(z,str) for z in x):
        raise EvidenceError("Invalid scientific triage references: "+label)
    if not set(x)<=valid:
        raise EvidenceError("Invented scientific triage reference: "+label)
    return list(dict.fromkeys(x))


def validate_scientific_triage(
    raw: dict[str, Any], diagnoses: list[dict], facts: list[dict]
) -> dict[str, Any]:
    """Validate IDs and require substantive scientific narrative for all frontiers."""
    if not isinstance(raw,dict):
        raise EvidenceError("Scientific triage is not a JSON object")
    d_ids={d["id"] for d in diagnoses}
    f_ids={f["fact_id"] for f in facts}
    classifications=raw.get("issue_classifications")
    questions=raw.get("scientific_questions")
    if not isinstance(classifications,list) or len(classifications)!=len(diagnoses):
        raise EvidenceError("Every diagnosis must be classified into a lane")
    if not isinstance(questions,list) or len(questions)>5:
        raise EvidenceError("Expected 0-5 scientific frontiers")
    seen=set();classified=[]
    for row in classifications:
        if not isinstance(row,dict):
            raise EvidenceError("Invalid scientific lane")
        did=row.get("diagnosis_id")
        if did not in d_ids or did in seen:
            raise EvidenceError("Missing or repeated diagnostic lane")
        seen.add(did)
        if row.get("lane") not in {"quality_review","scientific_frontier","both"}:
            raise EvidenceError("Invalid scientific lane")
        if row.get("scope_status") not in {"acknowledged","not_reported","unknown"}:
            raise EvidenceError("Invalid paper scope status")
        classified.append({
            "diagnosis_id":did,
            "lane":row["lane"],
            "scope_status":row["scope_status"],
            "reason":_text(row.get("reason"),"lane reasoning"),
        })
    question_rows=[];qids=set()
    for row in questions:
        if not isinstance(row,dict):
            raise EvidenceError("Invalid scientific question")
        qid=row.get("id")
        if not isinstance(qid,str) or not re.fullmatch(r"Q[0-9]{2,3}",qid) or qid in qids:
            raise EvidenceError("Invalid or duplicate frontier ID")
        qids.add(qid)
        question_rows.append({
            "id":qid,
            "fact_ids":_ids(row.get("fact_ids"),f_ids,"frontier facts"),
            "related_diagnosis_ids":_ids(
                row.get("related_diagnosis_ids"),d_ids,"frontier diagnoses",may_be_empty=True),
            **{k:_text(row.get(k),k) for k in (
                "motivating_observation","scientific_question","mechanism_hypothesis",
                "scope_change","why_not_just_a_quality_fix",
                "discriminating_test","narrative_arc")},
        })
    return {"issue_classifications":classified, "scientific_questions":question_rows}


def enforce_route_frontiers(
    raw: dict[str, Any], validated: dict[str, Any],
) -> dict[str, Any]:
    """Require each promoted candidate to address a named scientific question.

    Does not judge novelty from model prose; that still requires prior art.
    """
    fids={f["id"] for f in validated["scientific_questions"]}
    rows=raw.get("routes")
    if not isinstance(rows,list):
        raise EvidenceError("Routes must be a list")
    if rows and not fids:
        raise EvidenceError("A quality-only correction cannot be promoted to a next paper")
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get("frontier_ids"),list):
            raise EvidenceError("Routes must cite an independent scientific question")
        if not row["frontier_ids"] or not set(row["frontier_ids"])<=fids:
            raise EvidenceError("Route references no valid scientific frontier")
    return raw
