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
