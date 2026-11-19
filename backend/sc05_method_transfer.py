"""R6.7: separate defensible domain-neighbor evidence from method-transfer leads.

This module does not infer scientific originality, approve method transfer,
or treat shared words such as 'network' and 'resilience' as a mechanism match.
It never uses the exposed R6.6 DOI holdout as training/tuning data.
"""
from __future__ import annotations

from typing import Any

from backend.sc05_relevance import _matches

POLICY_VERSION = "sc05-dual-evidence-v0.1"

# Source-agnostic methodological terminology. A single generic word such as
# 'network', 'resilience', 'model', or 'analysis' is deliberately insufficient.
STRONG_METHODS = (
    "graph neural network", "graph attention", "graph embedding",
    "reinforcement learning", "causal inference", "difference-in-differences",
    "bayesian hierarchical", "agent-based model", "agent-based simulation",
    "network optimization", "integer programming", "stochastic programming",
    "topological data analysis", "spatial econometrics",
    "dynamic graph", "spatiotemporal modeling", "dimensionality reduction",
    "transfer learning", "gradient boosting", "random forest",
    "variational autoencoder", "multi-agent system", "percolation theory",
    "network flow optimization", "community detection", "graph convolution",
    "physics-informed neural", "optimal transport", "discrete choice model",
)
WEAK_METHODS = (
    "network flow", "simulation", "statistical learning", "causal model",
    "optimization", "classification", "graph model", "predictive model",
    "stochastic model", "spatial model", "machine learning",
    "multiscale model", "dynamical system", "sensitivity analysis",
)
TRANSFER_MIN_EXPLANATION = 20
TRANSFER_MAX_EXPLANATION = 700


def _clean_text(value: Any, *, length: int = 700) -> str:
    return value.strip()[:length] if isinstance(value, str) else ""


