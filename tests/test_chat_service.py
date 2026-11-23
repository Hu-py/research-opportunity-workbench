import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from research_workbench.core import Base
from backend.team import TeamMember
from backend import chat_models  # noqa: F401
from backend import chat_service


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def add_member(db, name):
    member = TeamMember(
        id=str(uuid.uuid4()), email=f"{name.lower()}-{uuid.uuid4().hex[:6]}@example.test",
        name=name, password_hash="test-hash", role="researcher", active=True,
    )
    db.add(member)
    db.commit()
    return member


def fake_provider(_db, history):
    assert history[0]["role"] == "system"
    return "已收到，我会区分事实与假设。", "fake", "fake-model", "resp-1", {
        "input_tokens": 12, "output_tokens": 9,
    }


def test_private_conversation_persists_and_calls_ai(db, monkeypatch):
    monkeypatch.setattr(chat_service, "_provider_reply", fake_provider)
    member = add_member(db, "Alice")
    conversation = chat_service.create_conversation(db, member, "private")
    result = chat_service.send_message(
        db, conversation["id"], member, "请帮我分析这个研究问题",
        "private-nonce-0001",
    )
    assert result["user_message"]["content"] == "请帮我分析这个研究问题"
    assert result["assistant_message"]["content"].startswith("已收到")
    assert result["ai_call"]["status"] == "completed"
    messages = chat_service.list_messages(db, conversation["id"], member.id)
    assert [item["role"] for item in messages] == ["user", "assistant"]


def test_team_message_does_not_call_ai_without_explicit_trigger(db, monkeypatch):
    calls = []
    monkeypatch.setattr(chat_service, "_provider_reply", lambda *args: calls.append(args) or fake_provider(*args))
    owner = add_member(db, "Owner")
    colleague = add_member(db, "Colleague")
    conversation = chat_service.create_conversation(db, owner, "team")
    result = chat_service.send_message(
        db, conversation["id"], owner, "我认为需要先检查研究假设",
        "team-nonce-0001", trigger_ai=False,
    )
    assert result["ai_call"] is None
    assert result["assistant_message"] is None
    assert calls == []
    visible = chat_service.list_messages(db, conversation["id"], colleague.id)
    assert len(visible) == 1
    assert visible[0]["sender_name"] == "Owner"


def test_team_at_gpt_triggers_ai_and_private_chat_isolated(db, monkeypatch):
    monkeypatch.setattr(chat_service, "_provider_reply", fake_provider)
    owner = add_member(db, "Owner")
    conversation = chat_service.create_conversation(db, owner, "team")
    outsider = add_member(db, "Outsider")
    result = chat_service.send_message(
        db, conversation["id"], owner, "请 GPT 帮忙整理刚才的讨论",
        "team-nonce-0002", trigger_ai=True, trigger_type="mention",
    )
    assert result["ai_call"]["status"] == "completed"
    assert result["user_message"]["trigger_type"] == "mention"
    with pytest.raises(chat_service.ChatServiceError) as exc:
        chat_service.list_messages(db, conversation["id"], outsider.id)
    assert exc.value.status_code == 404


def test_private_message_nonce_is_idempotent(db, monkeypatch):
    calls = []
    monkeypatch.setattr(chat_service, "_provider_reply", lambda *args: calls.append(1) or fake_provider(*args))
    member = add_member(db, "Alice")
    conversation = chat_service.create_conversation(db, member, "private")
    first = chat_service.send_message(db, conversation["id"], member, "同一条消息", "nonce-retry-001")
    second = chat_service.send_message(db, conversation["id"], member, "同一条消息", "nonce-retry-001")
    assert first["user_message"]["id"] == second["user_message"]["id"]
    assert first["assistant_message"]["id"] == second["assistant_message"]["id"]
    assert len(calls) == 1


def test_new_team_member_is_added_to_existing_team_conversation(db):
    owner = add_member(db, "Owner")
    conversation = chat_service.create_conversation(db, owner, "team")
    new_member = add_member(db, "NewMember")
    chat_service.add_conversation_member(db, conversation["id"], new_member.id)
    assert chat_service.list_messages(db, conversation["id"], new_member.id) == []


def test_stale_ai_lock_is_recovered_and_new_private_message_completes(db, monkeypatch):
    monkeypatch.setattr(chat_service, "_provider_reply", fake_provider)
    member = add_member(db, "Alice")
    conversation = chat_service.create_conversation(db, member, "private")
    conv = db.get(chat_models.ChatConversation, conversation["id"])
    old_user = chat_models.ChatMessage(
        id=str(uuid.uuid4()), conversation_id=conv.id, seq=1, sender_id=member.id,
        role="user", content="上一次请求", client_nonce="stale-user-nonce",
    )
    stale_call = chat_models.ChatAICall(
        id=str(uuid.uuid4()), conversation_id=conv.id, trigger_message_id=old_user.id,
        trigger_type="private", idempotency_key="message:stale-user-nonce",
        input_until_seq=1, status="running",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    db.add(old_user)
    db.add(stale_call)
    conv.last_seq = 1
    conv.active_ai_call_id = stale_call.id
    db.commit()

    result = chat_service.send_message(
        db, conv.id, member, "现在再测试", "fresh-user-nonce-001"
    )
    db.refresh(stale_call)
    db.refresh(conv)
    assert stale_call.status == "failed"
    assert conv.active_ai_call_id == ""
    assert result["assistant_message"]["content"].startswith("已收到")
    assert result["ai_call"]["status"] == "completed"

def test_private_chat_receives_own_profile_and_shared_team_profile(db, monkeypatch):
    member = add_member(db, "Alice")
    conversation = chat_service.create_conversation(db, member, "private")
    monkeypatch.setattr(chat_service, "get_shared_team_profile", lambda _db: {"research_lines": [{"name": "Team line"}]})
    monkeypatch.setattr(chat_service, "read_personal_profile", lambda _db, member_id: {"profile": {"research_lines": [{"name": "My line"}]}})
    monkeypatch.setattr(chat_service, "list_personal_assets", lambda _db, member_id, **kwargs: [{"kind": "report", "title": "My private report", "summary": "Private summary", "url": "https://example.test/report", "line_ids": ["line-1"]}])
    history = chat_service._build_history(db, db.get(chat_models.ChatConversation, conversation["id"]), 0, member.id)
    system = history[0]["content"]
    assert "Team line" in system
    assert "My line" in system
    assert "My private report" in system


def test_team_chat_receives_shared_profile_but_never_personal_profile_or_assets(db, monkeypatch):
    owner = add_member(db, "Owner")
    conversation = chat_service.create_conversation(db, owner, "team")
    monkeypatch.setattr(chat_service, "get_shared_team_profile", lambda _db: {"research_lines": [{"name": "Team line"}]})
    def forbidden_personal(*args, **kwargs):
        raise AssertionError("team chat must not read personal profiles or assets")
    monkeypatch.setattr(chat_service, "read_personal_profile", forbidden_personal)
    monkeypatch.setattr(chat_service, "list_personal_assets", forbidden_personal)
    history = chat_service._build_history(db, db.get(chat_models.ChatConversation, conversation["id"]), 0, owner.id)
    system = history[0]["content"]
    assert "Team line" in system
    assert "当前用户的个人科研档案" not in system
    assert "个人科研资料库" not in system