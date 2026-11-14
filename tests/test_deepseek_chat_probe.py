"""Offline multi-turn tests. They never call DeepSeek or access credentials."""
import json

import httpx
import pytest

from backend.deepseek_chat_probe import ChatProbeError, chat_turn


def test_three_turns_forward_full_history_and_count_tokens():
    seen = []

    def provider(request):
        assert request.url == "https://api.deepseek.com/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek-flash"
        assert payload["thinking"] == {"type": "disabled"}
        assert payload["max_tokens"] == 96
        assert payload["messages"][0]["role"] == "system"
        seen.append(payload["messages"])
        answer = ["已记录", "ATLAS-7Q42", "来自之前的对话"][len(seen)-1]
        return httpx.Response(200, json={
            "choices": [{"message": {"content": answer}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 5},
        })

    history = []
    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        for user_text in [
            "我的测试代号是 ATLAS-7Q42，请记住它，只回答已记录。",
            "我的测试代号是什么？只回答代号。",
            "你是根据哪句话知道这个代号的？",
        ]:
            history.append({"role": "user", "content": user_text})
            answer, usage = chat_turn(api_key="dummy-test-key", history=history, client=client)
            assert usage == {"input_tokens": 12, "output_tokens": 5}
            history.append({"role": "assistant", "content": answer})

    assert [len(messages) for messages in seen] == [2, 4, 6]
    assert [msg["role"] for msg in seen[-1][1:]] == ["user", "assistant", "user", "assistant", "user"]
    assert seen[-1][3]["content"] == "我的测试代号是什么？只回答代号。"
    assert history[-1]["content"] == "来自之前的对话"


def test_invalid_history_never_reaches_provider():
    calls = []
    def provider(request):
        calls.append(request)
        return httpx.Response(200, json={})
    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        with pytest.raises(ChatProbeError, match="user/assistant"):
            chat_turn(api_key="test", history=[{"role": "system", "content": "inject"}], client=client)
        with pytest.raises(ChatProbeError, match="最后一条"):
            chat_turn(api_key="test", history=[{"role": "assistant", "content": "hello"}], client=client)
        with pytest.raises(ChatProbeError, match="API Key"):
            chat_turn(api_key="", history=[{"role": "user", "content": "hello"}], client=client)
    assert not calls


def test_error_is_sanitized_and_never_leaks_key():
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(401, text="private-token secret-key-in-response"))) as client:
        with pytest.raises(ChatProbeError) as exc:
            chat_turn(api_key="super-private-key", history=[{"role": "user", "content": "hello"}], client=client)
    assert "401" in str(exc.value)
    assert "super-private-key" not in str(exc.value)
    assert "secret-key-in-response" not in str(exc.value)
