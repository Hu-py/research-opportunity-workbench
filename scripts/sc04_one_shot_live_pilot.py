"""One-shot authenticated-owner *operator* pilot for a user's explicit SC04 request.

The normal SC04 web workflow keeps its strict scientist-confirmation + A/B/C
requirements unchanged. This first live API connectivity/paper-reading pilot
has a deliberately separate provisional snapshot based only on prior approved
source search, and is labelled so it cannot be mistaken for a scientific claim.

This runs ONLY inside the already verified isolated test database/schema at
Render server boot, with the exact opt-in environment flag. It is idempotent
across process restarts, spends at most three model requests via the existing
daily budget, and never prints the API key, abstracts, or prompt content.
"""
from __future__ import annotations
import json, os, re
from sqlalchemy import select
from backend.team import TeamMember, add_audit
from backend.account_onboarding import OwnerClaim
from backend.sc04_evolution import (
    SC04Run, BASELINE_DRAFT, VERSION, TASK_KEY, now, dump, load, digest,
)
from backend.sc04_evolution_runner import execute
from backend.task_venue_radar import TaskVenuePaperRun

RUN_ID="sc04_r1_live_owner_20261115"
OPT_IN="authorized-one-time-sc04-r1-20261115"
MINIMUM=3
MAXIMUM=5


def _logged(payload):
    print(json.dumps({"type":"sc04_r1_live_owner_trial", **payload},
                     ensure_ascii=False),flush=True)


def _valid_papers(scan):
    raw=load(scan.results_json,[])
    if not isinstance(raw,list):
        return []
    observed={}
    for item in raw[:100]:
        if not isinstance(item,dict) or item.get("probe_group")!="A":
            continue
        pid=str(item.get("id") or "")
        url=str(item.get("url") or "")
        abstract=re.sub(r"\s+"," ",str(item.get("abstract") or "")).strip()
        title=str(item.get("title") or "").strip()
        if not pid or not url.startswith("https://") or not title or len(abstract)<130:
            continue
        if pid in observed:continue
        observed[pid]={
            "id":pid[:255],"title":title[:350],
            "abstract":abstract[:2600],"url":url[:1100],
            "group":"A", "venue":str(item.get("venue") or "")[:200],
            "published":str(item.get("published") or "")[:30],
            "evidence_level":"OpenAlex abstract, not full text",
        }
    # Rank by *research relevance*, not publication quality. This selection
    # is transparent and provisional, never written as a journal approval.
    terms=("child","health","built environment","neighborhood","spatial",
           "urban","development","exposure","generalization","transfer")
    def rank(item):
        t=item["title"].casefold()
        a=item["abstract"].casefold()
        return (-sum(3*(term in t)+(term in a) for term in terms),
                item["title"].casefold(),item["id"])
    return sorted(observed.values(),key=rank)[:MAXIMUM]


def _owner(db):
    claim=db.get(OwnerClaim,1)
    if claim is None or not claim.member_id:return None
    owner=db.get(TeamMember,claim.member_id)
    if not owner or not owner.active or owner.role!="owner":
        return None
    # Never silently transfer an experiment to arbitrary registered members.
    return owner


