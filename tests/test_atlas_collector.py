"""Offline OpenAlex collector integration tests; no network or paid LLM."""
from datetime import date

from backend.atlas_intelligence.collector import (
    _abstract,
    _author_filter,
    collect_three_sources,
)
from backend.atlas_intelligence.runner import prepare_paper_snapshot


PLAN = {
    "source_groups": {
        "planning_application": {"venues": ["Cities"]},
        "urban_science": {"venues": ["EPB"]},
        "computational_methods": {"venues": ["NeurIPS"]},
    },
    "authors": [{
        "author_id": "A100",
        "source_groups": ["computational_methods"],
    }],
}
CATALOG = [
    {"name": "Cities", "abbreviation": "Cities", "aliases": []},
    {"name": "Environment and Planning B: Urban Analytics and City Science",
     "abbreviation": "EPB", "aliases": ["Environment and Planning B Urban Analytics and City Science"]},
    {"name": "Conference on Neural Information Processing Systems",
     "abbreviation": "NeurIPS", "aliases": ["NeurIPS"]},
]
SOURCES = {
    "Cities": ("S1", "Cities"),
    "Environment and Planning B: Urban Analytics and City Science":
        ("S2", "Environment and Planning B Urban Analytics and City Science"),
    "Conference on Neural Information Processing Systems":
        ("S3", "Conference on Neural Information Processing Systems"),
}


def work(wid, source_id, venue, *, doi="", authors=None, abstract=None, retracted=False):
    authors = authors or []
    return {
        "id": "https://openalex.org/" + wid,
        "title": "Paper " + wid,
        "doi": ("https://doi.org/" + doi) if doi else None,
        "publication_date": "2026-11-07",
        "type": "article",
        "is_retracted": retracted,
        "primary_location": {
            "source": {"id": "https://openalex.org/" + source_id, "display_name": venue}
        },
        "authorships": [{
            "author": {"id": "https://openalex.org/" + ident, "display_name": ident}
        } for ident in authors],
        "abstract_inverted_index": abstract,
    }


def fake_api(endpoint, params):
    if endpoint == "/sources":
        lookup = SOURCES.get(params["search"])
        if lookup:
            sid, name = lookup
            return {"results": [{"id": "https://openalex.org/" + sid,
                                  "display_name": name}]}
        return {"results": []}
    assert endpoint == "/works"
    query = params["filter"]
    if "source.id:S1" in query:
        return {"results": [
            work("W1", "S1", "Cities", doi="10.1111/example",
                 abstract={"Planning": [0], "problem": [1]}),
            work("W9", "S1", "Cities", retracted=True),
        ]}
    if "source.id:S2" in query:
        return {"results": [work("W2", "S2",
                "Environment and Planning B Urban Analytics and City Science",
                doi="10.2222/example")]}
    if "source.id:S3" in query:
        return {"results": [work("W3", "S3",
                "Conference on Neural Information Processing Systems",
                abstract={"A": [0], "method": [1]})]}
    if "authorships.author.id:A100" in query:
        return {"results": [
            work("W4", "S99", "Other Venue", doi="10.2222/example",
                 authors=["A100"], abstract={"Methods": [0], "improved": [1]}),
            work("W8", "S99", "Other Venue", authors=["A200"]),
        ]}
    raise AssertionError("Unexpected API query " + query)


def test_live_schema_uses_independent_three_sources_and_author_linkage():
    feed = collect_three_sources(
        api=fake_api, plan=PLAN, catalog=CATALOG,
        today=date(2026, 11, 14), lookback_days=14, max_per_source=8,
    )
    assert feed["feed_kind"] == "atlas_three_source_public_evidence"
    assert feed["status"] == "complete"
    assert feed["coverage"]["global_unique_papers"] == 3
    assert feed["coverage"]["group_distinct_papers"] == {
        "planning_application": 1,
        "urban_science": 1,
        "computational_methods": 2,
    }
    by_id = {p["paper_id"]: p for p in feed["papers"]}
    assert set(by_id) == {"W1", "W2", "W3"}
    assert by_id["W1"]["evidence_level"] == "abstract"
    assert by_id["W2"]["evidence_level"] == "abstract"
    assert by_id["W2"]["source_groups"] == ["urban_science", "computational_methods"]
    assert set(by_id["W2"]["openalex_ids"]) == {"W2", "W4"}
    assert any(p["kind"] == "author" for p in by_id["W2"]["source_provenance"])
    assert by_id["W3"]["evidence_level"] == "abstract"
    assert feed["coverage"]["authors"]["successful"] == 1
    assert not feed["warnings"]


def test_feed_can_enter_L1_runner_without_old_radar_registry():
    feed = collect_three_sources(
        api=fake_api, plan=PLAN, catalog=CATALOG,
        today=date(2026, 11, 14), max_per_source=8,
    )
    papers, coverage = prepare_paper_snapshot(feed["papers"], [], per_group_limit=10)
    assert len(papers) == 3
    by_id = {p["paper_id"]: p for p in papers}
    assert by_id["W2"]["source_groups"] == ["urban_science", "computational_methods"]
    assert coverage["unclassified_candidate_count"] == 0


def test_failure_is_explicit_and_does_not_disappear_from_coverage():
    def broken_api(endpoint, params):
        if endpoint == "/works" and "source.id:S2" in params["filter"]:
            raise RuntimeError("OpenAlex HTTP 503")
        return fake_api(endpoint, params)

    feed = collect_three_sources(
        api=broken_api, plan=PLAN, catalog=CATALOG,
        today=date(2026, 11, 14),
    )
    assert feed["status"] == "partial"
    assert feed["coverage"]["source_groups"]["urban_science"]["failed_sources"][0]["venue"] == "EPB"
    assert feed["coverage"]["group_distinct_papers"]["planning_application"] == 1


def test_watched_author_requires_verified_id_not_matching_name():
    assert _author_filter("A100") == ("authorships.author.id", "A100")
    assert _author_filter("https://orcid.org/0000-0002-1825-0097") == (
        "authorships.author.orcid", "0000-0002-1825-0097"
    )


def test_abstract_truncation_is_not_falsely_labelled_complete():
    text, level = _abstract({"a": list(range(100)), "b": [101]}, limit=12)
    assert level == "abstract_excerpt"
    assert text.endswith("…")
    assert _abstract(None) == ("", "metadata")


def test_source_plan_cap_is_disclosed():
    plan = dict(PLAN)
    plan["source_groups"] = dict(PLAN["source_groups"])
    plan["source_groups"]["planning_application"] = {"venues": ["Cities", "NoMatchingJournal"]}
    feed = collect_three_sources(
        api=fake_api, plan=plan, catalog=CATALOG,
        today=date(2026, 11, 14), max_sources_per_group=1
    )
    assert feed["status"] == "partial"
    assert feed["coverage"]["source_groups"]["planning_application"]["configured_venues"] == 2
    assert feed["coverage"]["source_groups"]["planning_application"]["attempted_venues"] == 1
