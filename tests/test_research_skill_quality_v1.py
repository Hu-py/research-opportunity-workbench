from backend.skill_loader import ALLOWED, load_skills
from backend.research_opportunity_skill import VERSION, CAPABILITIES, catalog


def test_v1_skill_version_and_capabilities():
    assert VERSION == "1.0.0"
    assert set(CAPABILITIES) == {"paper_discovery", "evidence_review", "method_transfer", "idea_review"}
    assert catalog()["status"] == "quality_v1_draft"


def test_default_loader_includes_synthesis_and_templates():
    assert "cross_paper_synthesis" in ALLOWED
    assert "report_templates" in ALLOWED
    loaded = load_skills()
    assert "single-paper observation" in loaded
    assert "Template D — SC03 / UC01 research opportunity report" in loaded


def test_explicit_capabilities_load_required_skills():
    for capability, spec in CAPABILITIES.items():
        loaded = load_skills(spec["skills"])
        assert "research_opportunity" in loaded
        assert loaded
