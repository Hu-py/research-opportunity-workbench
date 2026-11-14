"""Email-verified Owner claim, member invitations and password recovery.

Uses the existing team identities and database; never returns setup tokens in API
responses or stores plaintext tokens. Mail transport is fail-closed.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import smtplib
import ssl
import time
import uuid
from email.message import EmailMessage
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, select, func, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from research_workbench.core import Base
from backend.team import (
    AuditEntry, PASSWORD, TeamMember, TeamSession, add_audit,
    normalize_email, timestamp,
)

OWNER_EMAIL_ENV = "TEAM_OWNER_EMAIL"
OWNER_FLAG_ENV = "TEAM_OWNER_SETUP_ENABLED"
TICKET_TTL = {"owner": 1800, "invite": 7 * 86400, "reset": 1800}
COOLDOWN = 90


class OwnerClaim(Base):
    """Singleton serializes Owner promotion on PostgreSQL."""
    __tablename__ = "team_owner_claim"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    member_id: Mapped[str] = mapped_column(String(36), default="")
    claimed_at: Mapped[int] = mapped_column(Integer, default=0)


class EnrollmentTicket(Base):
    __tablename__ = "team_enrollment_tickets"
    token_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(12), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(140), default="")
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    issued_by: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer)
    used_at: Mapped[int] = mapped_column(Integer, default=0)
    revoked_at: Mapped[int] = mapped_column(Integer, default=0)


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class InvitationRequest(EmailRequest):
    name: str = Field(min_length=2, max_length=140)
    role: str = Field(pattern="^(admin|researcher|viewer)$")


class RedeemRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=256)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _app_url() -> str:
    base = os.getenv("PUBLIC_APP_URL", "").rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("PUBLIC_APP_URL must be an HTTPS URL without credentials or query")
    return base


def _send_email(to_address: str, title: str, token: str, kind: str) -> None:
    """SMTP TLS transport; mail is sent only to the prevalidated recipient."""
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        raise RuntimeError("SMTP provider not configured")
    # Fragment prevents browsers and reverse proxies from logging setup tokens in URLs.
    href = _app_url() + "/account/setup#token=" + token
    label = {"owner": "Owner 初始化", "invite": "团队邀请", "reset": "密码重置"}[kind]
    msg = EmailMessage()
    msg["Subject"] = "Research Atlas - " + title
    msg["From"] = sender
    msg["To"] = to_address
    msg.set_content(
        "Research Atlas " + label + "\n\n"
        "请在有效期内使用下方链接设置密码：\n" + href +
        "\n\n如果不是你本人发起，请忽略此邮件。"
    )
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    if user and not password:
        raise RuntimeError("SMTP authentication is incomplete")
    context = ssl.create_default_context()
    if os.getenv("SMTP_USE_SSL", "true").lower() in ("1", "true", "yes"):
        with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as client:
            if user:
                client.login(user, password)
            client.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as client:
            client.starttls(context=context)
            if user:
                client.login(user, password)
            client.send_message(msg)


def _issue(
    db: Session, kind: str, email: str, name: str, role: str,
    issuer: str = "",
) -> bool:
    now = int(time.time())
    most_recent = db.scalar(
        select(EnrollmentTicket.created_at)
        .where(
            EnrollmentTicket.email == email,
            EnrollmentTicket.kind == kind,
        )
        .order_by(EnrollmentTicket.created_at.desc())
        .limit(1)
    )
    if most_recent is not None and now - most_recent < COOLDOWN:
        return False
    # Validate the provider and app URL before persisting the ticket.
    if not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM"):
        raise HTTPException(503, "邮件发送尚未配置，请联系平台管理员")
    try:
        _app_url()
    except RuntimeError as exc:
        raise HTTPException(503, "平台邮件链接配置无效") from exc
    token = secrets.token_urlsafe(48)
    ticket = EnrollmentTicket(
        token_sha256=_digest(token), kind=kind, email=email,
        name=name.strip(), role=role, issued_by=issuer,
        created_at=now, expires_at=now + TICKET_TTL[kind], used_at=0,
    )
    db.add(ticket)
    db.commit()
    try:
        _send_email(email, {"owner": "Owner 身份验证", "invite": "成员邀请", "reset": "重置密码"}[kind], token, kind)
    except (OSError, smtplib.SMTPException, RuntimeError, ValueError):
        ticket.used_at = now
        db.commit()
        raise HTTPException(503, "邮件发送失败，请检查 SMTP 配置后重试")
    add_audit(db, "account.ticket.sent", issuer or None, kind, note="recipient=" + email)
    db.commit()
    return True


def _singleton(db: Session) -> OwnerClaim:
    claim = db.get(OwnerClaim, 1)
    if claim is None:
        claim = OwnerClaim(id=1, member_id="", claimed_at=0)
        db.add(claim)
        db.commit()
    return claim


def mount(app, *, get_db, authenticate, require_actor, require_admin, team_auth_enabled):
    router = APIRouter()

    @router.post("/api/account/owner/request", status_code=202, dependencies=[Depends(authenticate)])
    def owner_request(data: EmailRequest, db: Session = Depends(get_db)):
        # Server-side API_BEARER_TOKEN remains enforced at the Next proxy.
        if not team_auth_enabled() or os.getenv(OWNER_FLAG_ENV, "").lower() not in ("1", "true", "yes"):
            raise HTTPException(404, "Owner setup unavailable")
        expected = os.getenv(OWNER_EMAIL_ENV, "")
        if not expected:
            raise HTTPException(503, "TEAM_OWNER_EMAIL 尚未配置")
        try:
            wanted = normalize_email(expected)
            supplied = normalize_email(data.email)
        except ValueError:
            raise HTTPException(422, "邮箱格式无效")
        _singleton(db)
        claim = db.execute(select(OwnerClaim).where(OwnerClaim.id == 1).with_for_update()).scalar_one()
        if claim.member_id:
            raise HTTPException(409, "Owner 已经完成初始化")
        if supplied == wanted:
            _issue(db, "owner", wanted, "Research Atlas Owner", "owner")
        return {"ok": True, "message": "如果邮箱匹配预设 Owner，验证邮件将发送至该邮箱"}

    @router.post("/api/account/reset/request", status_code=202, dependencies=[Depends(authenticate)])
    def reset_request(data: EmailRequest, db: Session = Depends(get_db)):
        if not team_auth_enabled():
            raise HTTPException(404, "Team auth disabled")
        try:
            email = normalize_email(data.email)
        except ValueError:
            raise HTTPException(422, "邮箱格式无效")
        member = db.scalar(select(TeamMember).where(
            TeamMember.email == email, TeamMember.active.is_(True)
        ))
        if member:
            _issue(db, "reset", email, member.name, member.role, member.id)
        return {"ok": True, "message": "如果账号存在，将发送重置密码邮件"}

    @router.post("/api/account/setup/redeem", dependencies=[Depends(authenticate)])
    def redeem(data: RedeemRequest, db: Session = Depends(get_db)):
        if not team_auth_enabled():
            raise HTTPException(404, "Team auth disabled")
        ticket = db.execute(
            select(EnrollmentTicket)
            .where(EnrollmentTicket.token_sha256 == _digest(data.token))
            .with_for_update()
        ).scalar_one_or_none()
        now = int(time.time())
        if ticket is None or ticket.used_at or ticket.revoked_at or ticket.expires_at <= now:
            raise HTTPException(410, "链接无效或已过期")
        if ticket.kind == "owner":
            claim = db.execute(select(OwnerClaim).where(OwnerClaim.id == 1).with_for_update()).scalar_one_or_none()
            if claim is None or claim.member_id or os.getenv(OWNER_FLAG_ENV, "").lower() not in ("1","true","yes"):
                raise HTTPException(409, "Owner 认领已关闭")
            expected = os.getenv(OWNER_EMAIL_ENV, "").strip().lower()
            if ticket.email != expected:
                raise HTTPException(409, "Owner 邮箱已更改")
            member = db.scalar(select(TeamMember).where(TeamMember.email == ticket.email))
            if member is None:
                member = TeamMember(
                    id=str(uuid.uuid4()), email=ticket.email, name=ticket.name,
                    password_hash=PASSWORD.hash(data.password), role="owner", active=True
                )
                db.add(member)
            else:
                member.password_hash = PASSWORD.hash(data.password)
                member.role = "owner"
                member.active = True
                db.execute(update(TeamSession).where(TeamSession.member_id == member.id).values(revoked=True))
            claim.member_id = member.id
            claim.claimed_at = now
            add_audit(db, "owner.claimed", member.id, member.id)
        elif ticket.kind == "invite":
            existing = db.scalar(select(TeamMember.id).where(TeamMember.email == ticket.email))
            if existing:
                raise HTTPException(409, "账号已经存在，不能重复接受邀请")
            member = TeamMember(
                id=str(uuid.uuid4()), email=ticket.email, name=ticket.name,
                password_hash=PASSWORD.hash(data.password), role=ticket.role, active=True,
            )
            db.add(member)
            add_audit(db, "member.invitation.accepted", member.id, ticket.email,
                      note="invited_by=" + ticket.issued_by)
        elif ticket.kind == "reset":
            member = db.scalar(select(TeamMember).where(
                TeamMember.email == ticket.email, TeamMember.active.is_(True)
            ))
            if member is None:
                raise HTTPException(410, "账号已失效")
            member.password_hash = PASSWORD.hash(data.password)
            db.execute(update(TeamSession).where(TeamSession.member_id == member.id).values(revoked=True))
            add_audit(db, "member.password.reset", member.id, member.id)
        else:
            raise HTTPException(422, "未知验证类型")
        ticket.used_at = now
        # Invalidate any other unused tickets of the same type for that email.
        db.execute(update(EnrollmentTicket)
                   .where(EnrollmentTicket.email == ticket.email,
                          EnrollmentTicket.kind == ticket.kind,
                          EnrollmentTicket.used_at == 0)
                   .values(used_at=now))
        db.commit()
        return {"ok": True, "message": "验证完成，请使用邮箱和新密码登录"}

    @router.get("/api/team/invitations")
    def list_invitations(actor: TeamMember = Depends(require_admin), db: Session = Depends(get_db)):
        tickets = db.scalars(
            select(EnrollmentTicket).where(EnrollmentTicket.kind == "invite")
            .order_by(EnrollmentTicket.created_at.desc()).limit(100)
        ).all()
        return {"items": [{
            "id": x.token_sha256[:12],
            "email": x.email,
            "name": x.name,
            "role": x.role,
            "status": "revoked" if x.revoked_at else ("used" if x.used_at else ("expired" if x.expires_at <= int(time.time()) else "pending")),
            "expires_at": x.expires_at,
        } for x in tickets]}

    @router.post("/api/team/invitations", status_code=202)
    def invite(data: InvitationRequest, actor: TeamMember = Depends(require_admin),
               db: Session = Depends(get_db)):
        if not team_auth_enabled():
            raise HTTPException(404, "Team auth disabled")
        if data.role == "admin" and actor.role != "owner":
            raise HTTPException(403, "只有 Owner 可以邀请管理员")
        try:
            email = normalize_email(data.email)
        except ValueError:
            raise HTTPException(422, "邮箱格式无效")
        if db.scalar(select(TeamMember.id).where(TeamMember.email == email)):
            raise HTTPException(409, "账号已经存在")
        sent = _issue(db, "invite", email, data.name, data.role, actor.id)
        return {"ok": True, "sent": sent, "message": "邀请邮件已发送" if sent else "最近已发送邀请，请稍后再试"}

    @router.post("/api/team/invitations/{ticket_id}/revoke")
    def revoke_invitation(ticket_id: str, actor: TeamMember = Depends(require_admin),
                          db: Session = Depends(get_db)):
        if len(ticket_id) != 12 or any(c not in "0123456789abcdef" for c in ticket_id):
            raise HTTPException(404, "邀请不存在")
        item = db.scalar(
            select(EnrollmentTicket).where(
                EnrollmentTicket.kind == "invite",
                EnrollmentTicket.token_sha256.like(ticket_id + "%")
            ).with_for_update()
        )
        if item is None:
            raise HTTPException(404, "邀请不存在")
        if actor.role != "owner" and item.issued_by != actor.id:
            raise HTTPException(403, "只能撤销本人发出的邀请")
        if item.used_at or item.revoked_at:
            raise HTTPException(409, "邀请已经结束")
        item.revoked_at = int(time.time())
        add_audit(db, "member.invitation.revoked", actor.id, item.email)
        db.commit()
        return {"ok": True}

    app.include_router(router)
