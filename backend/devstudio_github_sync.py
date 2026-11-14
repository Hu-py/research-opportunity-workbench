"""Signed GitHub -> Development Studio activity synchronization.

The GitHub feed is factual engineering metadata, *not* an approval queue.
No GH event automatically creates scientific experiments, approves a change,
claims deployment, or counts as a human evaluation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base
from backend.devstudio import DevRunRef

REPO = "Hu-py/research-opportunity-workbench"
REPO_URL = "https://github.com/" + REPO
SUPPORTED = {"push", "pull_request", "issues", "workflow_run"}
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")
SAFE_DELIVERY = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
SYNC_SECRET_ENV = "DEVSTUDIO_GITHUB_SYNC_SECRET"
SYNC_FLAG = "DEVSTUDIO_GITHUB_SYNC_ENABLED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compact(value: Any, limit: int = 220) -> str:
    return str(value or "").replace("\n", " ").replace("\r", " ").strip()[:limit]


class DevGithubActivity(Base):
    __tablename__ = "devstudio_github_activity"
    event_key: Mapped[str] = mapped_column(String(130), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(260))
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(36))
    actor: Mapped[str] = mapped_column(String(90), default="")
    branch: Mapped[str] = mapped_column(String(220), default="")
    sha: Mapped[str] = mapped_column(String(40), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    source_updated_at: Mapped[str] = mapped_column(String(40), default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DevGithubDelivery(Base):
    __tablename__ = "devstudio_github_deliveries"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_name: Mapped[str] = mapped_column(String(30))
    digest: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def record(kind, number, title, url, status, *, actor="", branch="", sha="", detail="", updated=""):
    return {
        "event_key": kind + ":" + str(number),
        "kind": kind,
        "title": compact(title, 260),
        "url": url,
        "status": compact(status, 36),
        "actor": compact(actor, 90),
        "branch": compact(branch, 220),
        "sha": sha if HEX_SHA.fullmatch(str(sha)) else "",
        "detail": compact(detail, 650),
        "source_updated_at": compact(updated, 40),
    }


def parse_github_event(event: str, data: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Allow only expected repo and canonical URLs; don't trust URLs in payload."""
    if not isinstance(data, Mapping) or not isinstance(data.get("repository"), dict):
        raise ValueError("Missing repository")
    if data["repository"].get("full_name") != REPO:
        raise ValueError("Unknown repository")
    actor = compact((data.get("sender") or {}).get("login"), 90)
    if event == "pull_request":
        pr = data.get("pull_request") or {}
        n = data.get("number")
        if not isinstance(n, int) or n <= 0 or not isinstance(pr, Mapping):
            raise ValueError("Invalid PR")
        state = "merged" if pr.get("merged") else "closed" if pr.get("state") == "closed" else "draft" if pr.get("draft") else "open"
        return [record("pull_request", n, pr.get("title") or "PR #" + str(n),
                       REPO_URL + "/pull/" + str(n), state,
                       actor=actor or (pr.get("user") or {}).get("login"),
                       branch=(pr.get("head") or {}).get("ref"),
                       sha=(pr.get("head") or {}).get("sha"),
                       detail="GitHub PR · " + compact(data.get("action"), 32),
                       updated=pr.get("updated_at"))]
    if event == "issues":
        issue = data.get("issue") or {}
        n = issue.get("number")
        if not isinstance(n, int) or n <= 0 or not isinstance(issue, Mapping) or issue.get("pull_request"):
            raise ValueError("Invalid issue")
        return [record("issue", n, issue.get("title") or "Issue #" + str(n),
                       REPO_URL + "/issues/" + str(n),
                       "closed" if issue.get("state") == "closed" else "open",
                       actor=actor or (issue.get("user") or {}).get("login"),
                       detail="GitHub issue · " + compact(data.get("action"), 32),
                       updated=issue.get("updated_at"))]
    if event == "workflow_run":
        run = data.get("workflow_run") or {}
        ident = run.get("id")
        if not isinstance(ident, int) or ident <= 0 or not isinstance(run, Mapping):
            raise ValueError("Invalid workflow run")
        state = compact(run.get("conclusion") or run.get("status") or "unknown", 36)
        return [record("workflow_run", ident,
                       compact(run.get("name") or "GitHub Actions", 180) + " #" + str(run.get("run_number") or ident),
                       REPO_URL + "/actions/runs/" + str(ident), state,
                       actor=actor or (run.get("actor") or {}).get("login"),
                       branch=run.get("head_branch"), sha=run.get("head_sha"),
                       detail="CI result only; not scientific approval or production deployment",
                       updated=run.get("updated_at"))]
    if event == "push":
        sha = str(data.get("after") or "")
        if not HEX_SHA.fullmatch(sha):
            raise ValueError("Invalid pushed SHA")
        raw_ref = compact(data.get("ref"), 220)
        branch = raw_ref.removeprefix("refs/heads/")
        count = data.get("size")
        count = count if isinstance(count, int) and 0 <= count < 100000 else len(data.get("commits") or [])
        return [record("push", sha, compact((data.get("head_commit") or {}).get("message") or "Git push", 240),
                       REPO_URL + "/commit/" + sha, "recorded",
                       actor=actor or (data.get("pusher") or {}).get("name"),
                       branch=branch, sha=sha,
                       detail=str(count) + " commits pushed; latest commit only (not a full diff)",
                       updated=compact((data.get("head_commit") or {}).get("timestamp"), 40))]
    raise ValueError("Unsupported GitHub event")


