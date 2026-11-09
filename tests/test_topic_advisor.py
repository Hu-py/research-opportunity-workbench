import pytest
from backend.topic_advisor import ExperimentModel, artifacts, save, validate_topics
from research_workbench.core import session_factory


def test_unknown_citations_fail_closed():
    with pytest.raises(ValueError):
        validate_topics({"ideas": [{"paper_ids": ["invented"], "dataset_ids": []}]},
                        {"papers": [], "datasets": []})
    assert validate_topics({"ideas": [], "reason": "Insufficient evidence"}, {})["ideas"] == []


def test_reservation_survives_provider_failure(tmp_path, monkeypatch):
    factory = session_factory("sqlite:///" + str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-not-a-real-key")
    def fail(*args, **kwargs):
        raise TimeoutError("provider unavailable")
    monkeypatch.setattr("backend.topic_advisor.request_json", fail)
    model = ExperimentModel(factory, str(tmp_path / "lock"))
    with pytest.raises(TimeoutError):
        model.call("test", {})
    row = artifacts(factory, "model_call")[0]["content"]
    assert row["status"] == "failed" and row["reservation"] > 0
    for i in range(59):
        save(factory, "model_call", {"digest": str(i), "reservation": 0.001})
    with pytest.raises(RuntimeError, match="budget"):
        model.call("another", {})


def test_exact_cache_avoids_paid_call(tmp_path, monkeypatch):
    factory = session_factory("sqlite:///" + str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-not-a-real-key")
    calls = []
    def complete(*args, **kwargs):
        calls.append(1)
        return {"ideas": []}, {"input_tokens": 100, "output_tokens": 10}
    monkeypatch.setattr("backend.topic_advisor.request_json", complete)
    model = ExperimentModel(factory, str(tmp_path / "lock"))
    assert model.call("test", {}) == model.call("test", {})
    assert len(calls) == 1


def test_feedback_is_version_bound_and_reasoned(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.topic_advisor_api import mount
    factory = session_factory("sqlite:///" + str(tmp_path / "portfolio.sqlite"))
    app = FastAPI()
    mount(app, lambda: factory, lambda: None, lambda: None)
    ident = save(factory, "result", {"result": {"ideas": [{"title": "Known topic"}]}})
    with TestClient(app) as client:
        body = {"result_id": ident, "title": "Unknown topic", "action": "reject",
                "reason": "The outcome variable cannot be observed.",
                "principle": "Require observable outcomes before causal claims."}
        assert client.post("/api/topic-advisor/feedback", json=body).status_code == 422
        body["title"] = "Known topic"
        assert client.post("/api/topic-advisor/feedback", json=body).status_code == 200
        decisions = client.get("/api/topic-advisor").json()["decisions"]
        assert decisions[0]["content"]["confirmed"] is True
        body["reason"] = ""
        assert client.post("/api/topic-advisor/feedback", json=body).status_code == 422
