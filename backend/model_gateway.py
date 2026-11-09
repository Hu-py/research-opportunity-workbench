"""Small, replaceable DeepSeek adapter: JSON-only calls, explicit token tracking.

Only data selected by the orchestrator goes to the provider. This module
never logs prompt data, API credentials, or provider response bodies.
"""
from __future__ import annotations
import json
from typing import Any
import httpx

DEEPSEEK_URL="https://api.deepseek.com/chat/completions"

class ModelCallError(Exception):
    pass

def _error(exc):
    if isinstance(exc,httpx.TimeoutException):return "DeepSeek 请求超时；可从已保存的阶段继续"
    if isinstance(exc,httpx.TransportError):return "DeepSeek 网络连接失败；请检查 Render 网络"
    if isinstance(exc,httpx.HTTPStatusError):
        code=exc.response.status_code
        hints={401:"密钥无效",402:"账户余额不足",403:"密钥权限不足",
               429:"超过服务限流",400:"请求或模型参数不兼容",
               422:"请求格式不符合要求"}
        return "DeepSeek HTTP "+str(code)+"："+hints.get(code,"请求失败，请查看 DeepSeek 服务状态")
    return "模型返回或验证失败："+type(exc).__name__

def request_json(api_key,model,system,payload,client=None,max_tokens=2000,on_usage=None):
    """Return (strict JSON object, token usage), never a plain free-form answer."""
    if model not in ("deepseek-flash","deepseek-v4-pro"):
        raise ModelCallError("模型类型不在许可列表中")
    http=client or httpx.Client(timeout=75.0,follow_redirects=False)
    close=client is None
    try:
        response=http.post(DEEPSEEK_URL,headers={
            "Authorization":"Bearer "+api_key,"Content-Type":"application/json"},
            json={"model":model,
                  "messages":[{"role":"system","content":system+
                               "\n只输出一个有效的 JSON 对象，不要 Markdown 或其他文字。"},
                              {"role":"user","content":json.dumps(payload,ensure_ascii=False)}],
                  "response_format":{"type":"json_object"},
                  "thinking":{"type":"disabled"},
                  "max_tokens":max_tokens,
                  "stream":False})
        response.raise_for_status()
        raw=response.json()
        if on_usage is not None:
            observed_usage = raw.get("usage") or {}
            on_usage({"input_tokens": max(0, int(observed_usage.get("prompt_tokens") or 0)),
                      "output_tokens": max(0, int(observed_usage.get("completion_tokens") or 0))})
        options=raw.get("choices") or []
        if not options:raise ModelCallError("DeepSeek 返回了空的模型结果")
        choice=options[0]
        if choice.get("finish_reason")=="length":
            raise ModelCallError("模型输出被截断，请降低单次输入或调大输出预算")
        content=(choice.get("message") or {}).get("content") or ""
        if not content.strip():
            raise ModelCallError("模型返回空内容，请重试或调整模型配置")
        try:
            parsed=json.loads(content)
        except (ValueError,TypeError) as exc:
            raise ModelCallError("模型未返回有效 JSON") from exc
        if not isinstance(parsed,dict):
            raise ModelCallError("模型输出必须是 JSON 对象")
        usage=raw.get("usage") or {}
        return parsed,{"input_tokens":max(0,int(usage.get("prompt_tokens") or 0)),
                       "output_tokens":max(0,int(usage.get("completion_tokens") or 0))}
    except httpx.HTTPError as exc:
        raise ModelCallError(_error(exc)) from exc
    except (ValueError,KeyError,TypeError) as exc:
        raise ModelCallError("模型响应格式异常") from exc
    finally:
        if close:http.close()
