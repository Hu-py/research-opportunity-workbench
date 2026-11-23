"""Deterministic, offline coverage of the first Research Opportunity Skill bridge."""
import json
import pytest
from backend.research_opportunity_skill import (
    VERSION, CAPABILITIES, catalog, make_payload, parse_payload, execute,
)


def test_catalog_and_scope():
    result = catalog()
    assert result["id"] == "research_opportunity"
    assert result["status"] == "quality_v1_draft"
    assert result["scope"] == "team_shared"
    assert set(i["id"] for i in result["capabilities"]) == set(CAPABILITIES)


@pytest.mark.parametrize("capability", list(CAPABILITIES))
def test_payload_round_trip(capability):
    value = make_payload(capability, "上海城市健康与图学习的外推边界")
    assert parse_payload(value) == (capability, "上海城市健康与图学习的外推边界")


@pytest.mark.parametrize("value", [
    "bad json", "[]", "null",
    json.dumps({"version": VERSION, "scope": "private",
                "capability": "paper_discovery", "question": "城市健康空间建模"}),
    json.dumps({"version": VERSION, "scope": "team_shared",
                "capability": "unknown", "question": "城市健康空间建模"}),
    json.dumps({"version": "0.0", "scope": "team_shared",
                "capability": "paper_discovery", "question": "城市健康空间建模"}),
])
def test_reject_bad_or_private_payload(value):
    with pytest.raises(ValueError):
        parse_payload(value)


def test_reject_short_question():
    with pytest.raises(ValueError):
        make_payload("paper_discovery", "hi")


def test_execute_uses_explicit_skills_and_marks_needs_review(monkeypatch):
    import backend.agent as agent_module
    captured = {}

    class StubAgent:
        def __init__(self, db, **kwargs):
            captured["skill_names"] = kwargs["skill_names"]

        def run(self, prompt):
            captured["prompt"] = prompt
            return {"mode": "bibliographic_preview", "answer": "文献证据预览",
                    "sources": [], "usage": {"tool_calls": 0}}

    monkeypatch.setattr(agent_module, "ResearchAgent", StubAgent)
    result = execute(None, make_payload("method_transfer", "上海城市健康图学习方法迁移"))
    assert "method_transfer" in captured["skill_names"]
    assert "research_opportunity" in captured["skill_names"]
    assert "城市健康" in captured["prompt"]
    assert result["review_status"] == "needs_review"
    assert result["model_mode"] == "bibliographic_preview"
    assert result["scope"] == "team_shared"


def test_worker_closed_loop_without_external_calls(monkeypatch, tmp_path):
    from research_workbench.core import session_factory
    from backend.tasks import enqueue, ResearchTask
    from backend.worker import run_task
    import backend.worker as worker_module
    import backend.agent as agent_module

    class StubAgent:
        def __init__(self, db, **kwargs):
            assert "research_opportunity" in kwargs["skill_names"]

        def run(self, prompt):
            assert "基线" in prompt
            return {"mode": "offline_stub", "answer": "需要近邻论文审查及基线实验",
                    "sources": [{"title": "Verified only in fixture", "url": "https://example.org/test"}],
                    "usage": {"tool_calls": 0, "model_rounds": 0}}

    monkeypatch.setattr(agent_module, "ResearchAgent", StubAgent)
    monkeypatch.setattr(worker_module, "task_source_context", lambda db, task_id: {
        "groups": {"A": ["a"], "B": ["b"], "C": ["c"]},
        "direct_ids": ["S1", "S2"], "method_ids": ["S3"], "all_ids": ["S1", "S2", "S3"],
        "source_ids_by_lane": {"A": ["S1"], "B": ["S2"], "C": ["S3"]},
        "allowed_venues": {"a", "b", "c"},
        "allowed_venues_by_lane": {"A": {"a"}, "B": {"b"}, "C": {"c"}},
        "scope_version": "test-source-v1", "scene": "directed_research",
    })
    factory = session_factory("sqlite:///" + str(tmp_path / "research.db"))
    with factory() as db:
        task = enqueue(db, "research_opportunity",
                       make_payload("method_transfer", "上海城市健康图学习方法迁移"))
        task_id = task.id
    assert run_task(factory, task_id)
    with factory() as db:
        finished = db.get(ResearchTask, task_id)
        assert finished.status == "completed"
        result = json.loads(finished.result_json)
        assert result["skill"] == "research_opportunity"
        assert result["review_status"] == "needs_review"
        assert result["capability"] == "method_transfer"
        assert "近邻论文" in result["answer"]


def test_disabled_until_explicitly_opted_in(monkeypatch):
    from fastapi import HTTPException
    from backend.api import require_research_opportunity_enabled
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "false")
    monkeypatch.setenv("RESEARCH_OPPORTUNITY_SKILL_ENABLED", "true")
    with pytest.raises(HTTPException) as exc:
        require_research_opportunity_enabled()
    assert exc.value.status_code == 503
    monkeypatch.setenv("TEAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("RESEARCH_OPPORTUNITY_SKILL_ENABLED", "false")
    with pytest.raises(HTTPException) as exc:
        require_research_opportunity_enabled()
    assert exc.value.status_code == 503
    monkeypatch.setenv("RESEARCH_OPPORTUNITY_SKILL_ENABLED", "true")
    assert require_research_opportunity_enabled() is None
