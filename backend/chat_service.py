"""Private/team chat service with local message history and explicit AI triggers.

The database is the authoritative conversation store. Provider calls receive only
the selected conversation's recent messages; provider IDs never grant chat access.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.chat_models import ChatAICall, ChatConversation, ChatMember, ChatMessage
from backend.team import TeamMember


MAX_MESSAGE_CHARS = 8000
MAX_HISTORY_MESSAGES = 24
MAX_HISTORY_CHARS = 16000


class ChatServiceError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _now():
    return datetime.now(timezone.utc)


def _member(db: Session, conversation_id: str, member_id: str) -> ChatMember:
    row = db.get(ChatMember, (conversation_id, member_id))
    if row is None or row.left_at is not None:
        raise ChatServiceError(404, "Conversation not found")
    return row


def _conversation(db: Session, conversation_id: str, member_id: str, *, lock=False) -> ChatConversation:
    stmt = select(ChatConversation).where(ChatConversation.id == conversation_id)
    if lock:
        stmt = stmt.with_for_update()
    conv = db.scalar(stmt)
    if conv is None:
        raise ChatServiceError(404, "Conversation not found")
    _member(db, conversation_id, member_id)
    return conv


def _serialize_message(db: Session, row: ChatMessage, call_by_message: dict[str, ChatAICall] | None = None) -> dict:
    sender = db.get(TeamMember, row.sender_id) if row.sender_id else None
    call = (call_by_message or {}).get(row.id)
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "seq": row.seq,
        "sender_id": row.sender_id,
        "sender_name": sender.name if sender else ("Research Atlas" if row.role == "assistant" else "成员"),
        "role": row.role,
        "content": row.content,
        "trigger_type": row.trigger_type,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "ai_status": call.status if call else None,
        "ai_error": call.error if call else None,
    }


def _serialize_call(call: ChatAICall | None) -> dict | None:
    if call is None:
        return None
    try:
        usage = json.loads(call.usage_json or "{}")
    except ValueError:
        usage = {}
    return {
        "id": call.id,
        "status": call.status,
        "trigger_type": call.trigger_type,
        "provider": call.provider,
        "model": call.model,
        "usage": usage,
        "error": call.error,
    }


def list_conversations(db: Session, member_id: str, kind: str | None = None) -> list[dict]:
    stmt = (
        select(ChatConversation)
        .join(ChatMember, ChatMember.conversation_id == ChatConversation.id)
        .where(ChatMember.member_id == member_id, ChatMember.left_at.is_(None))
        .order_by(ChatConversation.updated_at.desc())
    )
    if kind:
        stmt = stmt.where(ChatConversation.kind == kind)
    rows = db.scalars(stmt).all()
    items = []
    for conv in rows:
        last = db.scalar(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv.id)
            .order_by(ChatMessage.seq.desc())
            .limit(1)
        )
        count = db.scalar(
            select(ChatMember.member_id).where(
                ChatMember.conversation_id == conv.id, ChatMember.left_at.is_(None)
            )
        )
        items.append({
            "id": conv.id,
            "kind": conv.kind,
            "title": conv.title,
            "owner_id": conv.owner_id,
            "last_seq": conv.last_seq,
            "last_message": (last.content[:120] if last else ""),
            "last_message_at": last.created_at.isoformat() if last and last.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "active": bool(conv.active_ai_call_id),
        })
    return items


def create_conversation(db: Session, actor: TeamMember, kind: str, title: str = "") -> dict:
    if kind not in ("private", "team"):
        raise ChatServiceError(422, "Conversation kind must be private or team")
    if kind == "team" and actor.role not in ("admin", "researcher"):
        raise ChatServiceError(403, "Only researchers and admins can create team conversations")
    conv = ChatConversation(
        id=str(uuid.uuid4()),
        kind=kind,
        title=(title.strip()[:180] or ("私人对话" if kind == "private" else "团队讨论")),
        owner_id=actor.id,
    )
    db.add(conv)
    db.flush()
    if kind == "private":
        db.add(ChatMember(conversation_id=conv.id, member_id=actor.id, role="owner"))
    else:
        members = db.scalars(select(TeamMember).where(TeamMember.active.is_(True))).all()
        for member in members:
            db.add(ChatMember(
                conversation_id=conv.id,
                member_id=member.id,
                role="owner" if member.id == actor.id else "member",
            ))
    db.commit()
    db.refresh(conv)
    return {
        "id": conv.id, "kind": conv.kind, "title": conv.title,
        "owner_id": conv.owner_id, "last_seq": conv.last_seq,
        "last_message": "", "last_message_at": None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "active": False,
    }


def add_conversation_member(db: Session, conversation_id: str, member_id: str) -> dict:
    conv = db.get(ChatConversation, conversation_id)
    member = db.get(TeamMember, member_id)
    if conv is None or conv.kind != "team":
        raise ChatServiceError(404, "Team conversation not found")
    if member is None or not member.active:
        raise ChatServiceError(404, "Active team member not found")
    existing = db.get(ChatMember, (conversation_id, member_id))
    if existing:
        if existing.left_at is not None:
            existing.left_at = None
            existing.joined_at = _now()
        db.commit()
        return {"added": True, "member_id": member_id}
    db.add(ChatMember(conversation_id=conversation_id, member_id=member_id, role="member"))
    db.commit()
    return {"added": True, "member_id": member_id}


def list_messages(db: Session, conversation_id: str, member_id: str,
                  after_seq: int = 0, limit: int = 100) -> list[dict]:
    _conversation(db, conversation_id, member_id)
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id, ChatMessage.seq > after_seq)
        .order_by(ChatMessage.seq.asc())
        .limit(max(1, min(limit, 200)))
    ).all()
    ids = [row.id for row in rows]
    calls = db.scalars(
        select(ChatAICall).where(ChatAICall.trigger_message_id.in_(ids))
    ).all() if ids else []
    call_map = {call.trigger_message_id: call for call in calls if call.trigger_message_id}
    return [_serialize_message(db, row, call_map) for row in rows]


def _build_history(db: Session, conv: ChatConversation, input_until_seq: int) -> list[dict[str, str]]:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv.id, ChatMessage.seq <= input_until_seq)
        .order_by(ChatMessage.seq.desc())
        .limit(MAX_HISTORY_MESSAGES)
    ).all()
    rows.reverse()
    history: list[dict[str, str]] = []
    total = 0
    for row in rows:
        if row.role not in ("user", "assistant"):
            continue
        content = row.content.strip()
        if row.role == "user" and conv.kind == "team" and row.sender_id:
            sender = db.get(TeamMember, row.sender_id)
            content = (sender.name if sender else "团队成员") + "： " + content
        content = content[:3000]
        if total + len(content) > MAX_HISTORY_CHARS:
            break
        history.append({"role": row.role, "content": content})
        total += len(content)
    system = (
        "你是 Research Atlas 的科研协作助手。使用中文回答，保持准确、清晰和诚实。"
        "区分已知事实、推断和假设；没有检索或核验时不要声称已经完成。"
        "不要编造论文、DOI、数据、实验结果或研究新颖性。用户需要系统科研发现时，"
        "建议通过平台的定向科研任务启动正式 Research Opportunity Skill。"
    )
    if conv.kind == "team":
        system += " 当前是团队共享会话，所有参与者都能看到本会话内容；尊重不同成员的发言归属。"
    return [{"role": "system", "content": system}, *history]


def _provider_reply(db: Session, history: list[dict[str, str]]) -> tuple[str, str, str, str, dict[str, int]]:
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        try:
            from openai import OpenAI
            model = os.getenv("CHAT_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
            client = OpenAI(api_key=openai_key, timeout=45, max_retries=0)
            response = client.chat.completions.create(
                model=model,
                messages=history,
                max_tokens=1200,
            )
            choice = response.choices[0]
            answer = choice.message.content or ""
            if not answer.strip():
                raise ChatServiceError(502, "模型返回了空回答")
            usage = response.usage
            tokens = {
                "input_tokens": int(usage.prompt_tokens) if usage else 0,
                "output_tokens": int(usage.completion_tokens) if usage else 0,
            }
            return answer.strip(), "openai", model, str(response.id or ""), tokens
        except ChatServiceError:
            raise
        except Exception:
            raise ChatServiceError(502, "OpenAI 对话请求失败，请检查模型配置或服务状态") from None

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-flash")
    if not deepseek_key:
        try:
            from backend.model_vault import ModelCredential, load_key
            config = db.get(ModelCredential, "deepseek")
            if config and config.encrypted_key:
                deepseek_key = load_key(db) or ""
                model = config.fast_model or model
        except Exception:
            deepseek_key = ""
    if not deepseek_key:
        raise ChatServiceError(
            503,
            "尚未配置对话模型。请在服务器配置 OPENAI_API_KEY，或在研究设置中保存可用的 DeepSeek API Key。",
        )
    try:
        with httpx.Client(timeout=45, follow_redirects=False) as client:
            response = client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": "Bearer " + deepseek_key, "Content-Type": "application/json"},
                json={"model": model, "messages": history, "max_tokens": 1200, "stream": False},
            )
            if response.status_code >= 400:
                raise ChatServiceError(502, f"DeepSeek 对话请求失败（HTTP {response.status_code}）")
            data = response.json()
        answer = data["choices"][0]["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ChatServiceError(502, "DeepSeek 返回了空回答")
        usage = data.get("usage") or {}
        tokens = {
            "input_tokens": max(0, int(usage.get("prompt_tokens") or 0)),
            "output_tokens": max(0, int(usage.get("completion_tokens") or 0)),
        }
        return answer.strip(), "deepseek", model, str(data.get("id") or ""), tokens
    except ChatServiceError:
        raise
    except httpx.RequestError:
        raise ChatServiceError(502, "DeepSeek 网络或超时错误") from None
    except (ValueError, KeyError, TypeError, IndexError):
        raise ChatServiceError(502, "DeepSeek 响应结构不符合预期") from None


def _run_ai_call(db: Session, conv: ChatConversation, actor_id: str,
                 trigger_type: str, idempotency_key: str,
                 trigger_message_id: str | None = None) -> dict:
    conv = _conversation(db, conv.id, actor_id, lock=True)
    existing = db.scalar(select(ChatAICall).where(
        ChatAICall.conversation_id == conv.id,
        ChatAICall.idempotency_key == idempotency_key,
    ))
    if existing:
        assistant = db.get(ChatMessage, existing.assistant_message_id) if existing.assistant_message_id else None
        return {"ai_call": _serialize_call(existing),
                "assistant_message": _serialize_message(db, assistant) if assistant else None}
    if conv.active_ai_call_id:
        raise ChatServiceError(409, "本会话已有 AI 请求正在执行，请稍后再试")
    has_user = db.scalar(select(ChatMessage.id).where(
        ChatMessage.conversation_id == conv.id,
        ChatMessage.role == "user",
        ChatMessage.seq <= conv.last_seq,
    ).limit(1))
    if not has_user:
        raise ChatServiceError(422, "请先发送一条消息，再请求 AI 回复")
    call = ChatAICall(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        trigger_message_id=trigger_message_id,
        trigger_type=trigger_type,
        idempotency_key=idempotency_key[:100],
        input_until_seq=conv.last_seq,
        status="running",
    )
    db.add(call)
    conv.active_ai_call_id = call.id
    db.commit()
    history = _build_history(db, conv, call.input_until_seq)
    try:
        answer, provider, model, response_id, usage = _provider_reply(db, history)
        conv = _conversation(db, conv.id, actor_id, lock=True)
        call = db.get(ChatAICall, call.id)
        assistant = ChatMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            seq=conv.last_seq + 1,
            sender_id=None,
            role="assistant",
            content=answer,
        )
        db.add(assistant)
        conv.last_seq += 1
        conv.last_ai_synced_seq = call.input_until_seq
        conv.active_ai_call_id = ""
        conv.updated_at = _now()
        call.assistant_message_id = assistant.id
        call.status = "completed"
        call.provider = provider
        call.model = model
        call.provider_response_id = response_id[:160]
        call.usage_json = json.dumps(usage, ensure_ascii=False)
        call.completed_at = _now()
        db.commit()
        db.refresh(assistant)
        return {"ai_call": _serialize_call(call), "assistant_message": _serialize_message(db, assistant)}
    except ChatServiceError as exc:
        conv = db.get(ChatConversation, conv.id)
        call = db.get(ChatAICall, call.id)
        call.status = "failed"
        call.error = str(exc)[:500]
        call.completed_at = _now()
        if conv and conv.active_ai_call_id == call.id:
            conv.active_ai_call_id = ""
        db.commit()
        return {"ai_call": _serialize_call(call), "assistant_message": None}
    except Exception:
        conv = db.get(ChatConversation, conv.id)
        call = db.get(ChatAICall, call.id)
        call.status = "failed"
        call.error = "AI provider request failed"
        call.completed_at = _now()
        if conv and conv.active_ai_call_id == call.id:
            conv.active_ai_call_id = ""
        db.commit()
        return {"ai_call": _serialize_call(call), "assistant_message": None}


def send_message(db: Session, conversation_id: str, actor: TeamMember,
                 content: str, client_nonce: str, trigger_ai: bool = False,
                 trigger_type: str = "") -> dict:
    text = content.strip()
    if not text or len(text) > MAX_MESSAGE_CHARS:
        raise ChatServiceError(422, "消息不能为空，且不能超过 8000 个字符")
    if not client_nonce or len(client_nonce) > 80:
        raise ChatServiceError(422, "缺少有效的消息幂等标识")
    conv = _conversation(db, conversation_id, actor.id, lock=True)
    duplicate = db.scalar(select(ChatMessage).where(
        ChatMessage.conversation_id == conv.id,
        ChatMessage.client_nonce == client_nonce,
    ))
    if duplicate:
        call = db.scalar(select(ChatAICall).where(ChatAICall.trigger_message_id == duplicate.id))
        assistant = db.get(ChatMessage, call.assistant_message_id) if call and call.assistant_message_id else None
        return {
            "user_message": _serialize_message(db, duplicate, {duplicate.id: call} if call else {}),
            "assistant_message": _serialize_message(db, assistant) if assistant else None,
            "ai_call": _serialize_call(call),
        }
    should_call = conv.kind == "private" or bool(trigger_ai)
    effective_trigger = "private" if conv.kind == "private" else trigger_type
    if conv.kind == "team" and trigger_ai and effective_trigger not in ("mention", "manual"):
        raise ChatServiceError(422, "团队会话只能通过真实 @GPT 提及或 AI 回复操作触发模型")
    if should_call and conv.active_ai_call_id:
        raise ChatServiceError(409, "本会话已有 AI 请求正在执行，请稍后再试")
    message = ChatMessage(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        seq=conv.last_seq + 1,
        sender_id=actor.id,
        role="user",
        content=text,
        trigger_type=effective_trigger if should_call else "",
        client_nonce=client_nonce,
    )
    db.add(message)
    conv.last_seq += 1
    if conv.title in ("新对话", "私人对话", "团队讨论"):
        conv.title = text[:48]
    conv.updated_at = _now()
    db.commit()
    db.refresh(message)
    if not should_call:
        return {"user_message": _serialize_message(db, message),
                "assistant_message": None, "ai_call": None}
    result = _run_ai_call(
        db, conv, actor.id, effective_trigger,
        "message:" + client_nonce, trigger_message_id=message.id,
    )
    return {
        "user_message": _serialize_message(db, message, {
            message.id: db.scalar(select(ChatAICall).where(ChatAICall.trigger_message_id == message.id))
        }),
        "assistant_message": result.get("assistant_message"),
        "ai_call": result.get("ai_call"),
    }


def request_ai_reply(db: Session, conversation_id: str, actor: TeamMember,
                     idempotency_key: str) -> dict:
    if not idempotency_key or len(idempotency_key) > 100:
        raise ChatServiceError(422, "缺少有效的 AI 请求幂等标识")
    conv = _conversation(db, conversation_id, actor.id, lock=True)
    if conv.kind != "team":
        raise ChatServiceError(422, "私人会话发送消息时会自动请求 AI")
    result = _run_ai_call(
        db, conv, actor.id, "manual", "manual:" + idempotency_key,
    )
    return result
