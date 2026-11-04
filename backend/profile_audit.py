"""Headless, evidence-only research profile audit and reproducible JSON export.

Run locally with an authorized DATABASE_URL:
    python -m backend.profile_audit

On Render, admins may temporarily set PROFILE_AUDIT_ON_STARTUP=1.
The startup logger emits only restricted-data-filtered names/metadata,
never raw files, contact details, user messages, credentials or paths.
Default is disabled. Does not invoke DeepSeek or modify the official profile.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime,timezone
from sqlalchemy import select
from backend.profile_database import evidence_inventory,database_draft,matched_evidence
from backend.profile_intelligence import ResearchProfileDraft, _validated,unpack
from backend.team import current_profile_version

def audit(db):
    inventory=evidence_inventory(db)
    raw, refs=database_draft(inventory)
    profile,analysis=_validated(raw)
    allowed={
        x["ref"] for key in ("team_achievements","datasets","approved_papers")
        for x in inventory[key]
    }
    unknown=sorted(set(refs)-allowed)
    for x in analysis["line_insights"]:
        unknown.extend(ref for ref in x["evidence_refs"] if ref not in allowed)
    if unknown:
        raise ValueError("Profile audit references unsupported IDs")
    if len(profile["research_lines"])!=len(analysis["line_insights"]):
        raise ValueError("Research line and analysis count mismatch")
    profiles_before=current_profile_version(db)
    provisional=db.scalars(select(ResearchProfileDraft).where(
        ResearchProfileDraft.source=="database_snapshot",
        ResearchProfileDraft.status=="draft").order_by(
        ResearchProfileDraft.created_at.desc())).all()
    latest=provisional[0] if provisional else None
    snapshots=[]
    achievements={a["ref"]:a for a in inventory["team_achievements"]}
    assets={a["ref"]:a for a in inventory["datasets"]}
    for line,insight in zip(profile["research_lines"],analysis["line_insights"]):
        refs_for_line=insight["evidence_refs"]
        recorded=[achievements[x] for x in refs_for_line if x in achievements]
        matched_assets=[assets[x] for x in refs_for_line if x in assets]
        is_cluster=line["id"].startswith("db_theme_")
        snapshots.append({
            "id":line["id"],"label":line["name"],
            "type":"verified_output_topic_cluster" if is_cluster else
                   "registered_official_line",
            "problem":line["problem"],
            "keywords":line["keywords"],
            "evidence_status":insight["evidence_status"],
            "verified_output_matches":[{"ref":v["ref"],"title":v["title"],
                "year":v["year"],"kind":v["kind"]} for v in recorded],
            "dataset_matches":[{"ref":v["ref"],"name":v["name"],
                "category":v["category"],"coverage":v["coverage"],
                "period":v["period"],"format":v["format"]} for v in matched_assets],
            "approved_paper_matches":[x for x in refs_for_line if x.startswith("papers:")],
            "method_claim":"unverified_from_metadata",
            "next_experiment":insight["next_experiment"],
            "association_method":"deterministic-tag-and-name-matching;not-causal-proof",
        })
    categories=inventory["dataset_categories"]
    topics=Counter(t for a in inventory["team_achievements"] for t in a["tags"])
    output={
        "source":"live-render-postgresql",
        "report_kind":"read_only_headless_evidence_audit",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "counts":inventory["counts"],
        "sources":{
            "registered_profile":{"name":inventory["profile"]["team"]["name"]
                     if inventory["profile"] else "",
                "line_names":[x["name"] for x in
                    (inventory["profile"] or {}).get("research_lines",[])]},
            "verified_achievements":[{"ref":x["ref"],"title":x["title"],
                "year":x["year"],"kind":x["kind"],"tags":x["tags"]}
                for x in inventory["team_achievements"]],
            "eligible_dataset_metadata":[{"ref":x["ref"],"name":x["name"],
                "category":x["category"],"period":x["period"],
                "coverage":x["coverage"],"format":x["format"]}
                for x in inventory["datasets"]],
            "dataset_category_counts":categories,
            "recurring_achievement_tags":[{"tag":k,"count":v}
                for k,v in topics.most_common() if v>=2],
        },
        "proposed_lines":snapshots,
        "checks":{
            "database_connectivity":"pass",
            "evidence_refs_exist":"pass",
            "restricted_assets_excluded":"pass",
            "profile_schema":"pass",
            "report_has_raw_dataset_files":False,
            "official_version_unchanged":profiles_before==current_profile_version(db),
            "official_version":profiles_before,
            "review_draft_present":bool(latest),
            "draft_id":latest.id if latest else None,
            "draft_source":latest.source if latest else None,
            "llm_invoked":False,
            "paid_model_calls":0,
            "review_required":True
        },
        "caveats":[
            "This is a rule-based thematic grouping and source audit, not deep scholarly synthesis.",
            "An output's verified status reflects the team registry's existing label.",
            "Dataset registration does not verify field completeness, legal access or feasibility.",
            "No human-approved new paper abstracts are present unless approved_papers>0.",
            "No team profile is automatically published and no paid model is called.",
        ],
    }
    return output

def emit_log_report(db,logger):
    """Emit bounded, separately parseable lines; never log unrestricted fields."""
    report=audit(db)
    meta={"counts":report["counts"],"checks":report["checks"],
          "category_counts":report["sources"]["dataset_category_counts"],
          "top_tags":report["sources"]["recurring_achievement_tags"],
          "official":report["sources"]["registered_profile"]}
    logger.info("PROFILE_AUDIT_META %s",json.dumps(meta,ensure_ascii=False))
    for i,item in enumerate(report["sources"]["verified_achievements"]):
        logger.info("PROFILE_AUDIT_ACHIEVEMENT %s",
                    json.dumps({"i":i+1,**item},ensure_ascii=False))
    for i,item in enumerate(report["sources"]["eligible_dataset_metadata"]):
        logger.info("PROFILE_AUDIT_DATASET %s",
                    json.dumps({"i":i+1,**item},ensure_ascii=False))
    for i,item in enumerate(report["proposed_lines"]):
        logger.info("PROFILE_AUDIT_LINE %s",
                    json.dumps({"i":i+1,**item},ensure_ascii=False))
    logger.info("PROFILE_AUDIT_COMPLETE lines=%d findings=%d",
                len(report["proposed_lines"]),
                sum(len(x["verified_output_matches"]) for x in report["proposed_lines"]))
    return report

def main():
    from research_workbench.core import session_factory
    with session_factory()() as db:
        print(json.dumps(audit(db),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
