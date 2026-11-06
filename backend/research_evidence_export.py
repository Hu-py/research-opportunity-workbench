"""Explicitly authorized, read-only, public-safe team evidence export.

This module does not access files on disks, read dataset rows, modify database
records or invoke LLMs. It never exports custodians, private file paths, people,
or restricted/internal dataset catalog entries.
"""
from __future__ import annotations

import json
from sqlalchemy import select
from research_workbench.core import Paper, get_profile
from backend.profile_database import safe_official
from backend.repository import TeamAchievement
from backend.cusp import CuspDataset, sensitive_level
from backend.discovery import PaperCandidate


def team_evidence_bundle(db, *, max_achievements: int = 80,
                         max_datasets: int = 25, max_external: int = 12,
                         sharing_approved: bool = False) -> dict:
    if not 1 <= max_achievements <= 100 or not 0 <= max_datasets <= 50 or not 0 <= max_external <= 30:
        raise ValueError("Evidence export limits out of bounds")
    outputs = db.scalars(
        select(TeamAchievement).where(TeamAchievement.status == "verified")
        .order_by(TeamAchievement.year.desc(), TeamAchievement.title)
        .limit(max_achievements)
    ).all()
    achievements = [{
        "id": item.id, "title": item.title[:400],
        "year": item.year if 1900 <= item.year <= 2100 else 2000,
        "kind": item.kind[:40],
        "tags": [str(x)[:100] for x in json.loads(item.tags_json or "[]")[:16]],
        "abstract": "", "doi": (item.doi or "")[:200],
        "venue": (item.venue or "")[:200],
        "evidence_level": "title_only",
        "ownership": "verified_team_output",
    } for item in outputs if item.title and item.id]

    # Public-only metadata. Internal datasets still require separate owner
    # authorization and are intentionally NOT eligible for this automated feed.
    assets = db.scalars(
        select(CuspDataset).where(CuspDataset.sensitivity == "public")
        .order_by(CuspDataset.category, CuspDataset.name)
        .limit(max_datasets * 3 if max_datasets else 0)
    ).all()
    datasets = [{
        "id": item.id,
        "name": item.name[:200],
        "category": (item.category or "")[:120],
        "description": (item.description or "")[:350],
        "prior_research": (item.prior_research or "")[:350],
        "coverage": (item.coverage or "")[:200],
        "period": (item.period or "")[:150],
        "fields": [], "sensitivity": "public",
        "access_verified": False,
    } for item in assets
      if item.id and item.name and sensitive_level(item.name) != "restricted"][:max_datasets]
    candidates = db.scalars(
        select(PaperCandidate).where(PaperCandidate.status.in_(("relevant", "method")))
        .order_by(PaperCandidate.score.desc()).limit(max_external * 4 if max_external else 0)
    ).all()
    papers = []
    seen = set()
    for candidate in candidates:
        paper = db.get(Paper, candidate.paper_id)
        if not paper or paper.id in seen or not paper.title:
            continue
        seen.add(paper.id)
        papers.append({
            "id": paper.id[:140], "title": paper.title[:400],
            "abstract": (paper.abstract or "")[:750],
            "doi": (paper.doi or "")[:200],
            "venue": (paper.venue or "")[:200],
            "ownership": "external_literature",
        })
        if len(papers) >= max_external:
            break
    bundle = {
        "bundle_id": "research-team",
        "source": "authorized_database_export",
        "sharing_approved": bool(sharing_approved),
        "achievements": achievements,
        "datasets": datasets,
        "external_papers": papers,
        "old_profile": safe_official(get_profile(db)) or {},
    }
    if not achievements:
        raise ValueError("No verified team outputs are present; cannot create an evidence-grounded portrait")
    # One GitHub secret can store at most 48 KiB. Return a bounded payload and
    # fail visibly instead of silently dropping historical works to fit.
    packed = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(packed) > 44_000:
        raise ValueError("Team metadata exceeds safe GitHub Secret size; use the secure remote sync instead")
    return bundle
