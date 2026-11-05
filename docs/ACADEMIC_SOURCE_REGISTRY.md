# Academic Source Registry（学术来源管理）

## Purpose

Academic Source Registry is the standalone first-level module for managing the journals and conferences used by literature discovery. It is deliberately separated from manual research interests and from the official team research profile.

The module has two storage layers:

1. **Versioned GitHub bootstrap catalogue**: \`backend/data/academic_sources_seed.json\` stores the initial domain taxonomy and curated source list. Changes to this file are reviewed through Git history and can be restored.
2. **PostgreSQL runtime registry**: \`academic_domains\`, \`academic_sources\`, \`academic_source_revisions\`, and \`academic_registry_state\` are the runtime source of truth. The bootstrap process inserts missing entries but never overwrites records already present in PostgreSQL. Manual edits therefore survive code deployments and seed-version updates.

The initial catalogue contains 108 journals/conferences across 18 domains. The taxonomy is editable in the UI and is not hard-coded into the discovery engine.

## Source metadata

Each source stores:

- Canonical title, abbreviation and aliases
- Kind: journal or conference
- One or more research domains
- Rank label, ranking system and ranking version (e.g. CCF 2026 7th edition or team-curated priority)
- Official homepage and explanatory notes
- Retrieval channels: \`direct\` (domain/problem literature) and/or \`method\` (computer-science method transfer)
- Enabled/paused state
- OpenAlex Source ID, source type, exact-match resolution status and resolution note
- Creation/update timestamps and a revision history

A rank label is a **retrieval prior**, not a claim about the quality of an individual paper. CCF conference grades must be checked against the applicable paper format; OpenAlex does not reliably distinguish every Full/Regular Paper, Short Paper, Workshop, Demo or poster. Individual papers remain in the review queue.

## Runtime behaviour

- Only enabled sources with a verified OpenAlex Source ID enter the strict discovery filter.
- Direct and method-transfer queries use separate source channels.
- If a channel has no verified source, the discovery runner reports that channel as unavailable; it does not silently fall back to a broad all-OpenAlex search.
- The OpenAlex resolver accepts exact canonical-name, abbreviation or alias matches. Ambiguous matches are left unresolved; no fuzzy guess is accepted.
- Resolve requests process at most 10 sources per batch by default. Re-running a failed or ambiguous item is an explicit action.
- Editing a source's canonical name, abbreviation or aliases invalidates its previous OpenAlex ID so it must be resolved again.
- Sources are paused rather than deleted, preserving their history and prior candidate-paper provenance.

## CSV import/export

CSV is intended for bulk maintenance. UTF-8 files should include a \`name\` header. Supported columns:

| Column | Meaning |
|---|---|
| \`name\` | Canonical journal/conference title (required) |
| \`abbreviation\` | Short name |
| \`kind\` | \`journal\` or \`conference\` |
| \`domains\` | Domain slugs separated by \`|\` |
| \`rank_label\` | A/B/C, 核心, 重点, 补充, 观察, or team-defined text |
| \`ranking_system\` | Ranking authority or curation basis |
| \`ranking_version\` | Version/edition |
| \`ranking_source_url\` | Original ranking directory / authority URL |
| \`source_url\` | Official HTTPS homepage |
| \`aliases\` | Aliases separated by \`|\` |
| \`notes\` | Research scope and editorial notes |
| \`retrieval_channels\` | \`direct\` and/or \`method\`, separated by \`|\` |
| \`enabled\` | true/false |

Import is an upsert by normalized canonical name. Existing rows are updated, not duplicated. Unknown domain slugs are reported as row errors; add the domain first. Export includes the OpenAlex ID and resolution state for backup/audit.

## API

- \`GET /api/academic-sources\` — list, filters, domains, summary and catalogue version
- \`POST /api/academic-sources\` — create a source
- \`PATCH /api/academic-sources/{source_id}\` — edit or pause a source
- \`GET /api/academic-sources/{source_id}/history\` — source revision history
- \`POST /api/academic-sources/resolve\` — exact-match OpenAlex resolution
- \`GET /api/academic-sources/export\` — CSV export
- \`POST /api/academic-sources/import\` — CSV upsert (admin)
- \`GET /api/academic-domains\` — domain taxonomy
- \`POST/PATCH/DELETE /api/academic-domains...\` — taxonomy maintenance (admin)

All endpoints require the existing workbench authentication. Source editing requires the editor role; bulk import and taxonomy maintenance require the admin role.

## Bootstrap and deployment

The FastAPI startup path calls \`seed_registry()\`. New database tables are created through the existing SQLAlchemy metadata bootstrap. No manual SQL migration is required for a fresh database. For an existing PostgreSQL database, \`Base.metadata.create_all\` creates the four new registry tables without altering existing paper/profile tables.

Do not put private papers, API keys or confidential research notes in the public seed JSON. The seed file is a public catalogue of venues and domains only.
