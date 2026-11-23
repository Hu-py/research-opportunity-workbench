"""Provider-key resolution remains compatible with legacy Render secrets."""

from backend.model_vault import resolve_key


def test_resolve_key_prefers_current_environment_name(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "current-test-key")
    monkeypatch.setenv("SC04_DEEPSEEK_API_KEY", "legacy-test-key")
    assert resolve_key(None) == "current-test-key"


def test_resolve_key_accepts_legacy_sc04_environment_name(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SC04_DEEPSEEK_API_KEY", "legacy-test-key")
    assert resolve_key(None) == "legacy-test-key"
