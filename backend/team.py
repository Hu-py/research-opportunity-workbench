"""Single-team identity, shared profile revisions, and auditable operations.

Team workspace intentionally has ONE shared Profile and literature/ideas DB.
Members have separate sessions so contributions can be attributed and revoked.
"""
from __future__ import annotations
import hashlib
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Literal
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, DateTime, func, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from research_workbench.core import Base, Profile, get_profile, set_profile

PASSWORD = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
ROLES = ("admin", "researcher", "viewer")
SESSION_SECONDS = 7 * 24 * 60 * 60

def timestamp() -> datetime:
    return datetime.now(timezone.utc)

class TeamMember(Base):
    __tablename__ = "team_members"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(140))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="researcher")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=timestamp)

class TeamSession(Base):
    __tablename__ = "team_sessions"
    token_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("team_members.id"), index=True)
    expires_at: Mapped[int] = mapped_column(Integer)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=timestamp)

class TeamProfileRevision(Base):
    __tablename__ = "team_profile_revisions"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_json: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=timestamp)

class AuditEntry(Base):
    __tablename__ = "team_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target: Mapped[str] = mapped_column(String(255), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=timestamp)

def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if not email or len(email) > 255 or "@" not in email or email.startswith("@"):
        raise ValueError("Invalid email")
    return email

def add_audit(db: Session, action: str, actor_id: str | None, target: str="", note: str=""):
    db.add(AuditEntry(actor_id=actor_id, action=action, target=target[:255], note=note[:1500]))

def create_member(db: Session, email: str, name: str, password: str, role: str="researcher",
                  actor_id: str | None=None, initial: bool=False) -> TeamMember:
    normalized=normalize_email(email)
    if not 2 <= len(name.strip()) <= 140:raise ValueError("Name must be 2..140 characters")
    if len(password) < 12 or len(password) > 256:raise ValueError("Password must be 12..256 characters")
    if role not in ROLES:raise ValueError("Invalid role")
    if initial:
        count=db.scalar(select(func.count()).select_from(TeamMember))
        if count:raise ValueError("Team already initialized; invite using authenticated admin API")
        if role!="admin":raise ValueError("Initial account must be admin")
    if db.scalar(select(TeamMember.id).where(TeamMember.email==normalized)):
        raise ValueError("Email already exists")
    member=TeamMember(id=str(uuid.uuid4()),email=normalized,name=name.strip(),
                      password_hash=PASSWORD.hash(password),role=role,active=True)
    db.add(member)
    add_audit(db,"member.created",actor_id,member.id,note="role="+role)
    db.commit()
    return member

def public_member(m: TeamMember) -> dict:
    return {"id":m.id,"email":m.email,"name":m.name,"role":m.role,
            "active":m.active,"created_at":m.created_at.isoformat() if m.created_at else None}

def login(db: Session,email: str,password: str) -> tuple[str,TeamMember] | None:
    try:normalized=normalize_email(email)
    except ValueError:return None
    member=db.scalar(select(TeamMember).where(TeamMember.email==normalized))
    if member is None or not member.active:return None
    try:
        if not PASSWORD.verify(member.password_hash,password):return None
    except (VerifyMismatchError,VerificationError):
        return None
    raw=secrets.token_urlsafe(48)
    db.add(TeamSession(token_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                       member_id=member.id, expires_at=int(time.time())+SESSION_SECONDS))
    add_audit(db,"member.login",member.id,member.id)
    db.commit()
    return raw,member

def resolve_session(db: Session,raw: str | None) -> TeamMember | None:
    if not raw or len(raw) > 150:return None
    digest=hashlib.sha256(raw.encode()).hexdigest()
    record=db.get(TeamSession,digest)
    if record is None or record.revoked or record.expires_at<=int(time.time()):return None
    member=db.get(TeamMember,record.member_id)
    return member if member and member.active else None

def revoke_session(db: Session,raw: str,actor_id:str|None=None):
    digest=hashlib.sha256(raw.encode()).hexdigest()
    record=db.get(TeamSession,digest)
    if record:
        record.revoked=True
        add_audit(db,"member.logout",actor_id,record.member_id)
        db.commit()

def set_member_status(db:Session,member:TeamMember,*,active:bool|None=None,
                      role:str|None=None,actor_id:str):
    if role is not None and role not in ROLES:raise ValueError("Invalid role")
    if role is not None and role!=member.role or active is False and member.active:
        if member.role=="admin":
            active_admins=db.scalar(select(func.count()).select_from(TeamMember).where(
                TeamMember.role=="admin",TeamMember.active.is_(True))) or 0
            if active_admins<=1:raise ValueError("Cannot remove the last active admin")
    if active is not None:member.active=active
    if role is not None:member.role=role
    add_audit(db,"member.updated",actor_id,member.id,f"role={member.role} active={member.active}")
    db.commit()

def current_profile_version(db:Session) -> int:
    return db.scalar(select(func.max(TeamProfileRevision.version))) or 0

def save_team_profile(db:Session,payload:dict,actor_id:str,expected_version:int|None=None) -> int:
    # Use a database row lock to serialize profile writes on PostgreSQL.
    # SQLite serializes writes at the DB level; version comparison still covers normal UI conflicts.
    row=db.execute(select(Profile).where(Profile.id==1).with_for_update()).scalar_one_or_none()
    current=current_profile_version(db)
    if expected_version is not None and expected_version!=current:
        raise ValueError("Profile changed by another member; reload before saving")
    set_profile(db,payload,commit=False)
    version=current+1
    db.add(TeamProfileRevision(version=version,
                               profile_json=json.dumps(payload,ensure_ascii=False),
                               actor_id=actor_id))
    add_audit(db,"profile.updated",actor_id,"team-profile",f"v{version}")
    db.commit()
    return version
