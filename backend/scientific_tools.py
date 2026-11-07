"""Safe, discoverable scientific tool adapters for evidence-seeking agents.

No tools execute on import. This is an opt-in foundation for a future agent
runtime, not a replacement for the existing OpenAlex discovery workflow.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from research_workbench.core import normalize_paper, query_openalex


class ToolExecutionError(Exception):
    """A bounded, sanitized failure safe to show in an execution trace."""


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenAlexSearchArgs(_Args):
    query: str = Field(min_length=3, max_length=240)
    since: date
    limit: int = Field(default=10, ge=1, le=20)


class CrossrefDoiArgs(_Args):
    doi: str = Field(min_length=6, max_length=220)


class SemanticScholarNeighborsArgs(_Args):
    paper_id: str = Field(min_length=3, max_length=200)
    direction: Literal["references", "citations"] = "references"
    limit: int = Field(default=10, ge=1, le=20)


class SemanticScholarRecommendArgs(_Args):
    positive_paper_ids: list[str] = Field(min_length=1, max_length=8)
    negative_paper_ids: list[str] = Field(default_factory=list, max_length=8)
    limit: int = Field(default=10, ge=1, le=20)


def _safe_doi(raw: str) -> str:
    doi = raw.strip()
    if doi.lower().startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    if doi.lower().startswith("doi:"):
        doi = doi[4:]
    if not re.fullmatch(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", doi, re.I):
        raise ToolExecutionError("Invalid DOI format")
    return doi


def _paper_id(raw: str) -> str:
    ident = raw.strip()
    if not ident or len(ident) > 200 or any(c in ident for c in "\r\n\t?#"):
        raise ToolExecutionError("Invalid scholarly paper identifier")
    # Accept S2 paper hashes and explicit DOI, ARXIV, CorpusId identifiers.
    if re.fullmatch(r"[a-fA-F0-9]{40}", ident):
        return ident
    if ":" in ident:
        prefix, value = ident.split(":", 1)
        if prefix.upper() == "DOI":
            return "DOI:" + _safe_doi(value)
        if prefix.upper() in ("ARXIV", "CORPUSID"):
            if re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", value):
                return prefix + ":" + value
    raise ToolExecutionError("Use an S2 paper hash, DOI:, ARXIV: or CorpusId: identifier")


def _get(url: str, *, params: dict[str, Any] | None = None,
         headers: dict[str, str] | None = None,
         client: httpx.Client | None = None) -> dict[str, Any]:
    own = client is None
    http = client or httpx.Client(timeout=20, follow_redirects=False)
    try:
        response = http.get(url, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ToolExecutionError("Provider response was not a JSON object")
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            raise ToolExecutionError("Provider HTTP " + str(exc.response.status_code)) from exc
        raise ToolExecutionError("Provider request or JSON decode failed") from exc
    finally:
        if own:
            http.close()


def _post(url: str, *, body: dict[str, Any], params: dict[str, Any] | None = None,
          headers: dict[str, str] | None = None,
          client: httpx.Client | None = None) -> dict[str, Any]:
    own = client is None
    http = client or httpx.Client(timeout=20, follow_redirects=False)
    try:
        response = http.post(url, params=params, json=body, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ToolExecutionError("Provider response was not a JSON object")
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            raise ToolExecutionError("Provider HTTP " + str(exc.response.status_code)) from exc
        raise ToolExecutionError("Provider request or JSON decode failed") from exc
    finally:
        if own:
            http.close()


def _s2_headers() -> dict[str, str]:
    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    return {"x-api-key": key} if key else {}


def openalex_search(args: OpenAlexSearchArgs, client: httpx.Client | None = None) -> dict[str, Any]:
    try:
        records = query_openalex(args.query, args.since.isoformat(), args.limit, client=client)
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolExecutionError("OpenAlex retrieval failed") from exc
    papers = [normalize_paper(p) for p in records if isinstance(p, dict)]
    return {"query": args.query, "papers": papers[:args.limit],
            "source_url": "https://api.openalex.org/works"}


def crossref_lookup(args: CrossrefDoiArgs, client: httpx.Client | None = None) -> dict[str, Any]:
    doi = _safe_doi(args.doi)
    params = {}
    if os.getenv("CROSSREF_MAILTO"):
        params["mailto"] = os.environ["CROSSREF_MAILTO"]
    result = _get("https://api.crossref.org/works/" + quote(doi, safe=""),
                  params=params, client=client)
    record = result.get("message") or {}
    if not isinstance(record, dict):
        raise ToolExecutionError("Unexpected Crossref metadata")
    return {
        "doi": record.get("DOI") or doi, "title": (record.get("title") or [""])[0],
        "authors": [" ".join(filter(None, [a.get("given"), a.get("family")]))
                    for a in record.get("author", [])],
        "publisher": record.get("publisher"), "type": record.get("type"),
        "published": record.get("published"), "url": record.get("URL"),
        "update_to": record.get("update-to", []),
        "relation": record.get("relation", {}),
        "source_url": "https://api.crossref.org/works/" + quote(doi, safe=""),
    }


def s2_neighbors(args: SemanticScholarNeighborsArgs,
                 client: httpx.Client | None = None) -> dict[str, Any]:
    pid = _paper_id(args.paper_id)
    url = ("https://api.semanticscholar.org/graph/v1/paper/"
           + quote(pid, safe="") + "/" + args.direction)
    result = _get(url, params={"limit": args.limit, "offset": 0,
                               "fields": "title,year,url,externalIds"},
                  headers=_s2_headers(), client=client)
    paper_field = "citedPaper" if args.direction == "references" else "citingPaper"
    papers = []
    for item in (result.get("data") or [])[:args.limit]:
        if not isinstance(item, dict):
            continue
        paper = item.get(paper_field) or {}
        if isinstance(paper, dict):
            papers.append({k: paper.get(k) for k in (
                "paperId", "title", "year", "url", "externalIds")})
    return {"paper_id": pid, "direction": args.direction, "papers": papers,
            "source_url": url, "next": result.get("next")}


def s2_recommend(args: SemanticScholarRecommendArgs,
                 client: httpx.Client | None = None) -> dict[str, Any]:
    positives = list(dict.fromkeys(_paper_id(x) for x in args.positive_paper_ids))
    negatives = list(dict.fromkeys(_paper_id(x) for x in args.negative_paper_ids))
    if set(positives) & set(negatives):
        raise ToolExecutionError("Positive and negative seeds must not overlap")
    url = "https://api.semanticscholar.org/recommendations/v1/papers/"
    result = _post(url, body={"positivePaperIds": positives,
                              "negativePaperIds": negatives},
                   params={"limit": args.limit, "fields": "title,year,url"},
                   headers=_s2_headers(), client=client)
    papers = []
    for item in (result.get("recommendedPapers") or [])[:args.limit]:
        if isinstance(item, dict):
            papers.append({k: item.get(k) for k in ("paperId", "title", "year", "url")})
    return {"positive_paper_ids": positives,
            "negative_paper_ids": negatives, "papers": papers,
            "source_url": url}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    purpose: str
    provider: str
    schema: type[BaseModel]
    handler: Callable[[Any, httpx.Client | None], dict[str, Any]]
    required_scope: str = "literature:read"
    evidence_level: str = "bibliographic_metadata"

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "purpose": self.purpose,
                "provider": self.provider, "required_scope": self.required_scope,
                "evidence_level": self.evidence_level,
                "input_schema": self.schema.model_json_schema()}


@dataclass
class ToolSession:
    scopes: frozenset[str]
    max_calls: int = 12
    calls: int = 0


class ScientificToolRegistry:
    def __init__(self, specs: list[ToolSpec]):
        self._specs = {s.name: s for s in specs}
        if len(self._specs) != len(specs):
            raise ValueError("Duplicate tool names")

    def catalog(self, scopes: set[str] | frozenset[str] | None = None) -> list[dict[str, Any]]:
        items = list(self._specs.values())
        if scopes is not None:
            items = [s for s in items if s.required_scope in scopes]
        return [s.describe() for s in items]

    def invoke(self, name: str, arguments: dict[str, Any], *,
               session: ToolSession,
               client: httpx.Client | None = None) -> dict[str, Any]:
        spec = self._specs.get(name)
        if spec is None:
            raise ToolExecutionError("Unregistered scientific tool")
        if spec.required_scope not in session.scopes:
            raise ToolExecutionError("Tool permission denied")
        if session.max_calls < 1 or session.calls >= session.max_calls:
            raise ToolExecutionError("Per-run tool call limit reached")
        try:
            payload = spec.schema.model_validate(arguments)
        except ValidationError as exc:
            raise ToolExecutionError("Invalid tool arguments") from exc
        session.calls += 1   # Failed network calls count against the limit.
        data = spec.handler(payload, client)
        return {"tool": name, "provider": spec.provider,
                "evidence_level": spec.evidence_level,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "data": data,
                "novelty_verified": False}


REGISTRY = ScientificToolRegistry([
    ToolSpec("openalex.search_papers", "Discover academic papers by research question",
             "OpenAlex", OpenAlexSearchArgs, openalex_search),
    ToolSpec("crossref.lookup_doi", "Verify scholarly metadata for a DOI",
             "Crossref", CrossrefDoiArgs, crossref_lookup),
    ToolSpec("semantic_scholar.citation_neighbors",
             "Explore references or citing papers for novelty challenges",
             "Semantic Scholar", SemanticScholarNeighborsArgs, s2_neighbors),
    ToolSpec("semantic_scholar.recommend_papers",
             "Discover related papers from positive and negative seed papers",
             "Semantic Scholar", SemanticScholarRecommendArgs, s2_recommend),
])
