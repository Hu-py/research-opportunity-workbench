# Scientific Tool Registry / 科研工具能力库（首批集成）

Status: **experimental, opt-in**. This branch does not run automated agent tool calls and does not change daily discovery or the public frontend. All adapters return bibliographic evidence, never a verified novelty claim.

## Design choice

Keep the current FastAPI + PostgreSQL + DeepSeek deployment and existing OpenAlex query pipeline. New libraries should be introduced behind narrow, testable tool interfaces rather than copied wholesale into the application.

The first tool layer uses the project's existing Python >=3.10, Pydantic 2 and httpx dependencies. Later adoption of current Pydantic AI / official MCP Python SDK needs a reviewed runtime upgrade to Python >=3.11. LangGraph can be evaluated separately for graph orchestration and durable checkpoints; it is not installed in this change.

### Tool inventory

| Tool | Source | Function | Agent | Implementation |
| --- | --- | --- | --- | --- |
| openalex.search_papers | OpenAlex | Discover candidate publications | Question discovery / prior-art | Wrapped existing query_openalex |
| crossref.lookup_doi | Crossref | Verify registered DOI metadata and potential update metadata | Evidence verifier | HTTP adapter |
| semantic_scholar.citation_neighbors | Semantic Scholar | Explore incoming and outgoing citations | Novelty challenger | HTTP adapter |
| semantic_scholar.recommend_papers | Semantic Scholar | Discover related papers from positive and negative seeds | Frontier / adversarial agent | HTTP adapter |
| paper_qa.fulltext_answer | PaperQA2 | Citation-backed full-text evidence answering | Evidence reader | **planned; not installed** |
| spatial.describe_data | DuckDB Spatial / GeoPandas | Private spatial data exploration | Dataset agent | **planned; not installed** |
| spatial.stats | PySAL | Moran's I, spatial regression and other statistical tests | Experiment agent | **planned; not installed** |
| experiment.execute | Isolated sandbox + explicit approval | Run a reproducible baseline experiment | Experiment agent | **planned; disabled** |

References:
- OpenAlex: https://docs.openalex.org/
- Semantic Scholar Academic Graph: https://api.semanticscholar.org/api-docs/
- Semantic Scholar Recommendations: https://api.semanticscholar.org/api-docs/recommendations
- Crossref: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- PaperQA2: https://github.com/Future-House/paper-qa
- PySAL: https://pysal.org/
- DuckDB Spatial: https://duckdb.org/docs/current/core_extensions/spatial/overview
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Pydantic AI toolsets: https://ai.pydantic.dev/toolsets/

## Discover and call

```python
from backend.scientific_tools import REGISTRY, ToolSession

available = REGISTRY.catalog({"literature:read"})
print([tool["name"] for tool in available])

session = ToolSession(scopes=frozenset({"literature:read"}), max_calls=4)
result = REGISTRY.invoke(
    "openalex.search_papers",
    {"query": "urban graph domain generalization", "since": "2025-01-01", "limit": 5},
    session=session,
)
print(result["data"]["papers"])
```

Tools have typed JSON input schemas, capped results and per-run call limits. Invalid parameters, unregistered tools and insufficient scopes are rejected. Calls failing after dispatch still count against the limit. Network URLs are hardcoded provider endpoints; model-generated URLs are never fetched.

For local offline tests:

```bash
python -m pytest -q tests/test_scientific_tools.py
```

## Configuration

- Existing OpenAlex access: OPENALEX_API_KEY and optionally OPENALEX_MAILTO.
- Optional SEMANTIC_SCHOLAR_API_KEY for authenticated S2 use; without a key S2 may throttle requests heavily.
- Optional CROSSREF_MAILTO for polite Crossref requests.
- No model API key is needed to import or unit-test this registry.
- Do not commit real API credentials or private papers. Requests are restricted to public bibliographic identifiers and user-approved search terms.
- Dataset location, restricted metadata, source files and full-text copyrighted content are not sent to these providers by the registry.

## Integration gates before automatic agent use

