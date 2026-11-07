# Paper Understanding v1 — Research Reasoning Exemplars

> Status: **draft / pending full-text evidence audit**. Added as versioned development examples, **not** as authoritative scientific ground truth, reviewed training labels, or an evaluation holdout.
> First committed: 2026-11-07. Sources and interpretations come from the preceding human/assistant discussion; this commit does not claim a new line-by-line PDF audit.

## What this contains

| Role | Path | Purpose |
| --- | --- | --- |
| L1 — source evidence | DOI and legal source links in each case | Re-open original paper to verify claims, methods, numbers and tables. Full text is **not** redistributed here. |
| L2 — extended reasoning dossiers | `cases/PU-001.md`, `cases/PU-002.md` | Eight-part paper understanding, problem-reframing logic, evidence limitations, and transferable research insight. |
| L3 — compact reasoning cards | `cards/PU-001.json`, `cards/PU-002.json` | Retrieval-ready examples of *how* valuable research questions emerge, with applicability conditions and counterexamples. |

## Editorial decisions

- **PU-001 — Shen, Xu & Liu (2021):** The human reviewer explicitly chose **scientific problem reframing** as its most valuable transferable insight. The multidimensional measurement framework is a *means of addressing* that problem, not its primary lesson. This is a preference about *what to teach*, **not** independent proof of the paper's novelty.
- **PU-002 — Smith, Shen et al. (2020):** Initial assistant-authored hypothesis: **distributional question reframing**, from aggregate accessibility to occupational-class opportunity disparities. Human confirmation is still pending.
- Both records are **development demonstrations**. Use wholly separate, undisclosed papers for held-out evaluation. Do not leak a target paper's interpretation/answer into its own generation prompt.

## Evidence policy

Every claim must distinguish: (a) source-reported fact or author-stated limitation; (b) analyst inference or criticism; (c) human preference about educational salience. Section references are *navigation hints* until a human verifies the text in the accessible full version. Do not fabricate page numbers, quotations, precise causal findings or missing-literature assertions. Treat unavailable full text as **not read**, never as a research gap.

## Intended integration (not yet implemented)

1. Retrieve a compact card only when its reasoning pattern is relevant and the target paper differs from the exemplar.
2. Provide original paper content and a neutral eight-part protocol to a reading Agent; never supply the same paper's answer card during a blind analysis.
3. Judge the output against cited source passages, not against a single automatic model score or the exemplar's writing style.
4. Accumulate review corrections with source, reviewer status, version and applicability boundaries.
5. Keep these examples separate from team research profiles and experimental facts; no automatic import into production or model fine-tuning.

## External sources

- PU-001: https://doi.org/10.3390/ijgi10110740 (open article: https://www.mdpi.com/2220-9964/10/11/740)
- PU-002: https://doi.org/10.1016/j.jtrangeo.2020.102767 (UCL repository: https://discovery.ucl.ac.uk/id/eprint/10102429/)

Both paper citations refer to scholarly source works. These repository files contain paraphrased analysis rather than full copyrighted source text.
