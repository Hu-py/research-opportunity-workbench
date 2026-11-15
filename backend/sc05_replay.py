"""Zero-paid-call integrity review of an already-recorded SC05 diagnosis prefix.

Re-runs deterministic parsing and strict SHA256 checks against all *stored*
LLM responses. It must stop exactly before the first not-yet-recorded stage.
Never imports or calls a live provider.
"""
from __future__ import annotations

import hashlib

from backend.sc05_eval_api import SC05Case, SC05Run, dump, load
from backend.sc05_paper_only import run_paper
from backend.sc05_research_diagnosis import EvidenceError


class PrefixBoundaryReached(Exception):
    """The saved exact-input LLM prefix has been exhausted."""


def verify_diagnosis_prefix(run: SC05Run, source: SC05Case) -> dict:
    if run.status != "failed" or run.error != "Invalid diagnosis classification":
        raise EvidenceError("Not the eligible saved diagnosis classification failure")
    if run.variant != "science_gate_off":
        raise EvidenceError("Only the baseline evidence reconstruction is eligible")
    entries = load(run.checkpoints_json, [])
    if (not isinstance(entries, list) or len(entries) != run.calls
        or len(entries) < 3 or entries[-1].get("stage") != "diagnosis"):
        raise EvidenceError("Saved checkpoint prefix is incomplete or reordered")
    if any(not isinstance(e, dict) or
           not isinstance(e.get("response"), dict) or
           not isinstance(e.get("usage"), dict)
           for e in entries):
        raise EvidenceError("Stored checkpoint entries are invalid")
    cursor = [0]
    next_stage = [""]
    def cached_only(api_key, model, system, payload, max_tokens=3000):
        fingerprint = hashlib.sha256(dump({
            "model": model, "system": system,
            "payload": payload, "max_tokens": max_tokens
        }).encode()).hexdigest()
        if cursor[0] >= len(entries):
            next_stage[0] = str(payload.get("sc05_stage", ""))
            raise PrefixBoundaryReached()
        current = entries[cursor[0]]
        if (current.get("prompt_sha256") != fingerprint or
            current.get("stage") != payload.get("sc05_stage") or
            current.get("model") != model):
            raise EvidenceError("Cached model prompt or stage mismatch")
        cursor[0] += 1
        return current["response"], current["usage"]
    try:
        run_paper(
            None, "cached-only-not-a-provider-key", model_call=cached_only,
            source_title=source.title, pages_override=load(source.pages_json, {}),
            source_sha=source.source_sha, frozen_snapshot=None,
            scientific_value_gate=False, max_calls=40,
        )
    except PrefixBoundaryReached:
        if cursor[0] != len(entries) or next_stage[0] != "evidence_questions":
            raise EvidenceError("Cached run did not stop at the expected diagnosis boundary")
        last = entries[-1].get("response", {})
        issues = last.get("diagnoses", [])
        absent = sum(1 for issue in issues if isinstance(issue, dict)
                     and issue.get("confidence") is None)
        inference = sum(1 for issue in issues if isinstance(issue, dict)
                        and issue.get("issue_class") == "inference")
        return {"cached_stages": cursor[0], "verified_prompt_hashes": True,
                "next_stage": next_stage[0], "missing_confidences": absent,
                "inference_classes": inference}
    raise EvidenceError("Unexpected complete report from incomplete checkpoints")
