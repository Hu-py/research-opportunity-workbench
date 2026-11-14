"""Low-cost DeepSeek multi-turn probe, without server-side conversation assumptions.

The caller owns history and should persist it in the app database. This adapter
never logs prompts, model output or credentials; it is not a chat database.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import httpx

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-flash"
MAX_MESSAGES = 24
MAX_HISTORY_CHARS = 12000
SYSTEM = "你是 Research Atlas 的简洁对话助手。遵循已给出的多轮对话历史。"


class ChatProbeError(Exception):
    """Provider or input failure with a message safe for users/logs."""


def _validate_history(history: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    if not 1 <= len(history) <= MAX_MESSAGES:
        raise ChatProbeError("实验仅支持 1-24 条历史消息")
    result = []
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
            raise ChatProbeError("消息仅支持非空的 user/assistant 文本")
        if len(content) > 2000:
            raise ChatProbeError("单条消息超过实验长度限制")
        result.append({"role": role, "content": content})
    if result[-1]["role"] != "user" or sum(len(x["content"]) for x in result) > MAX_HISTORY_CHARS:
        raise ChatProbeError("对话历史长度或最后一条消息不合法")
    return result


def chat_turn(*, api_key: str, history: Sequence[Mapping[str, str]],
              client: httpx.Client | None = None, max_tokens: int = 96) -> tuple[str, dict[str, int]]:
    """Return (assistant text, token usage); append both sides before next turn."""
    if not api_key or not api_key.strip():
        raise ChatProbeError("未找到 DeepSeek API Key")
    if not 1 <= max_tokens <= 256:
        raise ChatProbeError("实验输出上限必须在 1-256 tokens")
    messages = [{"role": "system", "content": SYSTEM}, *_validate_history(history)]
    own = client is None
    http = client or httpx.Client(timeout=45, follow_redirects=False)
    try:
        response = http.post(API_URL, headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        }, json={"model": MODEL, "messages": messages, "thinking": {"type": "disabled"},
                 "max_tokens": max_tokens, "stream": False})
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        answer = choice["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ChatProbeError("模型返回了空文本")
        if choice.get("finish_reason") == "length":
            raise ChatProbeError("模型回答超过本次实验输出上限")
        usage = data.get("usage") or {}
        return answer, {
            "input_tokens": max(0, int(usage.get("prompt_tokens") or 0)),
            "output_tokens": max(0, int(usage.get("completion_tokens") or 0)),
        }
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        raise ChatProbeError(f"DeepSeek HTTP {code}（请检查密钥、余额或请求参数）") from None
    except httpx.RequestError:
        raise ChatProbeError("DeepSeek 网络或超时错误") from None
    except (ValueError, KeyError, TypeError, IndexError):
        raise ChatProbeError("DeepSeek 响应结构不符合预期") from None
    finally:
        if own:
            http.close()