def collect_transfer_leads(
    retrieved: list[dict[str, Any]],
    domain_papers: list[dict[str, Any]],
    screen_audit: dict[str, Any],
    *,
    max_leads: int = 6,
    forced_technical_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create a separate, unapproved method lane from domain-screen rejects.

    A lead is not a verified transfer. It is surfaced only when a real abstract
    explicitly names a non-generic method, never just lexical proximity.
    Source-paper/self-citation and missing-abstract rejects stay excluded.
    """
    if not 0 <= max_leads <= 12:
        raise ValueError("max_leads must be 0..12")
    accepted_ids = {p.get("id") for p in domain_papers}
    rejected = {
        r.get("paper_id"): r.get("reason")
        for r in screen_audit.get("quarantined_records", [])
    }
    forced_technical_ids = forced_technical_ids or set()
    leads: list[dict[str, Any]] = []
    considered = 0
    weak_only = 0
    methods_unverified = 0
    for paper in retrieved:
        pid = str(paper.get("id") or "")
        if not pid or pid in accepted_ids:
            continue
        reason = (
            "curated_C_technical_method_not_domain_prior"
            if pid in forced_technical_ids else rejected.get(pid, "")
        )
        if reason not in {
            "out_of_domain_or_unsupported_transfer",
            "curated_C_technical_method_not_domain_prior",
        }:
            continue
        considered += 1
        abstract = _clean_text(paper.get("abstract"), length=2200)
        title = _clean_text(paper.get("title"), length=300)
        if not title or not abstract:
            continue
        excerpt = title + " " + abstract
        strong = _matches(excerpt, STRONG_METHODS)
        weak = _matches(excerpt, WEAK_METHODS)
        if not strong:
            if weak:
                weak_only += 1
            continue
        if len(leads) >= max_leads:
            methods_unverified += 1
            continue
        url = _clean_text(paper.get("url"), length=1000)
        if not url.startswith("https://"):
            continue
        leads.append({
            "id": pid,
            "title": title,
            "doi": _clean_text(paper.get("doi"), length=180),
            "url": url,
            "year": _clean_text(paper.get("year"), length=10),
            "venue": _clean_text(paper.get("venue"), length=200),
            "source_tier": _clean_text(paper.get("source_tier"), length=20),
            "abstract": abstract[:1250],
            "method_signals": strong[:6],
            "review_status": "unreviewed_method_candidate",
            "eligible_for_nearest_prior": False,
            "evidence_level": "OpenAlex abstract only; transfer untested",
            "original_screen_reason": reason,
        })
    audit = {
        "policy_version": POLICY_VERSION,
        "cross_domain_rejects_considered": considered,
        "method_leads_emitted": len(leads),
        "weak_only_unpromoted": weak_only,
        "strong_method_overflow": methods_unverified,
        "method_lead_ids": [p["id"] for p in leads],
        "auto_approved_transfers": 0,
        "note": (
            "Method leads are non-prior, unreviewed cross-domain clues. "
            "Transfer requires an independently checked input/output mapping, "
            "invariance assumptions, falsification test, and human approval."
        ),
    }
    return leads, audit


def method_leads_for_model(
    leads: list[dict[str, Any]],
    *,
    max_leads: int = 4,
    abstract_chars: int = 650,
) -> list[dict[str, Any]]:
    """Bound the prompt without introducing an additional paid model call."""
    return [{
        "id": paper["id"],
        "title": paper["title"],
        "doi": paper["doi"],
        "url": paper["url"],
        "year": paper["year"],
        "method_signals": paper["method_signals"],
        "abstract": paper["abstract"][:abstract_chars],
        "review_status": "unreviewed_method_candidate",
    } for paper in leads[:max_leads]]


def _exact_excerpt(value: Any, abstract: str) -> tuple[str, str]:
    excerpt = _clean_text(value, length=151)
    if not 12 <= len(excerpt) <= 150:
        return "", "missing_or_invalid"
    if excerpt in abstract:
        return excerpt, "verified"
    if " ".join(excerpt.split()) in " ".join(abstract.split()):
        return excerpt, "verified_whitespace_normalized"
    return "", "rejected"


def screen_transfer_bridges(
    raw: Any,
    lead_papers: list[dict[str, Any]],
    route_ids: set[str],
    *,
    limit: int = 6,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Audit model-proposed cross-domain mappings, never approve them.

    A fabricated paper/route reference, missing bridge component, or invented
    abstract quote is excluded. Valid structure remains 'needs_human_review'
    and cannot be used as a closest prior or publication novelty evidence.
    """
    if not isinstance(raw, list):
        raw = []
    papers = {p["id"]: p for p in lead_papers}
    fields = (
        "method_name", "source_input", "target_input",
        "source_output", "target_output", "invariance_assumption",
        "discriminating_test", "failure_condition",
    )
    accepted = []
    reasons: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for pos, item in enumerate(raw[:limit], 1):
        if not isinstance(item, dict):
            reasons.append({"position": pos, "reason": "invalid_structure"})
            continue
        pid = item.get("paper_id")
        rid = item.get("route_id")
        if not isinstance(pid, str) or pid not in papers:
            reasons.append({"position": pos, "reason": "unrecognized_method_paper"})
            continue
        if not isinstance(rid, str) or rid not in route_ids:
            reasons.append({"position": pos, "reason": "unrecognized_route"})
            continue
        if (pid, rid) in seen:
            reasons.append({"position": pos, "reason": "duplicate_bridge"})
            continue
        values = {key: _clean_text(item.get(key), length=TRANSFER_MAX_EXPLANATION)
                  for key in fields}
        if any(len(val) < TRANSFER_MIN_EXPLANATION for val in values.values()):
            reasons.append({"position": pos, "reason": "incomplete_input_output_or_falsification"})
            continue
        quote, status = _exact_excerpt(
            item.get("abstract_excerpt"), papers[pid]["abstract"])
        if not quote:
            reasons.append({"position": pos, "reason": "abstract_quote_not_verified"})
            continue
        seen.add((pid, rid))
        accepted.append({
            "route_id": rid,
            "paper_id": pid,
            **values,
            "abstract_excerpt": quote,
            "abstract_quote_status": status,
            "review_status": "needs_human_review",
            "approved": False,
            "eligible_for_nearest_prior": False,
        })
    audit = {
        "policy_version": POLICY_VERSION,
        "submitted": len(raw),
        "considered": min(len(raw), limit),
        "accepted_provisional_bridges": len(accepted),
        "rejected": reasons,
        "excess_candidates": max(0, len(raw) - limit),
        "human_approved": 0,
        "scientific_novelty_certified": False,
    }
    return accepted, audit