1. **Runtime**: model tool-choice outputs must be validated against this registry's JSON schemas; invoke only allowed names/scopes. LLM cannot choose arbitrary URLs or executable Python.
2. **Budget**: connect per-run tool calls to the existing daily budget ledger. Handle rate limits, backoff, caching and per-provider quotas; max_calls alone is not a daily spending limit.
3. **Evidence**: store tool name, timestamp, provider URL, related hypothesis ID, retrieval identifiers and validation status with each hypothesis. Citation neighbors are discovery candidates, not proof of novelty.
4. **Human review**: no self-certification of academic originality. Any external/private data access, paid APIs, code execution or publication action needs separate authorization.
5. **Security**: keep live S2/other credentials server-side, protect private datasets and use isolated execution for statistical experiments.
6. **Experiment**: establish a reproducible baseline comparing current single-chain proposals with tool-backed competitive ideation, measuring human adoption and prior-art overlap.

## Why not install entire agent libraries yet?

The current system already has the DeepSeek adapter and guarded budget module. Replacing the orchestrator before verifying tools would add dependency risk and produce no proof of better science. The initial registry is intentionally a small, isolated and reversible PR with mock-network contract tests. Additional libraries should be promoted only after evaluating maintenance, license, data protections, full-text access rights, cost and benchmark results.


## P3 prototype: model-guided Scientific Exploration Agent

The repository now includes a **manual, opt-in LLM tool-use loop** in
`backend/scientific_agent.py`. It is not the daily discovery cron and it
does not replace the four-stage legacy `backend/ai_lab.py` flow.

### How to use the first UI

1. Log in to the team workspace as `researcher` or `admin`; single-user legacy
   mode cannot launch a paid exploration.
2. Go to **选题中心 → AI 选题分析 → 科研工具智能体 · 实验版**.
3. Confirm an encrypted DeepSeek key is configured by the administrator and
   select a registered research line.
4. Write a specific research question and click **开始证据探索**.
5. Review the trace, paper IDs/DOIs, data assumptions, baselines and falsifiers.
   The resulting hypothesis is *always* unverified and is not automatically
   promoted to a team research topic.

API:
- `GET /api/scientific-tools` lists registered safe tools and JSON schemas.
- `POST /api/scientific-explorations` body:
  `{"line_id":"<existing-line-id>","question":"<research question>"}`
- `GET /api/scientific-explorations` lists brief statuses.
- `GET /api/scientific-explorations/{id}` provides provenance and hypothesis.
- `POST /api/scientific-explorations/{id}/resume` resumes a failed run
  using already saved evidence; it does not restart completed runs.

Security and reliability:
- Role-gated manual trigger only; never started from a cron or on page load.
- The LLM may only select tools from the server-side allowlist; it cannot
  choose external URLs, send arbitrary HTTP requests or run source code.
- Each run is bounded to **5 model decisions** and **3 tool calls**.
- Every model call reserves one call plus 9,000 tokens through the existing
  global daily budget before contacting DeepSeek.
- Model outputs that cite nonexistent evidence IDs are rejected. No evidence
  leads to `insufficient_evidence` rather than `completed`.
- Evidence is **bibliographic metadata**, not independent confirmation of
  manuscript methods, results, novelty or dataset access.
- The trace and tool evidence are persisted to the configured database.
  The web service uses an inline FastAPI background task for a manual run;
  it may be interrupted on Render free-tier sleep, and a failed run can be
  manually resumed. A `running` or `queued` run must be stale for at least
  8 minutes before a manual retry is accepted, preventing duplicate live work.
  This is *not* a fully durable worker queue.
- Tests use mocked academic APIs and model choices. A passing CI run is
  not a live DeepSeek or Semantic Scholar validation.

The previous four-stage pipeline and its daily budget share the same ledger.
This improves tool grounding, but a genuine superiority claim requires
matched-source comparisons and independent blinded human judgments.

Run tests with:
```bash
python -m pytest -q tests/test_scientific_tools.py tests/test_scientific_agent.py tests/test_scientific_agent_api.py
```
