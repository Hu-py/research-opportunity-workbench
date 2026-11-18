"""Offline, deterministic R6.6 DOI/label benchmark; never calls actual providers."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import httpx
import pytest

from scripts.sc05_r66_eval import (
    evaluate, fetch_openalex_metadata, load_manifest, normalize_doi,
)

MANIFEST = Path("benchmarks/sc05_r66_silver_set_v01.json")


def _subset(labels):
    m = copy.deepcopy(load_manifest(MANIFEST))
    m["items"] = [row for row in m["items"] if row["label"] in labels]
    return m


def _work(item, abstract):
    return {
        "id": "doi:" + normalize_doi(item["doi"]),
        "doi": normalize_doi(item["doi"]),
        "title": item["title"],
        "abstract": abstract,
        "published": str(item["year"]) + "-06-01",
        "url": item["publisher_url"],
        "venue": "Verified journal source",
    }


def test_silver_manifest_is_provisional_curated_and_doi_frozen():
    m = load_manifest(MANIFEST)
    assert m["snapshot_status"] == "provisional_silver_not_gold"
    assert len(m["items"]) == 15
    assert {x["label"] for x in m["items"]} == {
        "direct_near", "domain_context", "method_transfer",
        "unrelated", "source_self"}
    assert m["heldout_source"]["doi"] == "10.1038/s41598-026-67177-7"
    assert m["evaluation_limits"]["model_calls_allowed"] == 0
    assert m["evaluation_limits"]["second_reviewer_required_for_gold"] is True
    assert all(x["publisher_url"].startswith("https://doi.org/") for x in m["items"])


def test_duplicate_doi_and_unmarked_self_citation_are_rejected():
    m = load_manifest(MANIFEST)
    m["items"][0]["doi"] = m["items"][1]["doi"]
    temp = Path("/tmp/sc05_r66_invalid_manifest.json")
    try:
        temp.write_text(json.dumps(m))
        with pytest.raises(ValueError, match="duplicate"):
            load_manifest(temp)
        m["items"][0]["doi"] = "10.1038/s41598-026-67177-7"
        temp.write_text(json.dumps(m))
        with pytest.raises(ValueError):
            load_manifest(temp)
    finally:
        temp.unlink(missing_ok=True)


def test_offline_silver_metrics_do_not_infer_novelty_from_relevance():
    m = _subset({"direct_near", "unrelated", "source_self"})
    near = m["items"][0]
    unrelated = next(x for x in m["items"] if x["label"] == "unrelated")
    source = next(x for x in m["items"] if x["label"] == "source_self")
    m["items"] = [near, unrelated, source]
    works = {
        normalize_doi(near["doi"]): _work(
            near, "Urban rail transit and metro station passenger flow resilience."),
        normalize_doi(unrelated["doi"]): _work(
            unrelated, "Blood microcirculation dynamics in cerebral capillary networks."),
        normalize_doi(source["doi"]): _work(
            source, "Urban multimodal transit disruptions and metro station capacity."),
    }
    d = evaluate(m, works)
    assert d["evaluation_status"] == "complete_silver_not_gold"
    assert d["metrics"]["metadata_coverage"] == 1
    assert d["metrics"]["domain_recall_provisional"] == 1
    assert d["metrics"]["direct_near_candidate_recall"] == 1
    assert d["metrics"]["unrelated_admission_rate"] == 0
    assert d["metrics"]["source_self_excluded"] is True
    assert d["metrics"]["nearest_prior_semantic_accuracy"] is None
    assert d["metrics"]["scientific_novelty_certified"] is False
    assert d["metrics"]["model_calls"] == 0
    assert "Blood microcirculation dynamics" not in json.dumps(d)
    assert all("abstract" not in p or p == {} for p in d["per_paper"])


def test_missing_provider_records_are_unresolved_not_false_negative():
    m = _subset({"direct_near", "source_self"})
    direct = m["items"][0]
    source = next(x for x in m["items"] if x["label"] == "source_self")
    m["items"] = [direct, source]
    report = evaluate(
        m,
        {normalize_doi(direct["doi"]): _work(
            direct, "Metro station passenger flow resilience.")},
        {normalize_doi(source["doi"]): "openalex_http_429"},
    )
    assert report["evaluation_status"] == "partial_provider_coverage_not_comparable"
    assert report["metrics"]["metadata_coverage"] == .5
    assert report["metrics"]["source_self_excluded"] is None
    assert report["unresolved_dois"] == [normalize_doi(source["doi"])]
    assert report["per_paper"][1]["error_code"] == "openalex_http_429"


def test_openalex_live_lookup_is_doi_addressed_and_secret_safe(monkeypatch):
    m = _subset({"direct_near", "source_self"})
    direct = m["items"][0]
    source = next(x for x in m["items"] if x["label"] == "source_self")
    m["items"] = [direct, source]
    observed = []
    def mocked(request):
        observed.append(request)
        doi = request.url.params["filter"].removeprefix("doi:https://doi.org/")
        assert request.url.params["per-page"] == "1"
        return httpx.Response(200, json={"results": [{
            "id": "https://openalex.org/W123",
            "doi": "https://doi.org/" + doi,
            "title": "Metro station passenger flow and rail transit resilience",
            "publication_date": "2025-02-01",
            "abstract_inverted_index": {
                "Metro":[0], "station":[1], "passenger":[2],
                "flow":[3], "resilience":[4]},
            "primary_location":{"source":{"display_name":"Transport research"}},
        }]})
    monkeypatch.setenv("OPENALEX_API_KEY", "private-never-print-key")
    with httpx.Client(transport=httpx.MockTransport(mocked)) as client:
        works, errors, calls = fetch_openalex_metadata(
            m, client=client, max_requests=2, delay_seconds=0)
    assert len(observed) == 2
    assert all(x.url.params["api_key"] == "private-never-print-key" for x in observed)
    assert errors == {}
    assert calls == 2
    report = evaluate(m, works, errors, api_calls=calls)
    # The output never contains a private key or the OpenAlex abstract.
    assert "private-never-print-key" not in json.dumps(report)
    assert "Metro station passenger flow resilience" not in json.dumps(report)
    assert report["metrics"]["api_requests"] == 2
    assert report["metrics"]["model_calls"] == 0


def test_request_budget_is_hard_capped_including_transient_retries():
    m = _subset({"direct_near", "source_self"})
    direct = m["items"][0]
    source = next(x for x in m["items"] if x["label"] == "source_self")
    m["items"] = [direct, source]
    n = []
    def rate_limited(request):
        n.append(request)
        return httpx.Response(429)
    with httpx.Client(transport=httpx.MockTransport(rate_limited)) as client:
        works, errors, count = fetch_openalex_metadata(
            m, client=client, max_requests=2, delay_seconds=0)
    assert works == {}
    assert len(n) == count == 2
    assert errors[normalize_doi(direct["doi"])] == "openalex_http_429"
    assert errors[normalize_doi(source["doi"])] == "request_cap_exhausted"
