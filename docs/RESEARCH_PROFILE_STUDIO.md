# Research Profile Intelligence Studio / 科研画像分析原型

## Why it exists

Previously the shared research profile was editable JSON, and most research
directions were extracted by keyword matching or preset rule templates. This
feature provides a structured, evidence-aware profile *draft* alongside the
existing official profile, as well as a reusable Skill that can synthesise
future research portraits with DeepSeek.

## In the workbench

Open the fixed domain `https://research-opportunity-workbench.vercel.app`,
log in, and choose **团队研究画像**.

The new panel **结构化科研画像分析原型** displays:
- Positioning, method capabilities, line-by-line scientific bottlenecks and
  near-term experiments, cross-line opportunities and explicit evidence gaps.
- A first **curated example**, bootstrapped privately from earlier discussions
  and flagged `personal_collaborative`, **not** verified team achievements.
- Versioned drafts that administrators may edit and publish to the official
  shared team profile. Every publish is subject to optimistic profile-version
  conflict checks and audit logging.
- **LLM 重新生成画像草稿**: an explicit admin click uses the saved DeepSeek API
  key and the reusable `skills/research_profile/SKILL.md`. Without a Key,
  the first curated static prototype is still available.
- LLM synthesis uses a bounded data snapshot: canonical official profile
  (without any free-form embedded dataset rows), first curated example,
  verified team output title/year/kind, and non-restricted CUSP dataset names,
  categories, time and spatial coverage, and formats. No files, identifiers,
  custodian fields, paths or restricted data are sent to the LLM.

## Storage and privacy

SQLAlchemy tables:
- `research_profile_drafts`: independent analysis and compatible official
  `Profile` JSON with source, owner-scope warning, status and base_version
- `research_profile_draft_revisions`: versioned edited profile snapshots
- `research_profile_synthesis_runs`: model, tokens, status and errors

Initial seed is **not committed to the public repository**. It is imported via
a one-time environment variable `RESEARCH_PROFILE_BOOTSTRAP_B64` with a UTF-8
base64 JSON object that follows the exact Skill output contract, and then
the variable is immediately cleared from Render. The id is based on a hash
for idempotence on restarts; no document body or dataset files are hosted
as code assets. The bootstrap *never* overwrites `profiles`.

The `research_profile` Skill can be loaded explicitly by
`load_skills(("research_profile",))`. It does not alter the default existing
Paper Reader/Method Transfer/Idea Critic instructions.

## Workflow

1. Review and annotate the curated *personal/collaborative* profile. Confirm
   which lines the shared team owns and what stage each project is in.
2. Where necessary, edit the profile fields in the draft JSON editor and save
   its revision (does not publish).
3. Optionally configure DeepSeek Key under **AI 选题实验台**, add extra notes,
   and click **LLM 重新生成画像草稿**. This costs an API call and runs only
   when explicitly clicked; no automatic profile model invocation.
4. Review the generated draft, compare research lines and evidence gaps.
5. Only an admin may click **确认并应用到团队画像**, which creates the next
   official profile version and updates the existing research line directory.

## Validation boundaries

- Current CUSP inventory has metadata only; matches do not prove file access,
  data quality, sample sizes, permissions or spatial/temporal compatibility.
- Stated research experience is not automatically a completed publication,
  project award or team-wide verified achievement.
- Abstract-only research discovery still requires independent literature review.
- The DeepSeek model cannot certify novelty; scientific judgment and approval
  remain with team members.
- The free Render database needs durable backups/migration before expiration.
