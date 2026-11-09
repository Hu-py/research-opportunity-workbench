"""Offline contract tests: no academic API keys or live network required."""
import httpx
import pytest

from backend.scientific_tools import (
    REGISTRY, ToolSession, ToolExecutionError,
)


def fake_http(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def session(calls=12, scopes=("literature:read",)):
    return ToolSession(scopes=frozenset(scopes), max_calls=calls)


def test_catalog_exposes_four_typed_tools():
    names = {t["name"] for t in REGISTRY.catalog()}
    assert names == {
        "openalex.search_papers", "crossref.lookup_doi",
        "semantic_scholar.citation_neighbors",
        "semantic_scholar.recommend_papers",
    }
    assert REGISTRY.catalog(set()) == []
    tool = next(t for t in REGISTRY.catalog() if t["name"] == "openalex.search_papers")
    assert "properties" in tool["input_schema"]


def test_scope_prevents_network_request():
    s = session(scopes=())
    with pytest.raises(ToolExecutionError, match="permission denied"):
        REGISTRY.invoke("openalex.search_papers",
                        {"query": "urban networks", "since": "2025-01-01"},
                        session=s)
    assert s.calls == 0


def test_argument_validation_prevents_network_request():
    s = session()
    with pytest.raises(ToolExecutionError, match="Invalid tool arguments"):
        REGISTRY.invoke("openalex.search_papers",
                        {"query": "urban", "since": "2025-01-01", "limit": 200,
                         "unexpected": "value"}, session=s)
    assert s.calls == 0


def test_openalex_reuses_existing_normalization():
    urls = []
    def response(request):
        urls.append(str(request.url))
        return httpx.Response(200, json={"results": [{
            "id": "https://openalex.org/W1", "title": "Urban graphs",
            "publication_date": "2026-01-20",
            "doi": "https://doi.org/10.1234/sample",
            "primary_location": {"source": {"display_name": "Journal of Cities"}}
        }]})
    with fake_http(response) as http:
        result = REGISTRY.invoke("openalex.search_papers",
            {"query": "urban graph", "since": "2025-01-01", "limit": 5},
            session=session(), client=http)
    assert result["data"]["papers"][0]["title"] == "Urban graphs"
    assert "openalex.org/works" in urls[0]
    assert result["novelty_verified"] is False


def test_crossref_doi_lookup_and_metadata_only():
    def response(request):
        assert "/works/10.1234%2Fabc" in str(request.url)
        return httpx.Response(200, json={"message": {
            "DOI": "10.1234/abc", "title": ["Research Title"],
            "publisher": "Example Press", "type": "journal-article",
            "author": [{"given":"Yao", "family":"Shen"}],
        }})
    with fake_http(response) as http:
        result = REGISTRY.invoke("crossref.lookup_doi",
             {"doi": "https://doi.org/10.1234/abc"},
             session=session(), client=http)
    assert result["data"]["title"] == "Research Title"
    assert result["data"]["authors"] == ["Yao Shen"]
    assert result["evidence_level"] == "bibliographic_metadata"


def test_doi_injection_rejected():
    s = session()
    with pytest.raises(ToolExecutionError, match="Invalid DOI"):
        REGISTRY.invoke("crossref.lookup_doi", {"doi": "../api/keys"},
                        session=s)
    assert s.calls == 1


def test_citation_graph_direction_and_output():
    def response(request):
        assert "/references" in str(request.url)
        assert request.url.params["limit"] == "2"
        return httpx.Response(200, json={
            "data": [{"citedPaper": {
                "paperId": "abc", "title": "Prior Work", "year": 2024,
                "url": "https://www.semanticscholar.org/paper/abc"
            }}]})
    with fake_http(response) as http:
        result = REGISTRY.invoke("semantic_scholar.citation_neighbors",
            {"paper_id": "DOI:10.1234/abc", "direction": "references", "limit": 2},
            session=session(), client=http)
    assert result["data"]["papers"][0]["title"] == "Prior Work"


def test_recommendations_use_positive_and_negative_seeds():
    def response(request):
        assert request.method == "POST"
        assert request.url.params["limit"] == "3"
        import json
        body = json.loads(request.content.decode())
        assert body["negativePaperIds"] == ["DOI:10.1234/b"]
        return httpx.Response(200, json={
            "recommendedPapers": [{"paperId": "p1", "title": "Different Method"}]})
    with fake_http(response) as http:
        result = REGISTRY.invoke("semantic_scholar.recommend_papers",
            {"positive_paper_ids": ["DOI:10.1234/a"],
             "negative_paper_ids": ["DOI:10.1234/b"], "limit": 3},
            session=session(), client=http)
    assert result["data"]["papers"][0]["title"] == "Different Method"


def test_failed_network_call_consumes_budget_without_exposing_credentials(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "super-secret")
    s = session(calls=1)
    def response(request):
        return httpx.Response(429, json={"message": "rate limit", "key": "super-secret"})
    with fake_http(response) as http:
        with pytest.raises(ToolExecutionError) as err:
            REGISTRY.invoke("semantic_scholar.citation_neighbors",
                {"paper_id": "DOI:10.1234/a"}, session=s, client=http)
        assert "429" in str(err.value)
        assert "super-secret" not in str(err.value)
    assert s.calls == 1
    with pytest.raises(ToolExecutionError, match="limit reached"):
        REGISTRY.invoke("crossref.lookup_doi", {"doi": "10.1234/abc"},
                        session=s)
