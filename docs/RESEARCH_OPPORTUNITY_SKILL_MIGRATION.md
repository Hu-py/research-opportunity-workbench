# Research Atlas — Research Opportunity Skill migration V0.1

> Status: **experimental draft branch**, not production. This bridge does not implement V0.6 private/team chat, nor the unmerged L1 multi-paper signal pipeline.

## Scope and scientific lineage

The Research Opportunity Radar (ROR V3.1) research process is being migrated as versioned backend capabilities, not transplanted as a ChatGPT Custom GPT. ChatGPT Builder knowledge, conversations, memory, and plugins cannot be inherited automatically through the API.

Current bridge capabilities, all **draft-only**:

| Capability ID | User-level function | Existing implementation |
| --- | --- | --- |
| `paper_discovery` | Find relevant bibliographic evidence | `backend.agent.ResearchAgent`, OpenAlex / saved papers, `literature_discovery` |
| `evidence_review` | Inspect source-supported research claims and limits | `paper_reader` |
| `method_transfer` | Map computational methods to urban questions | `method_transfer`, baseline/pilot prompts |
| `idea_review` | Criticize proposed research novelty and feasibility | `idea_discovery`, `idea_critic` |

The shared `research_opportunity` instructions cover evidence levels, provenance, scientific uncertainty, ROR Radar A/B1/B2 distinctions, and Research Atlas's distinct A/B/C source groups. `backend/skill_loader.py` now recognizes the versioned instructions; the default explore task keeps its previous skill set unchanged.

**Not implemented**: a production three-source literature collector; cross-paper L1 synthesis; complete scientific validity audit; private/personal analysis; automatic weekly report; approval or publication. The separate draft PR #57 remains independently reviewable. Existing weekly tasks and reports remain unchanged.

## Opt-in configuration

Requires **both** flags on the FastAPI service:

- `TEAM_AUTH_ENABLED=true` (existing team identity and session authentication).
- `RESEARCH_OPPORTUNITY_SKILL_ENABLED=true` (new, off by default).

Do not enable this route in personal/no-login mode. It uses the existing shared `research_tasks` table, which team members can read; **never pass private conversations, restricted research content, personal health data, or unpublished confidential material**. The eventual V0.6 chat integration must implement conversation membership authorization before forwarding private research inputs.

No new database tables or schema migration are introduced. Backend model calls use existing server-only `OPENAI_API_KEY` and `OPENAI_MODEL`; without a model key the result explicitly falls back to a *bibliographic preview*.

## Endpoints and execution

Authenticated team members:

```
GET /api/skills/research-opportunity
```

Researcher/admin only:

```http
POST /api/skills/research-opportunity/runs
Content-Type: application/json
X-Research-Session: <existing authenticated team session>

{"capability":"method_transfer","question":"上海城市健康预测中图学习的可迁移性"}
```

Returns a regular queued `research_tasks` object, with a versioned payload. Retrieve status/result using the existing `GET /api/tasks/{task_id}`. The normal worker runs the task; local explicitly configured `WORKER_MODE=background` may run inline as an experimental fallback. No model calls are made merely by browsing the catalogue.

The payload includes `version`, `scope=team_shared`, `capability`, and `question`. Worker validation re-checks all fields, then calls bounded `ResearchAgent` with the capability's selected skill set. Result fields include `skill`, `version`, `capability`, `scope`, `review_status=needs_review`, `model_mode`, `answer`, `sources`, `usage`, and original `result`.

**Security and review:** existing API Bearer check plus team session is enforced on the FastAPI route. Role enforcement is on the server. The worker uses the existing read-only tool whitelist and bounded call count; this migration does not add arbitrary tool execution. Recording a result does **not** approve its scientific content.

## Test plan

```bash
python -m pytest -q tests/test_research_opportunity_skill.py
python -m pytest -q
python -m compileall -q backend
```

Offline tests cover explicit scope/version validation, the four capabilities, opt-in protection, skill selection, and a fake-model end-to-end worker round trip. No paid model or external API call is needed for these tests.

Further acceptance gates before production:

1. GitHub CI green; test authorized researcher vs viewer, invalid session and disabled flag on a real test backend.
2. Run small, explicitly approved OpenAlex retrieval tests and inspect false positives, missing abstracts and citation integrity.
3. Add controlled L1 cross-paper signals and true prior-art comparison from PR #57, with expert quality review.
4. Implement V0.6 conversation ACL, persistence, structured `@GPT` and idempotent calls before enabling conversational invocation.
5. Add runtime cost and provenance snapshots, manual approvals and change logs in Development Studio.
6. Preserve old Radar data, reports, review states and scheduled workflows until a separately approved migration verifies data lineage and rollback.

## References

- [V0.6 GPT-native conversation and Skill backend specification](https://chatgpt.com/space/page_9e6cbd2d82348191a85fa2e47f5d2596)
- [Research Atlas AI workflow and research quality design](https://chatgpt.com/space/page_4f5d2daf5684819181b1756930835fde)
- [ROR V3.1 scientific research and technical pathway protocol](https://github.com/Hu-py/research-opportunity-workbench)
- [Research Atlas three-source L1 draft PR #57](https://github.com/Hu-py/research-opportunity-workbench/pull/57)
