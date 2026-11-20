"""Opt-in, read-only public GitHub API synchronization for the isolated DevStudio.

No webhook/repository secret is required. This is a bounded recent-activity
snapshot (not every historical commit) and never grades scientific experiments.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base
from backend.devstudio_github_sync import (
    REPO, REPO_URL, HEX_SHA, DevGithubActivity, record,
    event_to_ci_status,
)
from backend.devstudio import DevRunRef

PUBLIC_FLAG = "DEVSTUDIO_GITHUB_PUBLIC_POLL_ENABLED"
INTERVAL_SECONDS = 600
API = "https://api.github.com/repos/" + REPO


class DevGithubPoll(Base):
    __tablename__ = "devstudio_github_poll"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(String(80), default="")


def _json(path: str):
    """Never accept arbitrary API URLs or caller-controlled pagination."""
    if not path.startswith("/") or "://" in path or ".." in path:
        raise ValueError("Invalid GitHub API path")
    req = Request(API + path, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "ResearchAtlasDevStudio-GitHubReadOnly/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(req, timeout=6) as response:
        data = response.read(512 * 1024 + 1)
        if len(data) > 512 * 1024:
            raise ValueError("GitHub API payload too large")
        return json.loads(data)


def public_snapshot() -> list[dict]:
    """Recent default-branch commits, PRs, issues and Actions runs."""
    paths = (
        "/commits?per_page=20",
        "/pulls?state=all&per_page=20&sort=updated&direction=desc",
        "/issues?state=all&per_page=20&sort=updated&direction=desc",
        "/actions/runs?per_page=20",
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(_json, paths))
    commits, prs, issues, actions = responses
    if not (isinstance(commits, list) and isinstance(prs, list)
            and isinstance(issues, list) and isinstance(actions, dict)
            and isinstance(actions.get("workflow_runs"), list)):
        raise ValueError("Unexpected GitHub API response format")
    results = []
    for item in commits:
        sha = item.get("sha")
        if not isinstance(sha, str) or not HEX_SHA.fullmatch(sha):
            continue
        data = item.get("commit") or {}
        results.append(record(
            "push", sha, (data.get("message") or "Git commit").split("\n")[0],
            REPO_URL + "/commit/" + sha, "recorded",
            actor=(item.get("author") or {}).get("login") or (data.get("author") or {}).get("name"),
            branch="default-branch", sha=sha,
            detail="Latest commit on default branch (public API, not push webhook)",
            updated=(data.get("committer") or {}).get("date"),
        ))
    for item in prs:
        ident = item.get("number")
        if not isinstance(ident, int) or ident <= 0:
            continue
        status = ("merged" if item.get("merged_at") else
                  "closed" if item.get("state") == "closed" else
                  "draft" if item.get("draft") else "open")
        results.append(record(
            "pull_request", ident, item.get("title"), REPO_URL + "/pull/" + str(ident),
            status, actor=(item.get("user") or {}).get("login"),
            branch=(item.get("head") or {}).get("ref"),
            sha=(item.get("head") or {}).get("sha"),
            detail="Read-only public GitHub API; current PR state",
            updated=item.get("updated_at"),
        ))
    for item in issues:
        ident = item.get("number")
        if not isinstance(ident, int) or ident <= 0 or item.get("pull_request"):
            continue
        results.append(record(
            "issue", ident, item.get("title"), REPO_URL + "/issues/" + str(ident),
            "closed" if item.get("state") == "closed" else "open",
            actor=(item.get("user") or {}).get("login"),
            detail="Read-only public GitHub API; current issue state",
            updated=item.get("updated_at"),
        ))
    for item in actions["workflow_runs"]:
        ident = item.get("id")
        if not isinstance(ident, int) or ident <= 0:
            continue
        results.append(record(
            "workflow_run", ident,
            str(item.get("name") or "CI") + " #" + str(item.get("run_number") or ident),
            REPO_URL + "/actions/runs/" + str(ident),
            item.get("conclusion") or item.get("status") or "unknown",
            actor=(item.get("actor") or {}).get("login"),
            branch=item.get("head_branch"), sha=item.get("head_sha"),
            detail="CI result only; no science evaluation or deployment",
            updated=item.get("updated_at"),
        ))
    return results


def _upsert(db: Session, obj: dict) -> bool:
    row = db.get(DevGithubActivity, obj["event_key"])
    if row and row.source_updated_at and obj["source_updated_at"]:
        if obj["source_updated_at"] < row.source_updated_at:
            return False
    if row is None:
        db.add(DevGithubActivity(**obj))
    else:
        for key, val in obj.items():
            if key != "event_key":
                setattr(row, key, val)
        row.updated_at = datetime.now(timezone.utc)
    if obj["kind"] == "workflow_run":
        url = REPO_URL + "/actions/runs/" + obj["event_key"].split(":")[1]
        for run in db.scalars(select(DevRunRef).where(
            DevRunRef.kind == "github_actions", DevRunRef.external_url == url
        )).all():
            run.status = event_to_ci_status(obj["status"])
    return True


def poll(db: Session) -> dict:
    """Refresh at most once per 10 min per database, retaining older records."""
    if os.getenv(PUBLIC_FLAG, "").lower() not in {"1", "true", "yes"}:
        return {"state": "disabled"}
    now = datetime.now(timezone.utc)
    row = db.get(DevGithubPoll, 1)
    if row is None:
        row = DevGithubPoll(id=1)
        db.add(row)
        db.flush()
    if row.attempted_at:
        previous = row.attempted_at
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        if (now - previous).total_seconds() < INTERVAL_SECONDS:
            return {"state": "cached", "error": row.last_error or None,
                    "last_success": row.succeeded_at.isoformat() if row.succeeded_at else None}
    row.attempted_at = now
    try:
        objects = public_snapshot()
        updated = sum(_upsert(db, x) for x in objects)
        row.succeeded_at = now
        row.last_error = ""
        db.commit()
        return {"state": "updated", "events": updated, "last_success": now.isoformat()}
    except (HTTPError, URLError, OSError, ValueError, TypeError, KeyError) as exc:
        db.rollback()
        row = db.get(DevGithubPoll, 1)
        if row is None:
            row = DevGithubPoll(id=1)
            db.add(row)
        row.attempted_at = now
        row.last_error = type(exc).__name__
        db.commit()
        return {"state": "error", "error": type(exc).__name__,
                "last_success": row.succeeded_at.isoformat() if row.succeeded_at else None}
