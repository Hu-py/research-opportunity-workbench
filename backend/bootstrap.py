"""One-time first administrator initialization for free hosts without shell access.

Credentials come only from provider environment variables and are never logged.
Turn TEAM_BOOTSTRAP_ENABLED off and delete the password immediately afterward.
"""
from __future__ import annotations

import logging
import os
from sqlalchemy import select, func
from research_workbench.core import Profile
from backend.team import TeamMember, create_member

logger = logging.getLogger("uvicorn.error")


def bootstrap_admin_from_env(factory) -> str:
    if os.getenv("TEAM_BOOTSTRAP_ENABLED", "false").strip().lower() not in ("true", "1", "yes"):
        return "disabled"
    email = os.getenv("TEAM_BOOTSTRAP_EMAIL", "").strip()
    password = os.getenv("TEAM_BOOTSTRAP_PASSWORD", "")
    name = os.getenv("TEAM_BOOTSTRAP_NAME", "Research Team Admin").strip()
    if not email or not password:
        raise RuntimeError("One-time admin setup requires TEAM_BOOTSTRAP_EMAIL and TEAM_BOOTSTRAP_PASSWORD")
    if len(password) < 12 or len(password) > 256:
        raise RuntimeError("One-time admin password must contain 12 to 256 characters")

    with factory() as db:
        member_count = db.scalar(select(func.count()).select_from(TeamMember)) or 0
        if member_count:
            logger.info("Team admin bootstrap skipped: member accounts already exist")
            return "already_initialized"
        # A fresh account is created only when there are zero members.
        # create_member refuses a non-admin initial role, validates inputs,
        # and commits a one-way Argon2 password hash and audit entry.
        create_member(db, email=email, name=name, password=password, role="admin", initial=True)
    logger.info("First team administrator initialized successfully; remove one-time bootstrap secrets")
    return "created"
