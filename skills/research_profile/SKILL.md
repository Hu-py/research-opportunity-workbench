---
name: research_profile
description: Synthesize a research group profile using ONLY cited current PostgreSQL records from Research Atlas; create a reviewable draft, never a direct overwrite.
---

# Database-Sourced Research Profile / 仅数据库证据的科研画像

## Mandatory source boundary

Use ONLY the current database snapshot supplied for this run:
- `profiles`: current official research goals; recorded intentions, not verified outcomes.
- `team_achievements`: verified output registry (stable ID, title, year, type, tags).
- `cusp_datasets`: metadata only, filtered to non-restricted assets; no raw samples or verified file availability.
- `papers` and approved `paper_discovery_candidates`: human-approved scholarly metadata (not automatic full-text comprehension).
- `research_line_relations`: previously confirmed links only.

Never use historical chat messages, personal project memory, manually seeded chat-based drafts, or anything outside these tables as evidence. Reviewer notes are editorial directions, not independent factual sources. Do not claim an unpublished research plan is a verified team publication.

Do not send any raw geographic data, individual-level observations, owners/custodians, personal identifiers, paths, private data descriptions, or credentials to the model.

## Repeatable scientific synthesis steps

1. Inventory source records by table and stable ID, count verified outputs and registered assets, flag missing permissions, missing spatial/temporal links and uncertainties.
2. Form 3–7 research line clusters from recurrent titles/tags in verified outcomes and recorded official research goals. Never force predefined personal project names into the output.
3. For each line identify a concrete research bottleneck, supported data modalities, method capability (only where there is direct evidence), and minimum falsifiable experiment.
4. Compare related lines, distinguish documented complementarities from unverified cross-line hypotheses.
5. Critique data gaps, baseline limitations, paper citation confidence, access restrictions and methods that cannot be established from title-only evidence.
6. Produce the exact compatible workbench profile and structured analysis. Each line's `evidence_refs` must be stable refs from the input registry (e.g. `team_achievements:<id>` or `cusp_datasets:<id>`). The backend checks every provided reference and rejects invented IDs.
7. Save only as a reviewable draft. Team admins may edit or publish with profile version-conflict checking. Never auto-overwrite official profiles.

## Machine-readable output contract

Return a single JSON object with:

- `profile.goals`: short grounded positioning
- `profile.team`: `name`, `mission`, `priorities`
- `profile.methods`: methods supported by evidence or explicitly flagged unverified
- `profile.datasets`: always an empty array; use CUSP registry directly
- `profile.excluded_terms`: search exclusion keywords
- `profile.research_lines`: 1–8 records each with `id`, `name`, `problem`, `keywords`, `search_queries`, `method_queries`
- `analysis.positioning`, `analysis.method_capabilities`, `analysis.cross_line_opportunities`, `analysis.evidence_gaps`, `analysis.scope_cautions`
- `analysis.line_insights`: one per research line, each with `line_id`, `bottleneck`, `next_experiment`, `data_requirements`, `evidence_status` and `evidence_refs`

Reference contract: stable refs follow `team_achievements:<id>`, `cusp_datasets:<id>`, or `papers:<id>` exactly as provided in the snapshot. Empty `evidence_refs` are permitted only for explicitly inferred/unsubstantiated lines. A title or asset listing is not evidence of method performance, scientific novelty, causal effect, or legal access.

Each `evidence_status` must be `verified`, `described`, `inferred` or `planned`. Purely listed team output titles should normally justify `described`, not a strong verified scientific conclusion.

The first prototype may use deterministic database matching with NO LLM calls; label it explicitly **database-grounded rule-based draft**. Subsequent manually triggered LLM generation uses the same database-only snapshot and must pass citation validation. Never call an LLM or alter the official shared profile without explicit approval.

## Updating

Use up-to-date live records, cite changes by source ID, and preserve older draft versions. Do not reuse retired conversation-derived drafts. Re-run only on new data or explicit user request.
