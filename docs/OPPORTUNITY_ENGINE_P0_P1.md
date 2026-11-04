# Research Atlas · P0 + P1

## Purpose
The Research Opportunity Engine now has two explicit review stages: link team research
lines to prior achievements/dataset metadata, then discover literature candidates for
manual relevance and method-transfer assessment. All sources remain traceable.

## P0 Research associations
- Source tables: profiles, cusp_datasets, team_achievements.
- Suggested link scores come from keywords/theme overlap; they are not verified facts.
- Admins can confirm or reject. The decisions remain in research_line_relations
  with an audit record. Confirmed links can be supplied read-only to Research Agent.
- Dataset links refer to registered metadata only. Raw file access is not implied.

## P1 Research-line literature discovery
- Each saved research line has direct-question searches and method searches.
- Maximum 3 editable queries/channel, max 2 queries/channel executed per run.
- Each request retrieves at most 12 OpenAlex records, default 8, 30-day window.
- A single daily run covers up to 3 explicitly opted-in lines (max 12 HTTP queries).
- Scheduled discovery is DISABLED by default. The existing Vercel daily cron
  (01:00 UTC) remains shared with the Shen Yao ORCID public output update.
- Manual per-line trial search is available to admins and research members.
- Literature is stored in paper_discovery_candidates as PENDING, not in papers.
- Human reviewers mark relevant or method-transfer to promote into papers.
- Rejected candidates remain excluded even when rediscovered; duplicate DOI IDs
  are merged per research line, and run logs track partial failures.
- Relevance scores are query matching heuristics, not novelty, rigor or quality.

## Usage
1. Log in at https://research-opportunity-workbench.vercel.app
2. Open the new sidebar: 科研关联与文献发现.
3. Research associations: confirm a few well-grounded links.
4. Search strategy: choose ONE line, edit queries, keep automatic monitoring
   disabled, and test a single scan.
5. Candidate papers: inspect title, DOI, original URL, abstract and why it matched.
6. Approve or reject; evaluate the relevance of the top 20 recommendations.
7. Only then enable opt-in daily monitoring for high-signal research lines.

## Free-tier scope and limitations
- No paid Render worker, no extra Vercel cron and no LLM charges.
- The Render Free FastAPI service can sleep or restart, interrupting background
  tasks; interrupted runs have no durable recovery in this prototype.
- OpenAlex API may require a free account key and imposes rate/usage limits.
- Only configured search queries (not private asset descriptions or raw files)
  are sent to OpenAlex. Keep confidential topics out of external search queries.
- Automatic matching is imperfect for Chinese data titles and English queries;
  use review controls to correct false matches.
- The Render Free PostgreSQL instance is due to expire 2026-12-04, with no
  automatic backups. Preserve the local source catalogue and move to backed-up
  storage before relying on long-term unattended accumulation.
