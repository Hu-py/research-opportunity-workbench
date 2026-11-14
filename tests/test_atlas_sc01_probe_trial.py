"""SC01 probe replay validates provenance and cannot impersonate a team backend run."""
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.atlas_sc01_probe_trial import evaluate, ROOT, DEFAULT

MANIFEST = json.loads(DEFAULT.read_text(encoding="utf-8"))
PLAN = json.loads((ROOT / "config/atlas_source_plan.json").read_text(encoding="utf-8"))


def test_three_probes_and_explicit_four_supplementary_sources():
    result = evaluate(MANIFEST, PLAN)
    assert result["probe_counts"] == {
        "planning_application": 4,
        "urban_science": 4,
        "computational_methods": 4,
    }
    assert result["unique_papers"] == 16
    assert result["supplementary_count"] == 4
    assert result["autonomous_agent_run"] is False
    assert result["team_acl_verified"] is False
    assert result["scientific_claims_verified_from_full_text"] is False


def test_reject_duplicate_citations():
    data = deepcopy(MANIFEST)
    data["papers"][1]["paper_id"] = data["papers"][0]["paper_id"]
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate(data, PLAN)


def test_reject_cross_probe_venue_misclassification():
    data = deepcopy(MANIFEST)
    data["papers"][0]["source_group"] = "computational_methods"
    with pytest.raises(ValueError, match="exact venue"):
        evaluate(data, PLAN)


def test_reject_false_authentication_claim():
    data = deepcopy(MANIFEST)
    data["access_control_tested"] = True
    with pytest.raises(ValueError, match="cannot claim"):
        evaluate(data, PLAN)


def test_reject_placeholder_sources():
    data = deepcopy(MANIFEST)
    data["papers"][0]["url"] = "https://example.org/fake"
    with pytest.raises(ValueError, match="Placeholder"):
        evaluate(data, PLAN)
