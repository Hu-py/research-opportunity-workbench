import json

from backend.discovery import PaperCandidate, candidate_id
from backend.preanalysis import PaperPreanalysis, execute_preanalysis, _validate
from test_ai_lab import PAPER_ID, lab, save_key


def test_preanalysis_validates_scores_and_requires_human_review():
    result = _validate({
        "fit_score": 82, "priority": "high_priority",
        "relevance": "与研究主线直接相关",
        "research_problem": "有限标签条件下的建筑功能推断",
        "method": "图表示学习",
        "claimed_contribution": "摘要声称跨区域迁移",
        "limitations_or_unknowns": "摘要未提供空间留出实验",
        "evidence_quality": "有摘要，仅摘要级证据",
        "reason": "问题与方法均匹配",
        "topic_tags": ["graph learning"], "evidence_level": "abstract",
    })
    assert result["fit_score"] == 82
    assert result["human_review_required"] is True
    assert result["novelty_verified"] is False


def test_preanalysis_persists_result_without_approving_candidate(lab, monkeypatch):
    factory, client, admin, member, _ = lab
    save_key(client, admin)
    ident = candidate_id("vertical", "openalex:W999999999")
    with factory() as db:
        db.add(PaperCandidate(
            id=ident, line_id="vertical", paper_id="openalex:W999999999",
            title="Graph transfer for building vertical functions",
            abstract="We study transfer learning for building floor functions.",
            doi="", url="https://openalex.org/W999999999",
            published="2026-10-01", venue="Example Conference",
            score=78, score_reason="method match", match_type="method",
            status="pending",
        ))
        db.commit()

    def fake_request(key, model, system, payload, client=None, max_tokens=1100):
        assert model == "deepseek-flash"
        assert payload["paper"]["candidate_id"] == ident
        assert "摘要" in system
        return ({
            "fit_score": 86, "priority": "high_priority",
            "relevance": "与建筑垂直功能研究高度相关",
            "research_problem": "跨区域条件下楼层功能迁移",
            "method": "图迁移学习",
            "claimed_contribution": "摘要声称提出跨域迁移方法",
            "limitations_or_unknowns": "尚未核验全文与外部城市泛化",
            "evidence_quality": "仅摘要级证据",
            "reason": "研究对象与方法均匹配",
            "topic_tags": ["vertical function", "graph learning"],
            "evidence_level": "abstract",
        }, {"input_tokens": 100, "output_tokens": 60})

    monkeypatch.setattr("backend.preanalysis.request_json", fake_request)
    stats = execute_preanalysis(factory, limit=6)
    assert stats["processed"] == 1
    with factory() as db:
        candidate = db.get(PaperCandidate, ident)
        analysis = db.get(PaperPreanalysis, ident)
        assert candidate.status == "pending"
        assert analysis.status == "completed"
        assert analysis.fit_score == 86
        assert json.loads(analysis.analysis_json)["novelty_verified"] is False


def test_preanalysis_rejects_invalid_priority():
    data = {
        "fit_score": 50, "priority": "approved",
        "relevance": "x", "research_problem": "x", "method": "x",
        "claimed_contribution": "x", "limitations_or_unknowns": "x",
        "evidence_quality": "x", "reason": "x", "topic_tags": [],
    }
    try:
        _validate(data)
    except ValueError as exc:
        assert "priority" in str(exc)
    else:
        raise AssertionError("Invalid priority must be rejected")
