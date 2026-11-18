"""Offline tests for the DeepSeek JSON adapter."""
import pytest

from backend.model_gateway import ModelCallError, request_json


class FakeResponse:
    def __init__(self, content):
        self.content=content
        self.status_code=200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices":[{"finish_reason":"stop","message":{"content":self.content}}],
            "usage":{"prompt_tokens":12,"completion_tokens":7},
        }


class FakeClient:
    def __init__(self, content):
        self.content=content

    def post(self, *args, **kwargs):
        return FakeResponse(self.content)


@pytest.mark.parametrize("content",[
    '{"ok":true,"count":2}',
    'Here is the result:\n```json\n{"ok":true,"count":2}\n```',
    '{"ok":true,"message":"comma,} remains inside string",}',
])
def test_request_json_parses_wrapped_or_trailing_comma_objects(content):
    parsed,usage=request_json(
        "test-key","deepseek-flash","system",{"stage":"test"},
        client=FakeClient(content),max_tokens=64,
    )
    assert parsed["ok"] is True
    assert usage=={"input_tokens":12,"output_tokens":7}


def test_request_json_rejects_non_json_content():
    with pytest.raises(ModelCallError,match="模型未返回有效 JSON"):
        request_json(
            "test-key","deepseek-flash","system",{"stage":"test"},
            client=FakeClient("This is not JSON"),max_tokens=64,
        )


@pytest.mark.parametrize("provider_message,reason",[
    ("The input exceeds the maximum context length","上下文长度超限"),
    ("Content Exists Risk","内容审核拒绝"),
    ("Unsupported parameter 'thinking'","模型请求参数不兼容"),
])
def test_deepseek_400_has_sanitized_error_class_without_upstream_payload(provider_message,reason):
    import httpx
    request=httpx.Request("POST","https://api.deepseek.com/chat/completions")
    response=httpx.Response(400,request=request,json={
        "error":{"message":provider_message+" private-paper-token",
                 "code":"invalid_request_error"},
    })
    class BadClient:
        def post(self,*args,**kwargs):
            return response
    with pytest.raises(ModelCallError) as failure:
        request_json("do-not-leak-key","deepseek-flash","test",
                     {"private":"private-paper-token"},client=BadClient())
    assert reason in str(failure.value)
    assert "private-paper-token" not in str(failure.value)
    assert "do-not-leak-key" not in str(failure.value)


def test_plain_text_fallback_keeps_strict_json_parser_and_omits_provider_json_mode():
    captured=[]
    class CapturingClient:
        def post(self,*args,**kwargs):
            captured.append(kwargs["json"])
            return FakeResponse('{"ok":true,"count":1}')
    client=CapturingClient()
    parsed,usage=request_json(
        "dummy","deepseek-flash","Produce JSON",{"task":"verification"},
        client=client,response_mode="plain_text")
    assert parsed["ok"] is True
    assert "response_format" not in captured[0]
    assert captured[0]["thinking"]=={"type":"disabled"}
    request_json("dummy","deepseek-flash","Produce JSON",{"task":"verification"},
                 client=client)
    assert captured[1]["response_format"]=={"type":"json_object"}


def test_unsupported_provider_response_mode_rejected_without_model_call():
    with pytest.raises(ModelCallError,match="不支持的模型响应模式"):
        request_json("dummy","deepseek-flash","system",{},response_mode="unsafe")