def event_to_ci_status(conclusion: str) -> str:
    if conclusion == "success":
        return "ci_success"
    if conclusion in {"failure", "timed_out", "action_required", "startup_failure"}:
        return "ci_failure"
    if conclusion in {"cancelled", "skipped", "neutral", "stale"}:
        return "ci_" + conclusion
    return "ci_running"


def ingest(db: Session, event: str, data: Mapping[str, Any], delivery: str, digest: str) -> dict:
    if db.get(DevGithubDelivery, delivery):
        old = db.get(DevGithubDelivery, delivery)
        if old.digest != digest or old.event_name != event:
            raise ValueError("Conflicting GitHub delivery identifier")
        return {"state": "duplicate", "events": 0}
    activities = parse_github_event(event, data)
    updated = 0
    for obj in activities:
        row = db.get(DevGithubActivity, obj["event_key"])
        stale = bool(row is not None and row.source_updated_at and obj["source_updated_at"]
                     and obj["source_updated_at"] < row.source_updated_at)
        if row is None:
            db.add(DevGithubActivity(**obj))
            updated += 1
        elif not stale:
            for key, value in obj.items():
                if key != "event_key":
                    setattr(row, key, value)
            row.updated_at = utc_now()
            updated += 1

        if obj["kind"] == "workflow_run" and not stale:
            # Only engineering CI provenance changes; never a human evaluation.
            github_run = REPO_URL + "/actions/runs/" + obj["event_key"].split(":")[1]
            refs = db.scalars(select(DevRunRef).where(
                DevRunRef.kind == "github_actions",
                DevRunRef.external_url == github_run)).all()
            for run in refs:
                run.status = event_to_ci_status(obj["status"])
    db.add(DevGithubDelivery(id=delivery, event_name=event, digest=digest))
    db.commit()
    return {"state": "applied", "events": updated}


def verify_signature(body: bytes, supplied: str, secret: str) -> bool:
    if not secret or not supplied.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def public_activity(row: DevGithubActivity) -> dict[str, Any]:
    return {k: getattr(row, k) for k in (
        "event_key", "kind", "title", "url", "status", "actor", "branch", "sha",
        "detail", "source_updated_at")} | {
        "received_at": row.received_at.isoformat() if row.received_at else None
    }


def mount(app, *, get_db, require_actor, team_auth_enabled):
    router = APIRouter(prefix="/api/devstudio/github", tags=["Development Studio GitHub Sync"])

    @router.get("/activity")
    def activity(db: Session = Depends(get_db), actor=Depends(require_actor)):
        if not team_auth_enabled() or actor is None:
            raise HTTPException(403, "Team login required")
        rows = db.scalars(select(DevGithubActivity)
                          .order_by(DevGithubActivity.updated_at.desc())
                          .limit(60)).all()
        return {
            "repo": REPO,
            "items": [public_activity(row) for row in rows],
            "integration_status": (
                "disabled" if os.getenv(SYNC_FLAG, "").lower() not in {"1", "true", "yes"}
                else "missing_secret" if not os.getenv(SYNC_SECRET_ENV)
                else "ready_for_signed_events"
            ),
            "last_received_at": rows[0].updated_at.isoformat() if rows else None,
            "note": "只同步 GitHub 工程事件；实验与科研质量必须单独登记并审核。"
        }

    @router.post("/webhook")
    async def webhook(request: Request, db: Session = Depends(get_db)):
        if not team_auth_enabled() or os.getenv(SYNC_FLAG, "").lower() not in {"1", "true", "yes"}:
            raise HTTPException(503, "GitHub synchronization disabled")
        secret = os.getenv(SYNC_SECRET_ENV, "")
        if len(secret) < 32:
            raise HTTPException(503, "GitHub synchronization secret is missing or too short")
        if request.headers.get("content-length", "").isdigit() and int(request.headers["content-length"]) > 1024 * 1024:
            raise HTTPException(413, "GitHub event too large")
        body = await request.body()
        if len(body) > 1024 * 1024:
            raise HTTPException(413, "GitHub event too large")
        supplied = request.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(body, supplied, secret):
            raise HTTPException(401, "Invalid GitHub event signature")
        event = request.headers.get("X-GitHub-Event", "")
        delivery = request.headers.get("X-GitHub-Delivery", "")
        if event not in SUPPORTED or not SAFE_DELIVERY.fullmatch(delivery or ""):
            raise HTTPException(422, "Unsupported GitHub event or delivery identifier")
        try:
            payload = json.loads(body)
            return ingest(db, event, payload, delivery, hashlib.sha256(body).hexdigest())
        except (ValueError, TypeError, KeyError) as exc:
            db.rollback()
            raise HTTPException(422, str(exc)[:200]) from exc

    app.include_router(router)