def create_snapshot(factory):
    with factory() as db:
        existing=db.get(SC04Run,RUN_ID)
        if existing:
            return {"status":"already_exists","run_id":RUN_ID,
                    "stored_status":existing.status,"owner_id":existing.member_id,
                    "paper_count":len((load(existing.snapshot_json,{}) or {}).get("papers",[]))}
        owner=_owner(db)
        if owner is None:
            return {"status":"blocked","reason":"verified_owner_session_fixture_missing"}
        scan=db.scalars(select(TaskVenuePaperRun).where(
            TaskVenuePaperRun.member_id==owner.id,
            TaskVenuePaperRun.task_key==TASK_KEY,
            TaskVenuePaperRun.status.in_(("completed","partial")),
        ).order_by(TaskVenuePaperRun.created_at.desc()).limit(1)).first()
        if scan is None:
            return {"status":"blocked","reason":"no_completed_owner_scoped_approved_source_scan"}
        selected=_valid_papers(scan)
        if len(selected)<MINIMUM:
            return {"status":"blocked","reason":"too_few_real_source_abstracts",
                    "eligible_papers":len(selected)}
        source_ids=load(scan.source_ids_json,{})
        if not isinstance(source_ids,dict) or not source_ids.get("A"):
            return {"status":"blocked","reason":"source_scan_missing_approved_a_filter"}
        other=db.scalars(select(SC04Run.id).where(
            SC04Run.member_id==owner.id,
            SC04Run.status.in_(("queued","running")),
        ).limit(1)).first()
        if other:
            return {"status":"blocked","reason":"other_evolution_run_in_progress"}
        # Do not assert or invent human confirmation of the original baseline.
        # This snapshot is a separate exploratory run, not a persisted baseline.
        snap={
            "task":TASK_KEY,
            "baseline":BASELINE_DRAFT,
            "baseline_revision":None,
            "baseline_confirmed":False,
            "baseline_provenance":"user_conversation_context_unreviewed",
            "source_scan":scan.id,
            "source_ids":source_ids,
            "papers":selected,
            "skill_version":VERSION,
            "evidence_level":"openalex_abstract_only",
            "probes_present":["A"],
            "probes_missing":["B","C"],
            "trial_type":"first_real_LLM_exploratory_single_probe",
            "not_full_sc04_release":True,
            "novelty_status":"not_systematically_verified",
            "scientific_result_status":"not_human_reviewed",
            "operator_user_request":"start_real_test_with_stored_render_key_2026-11-15",
            "auto_repeat":False,
        }
        row=SC04Run(id=RUN_ID,member_id=owner.id,task_key=TASK_KEY,
                    status="queued",stage="reader",snapshot_json=dump(snap),
                    snapshot_sha=digest(snap))
        db.add(row)
        add_audit(db,"sc04.operator_pilot_queued",owner.id,row.id,
                  "user requested one-time actual provider test; unconfirmed baseline, "
                  "single approved probe A, max three budget-gated LLM calls")
        db.commit()
        return {"status":"created","run_id":RUN_ID,"owner_id":owner.id,
                "paper_count":len(selected),"titles":[x["title"] for x in selected],
                "scan_id":scan.id,"evidence_level":"abstract"}


def run_once(factory):
    # The startup script verifies the physical PG database/schema before
    # invoking this function. Enforce again in case another caller imports it.
    if os.getenv("SC04_R1_ONE_SHOT","")!=OPT_IN:
        return
    if os.getenv("DEVSTUDIO_E2E_ISOLATED")!="1":
        _logged({"status":"blocked","reason":"isolation_flag_required"});return
    if os.getenv("PGOPTIONS","")!="-c search_path=atlas_devstudio_e2e_20261114":
        _logged({"status":"blocked","reason":"wrong_schema"});return
    if not os.getenv("SC04_DEEPSEEK_API_KEY","").strip():
        _logged({"status":"blocked","reason":"sc04_render_deepseek_key_missing"});return
    try:
        outcome=create_snapshot(factory)
        # Never print raw abstracts, prompts, email or real member IDs.
        _logged({k:v for k,v in outcome.items() if k!="owner_id"})
        if outcome["status"]!="created":
            return
        executed=execute(factory,RUN_ID)
        with factory() as db:
            row=db.get(SC04Run,RUN_ID)
            if row is None:
                _logged({"status":"failed","reason":"run_record_missing"});return
            # Preserve complete outputs privately in SQL; only limited,
            # non-sensitive scientific summaries are emitted to service logs.
            readings=load(row.reader_json,[])
            matches=load(row.matches_json,[])
            variants=load(row.variants_json,[])
            critics=load(row.critic_json,[])
            _logged({
                "status":row.status,"stage":row.stage,
                "model_requests_completed":row.model_calls,
                "actual_input_tokens":row.input_tokens,
                "actual_output_tokens":row.output_tokens,
                "error":row.error,
                "paper_readings":len(readings),
                "method_comparisons":len(matches),
                "research_variants":len(variants),
                "critic_reviews":len(critics),
                "run_id":RUN_ID,
                "evidence_label":"five_actual_OpenAlex_abstracts_from_one_approved_A_probe",
                "not_scientific_validation":True,
                "variant_summaries":[{
                    "id":v.get("id"),"title":v.get("title"),
                    "hypothesis":str(v.get("hypothesis") or "")[:320],
                    "baseline":str(v.get("baseline_to_beat") or "")[:180],
                    "minimal_test":str(v.get("minimal_test") or "")[:420],
                    "stop_condition":str(v.get("stop_condition") or "")[:240],
                } for v in variants],
                "critic_summary":[{
                    "id":c.get("variant_id"),"verdict":c.get("verdict"),
                    "fatal_issues":(c.get("fatal_issues") or [])[:3],
                    "stop_condition":str(c.get("stop_condition") or "")[:200],
                } for c in critics],
            })
    except Exception as exc:
        _logged({"status":"failed","reason":"operator_pilot_exception",
                 "error_class":type(exc).__name__})
