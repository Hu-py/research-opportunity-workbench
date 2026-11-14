"""Evidence-bounded L1 research-signal outputs for Research Atlas.

This module validates *model proposals* against retrieved paper records. It
does not claim that reference existence verifies an academic gap or novelty.
All outputs remain review drafts; L2/L3 are optional, not mandatory.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from .sources import SOURCE_GROUPS

ALLOWED_EVIDENCE = {"metadata", "abstract_excerpt", "abstract", "full_text"}
ALLOWED_CLAIM_KINDS = {"paper_statement", "author_claim", "cross_paper_synthesis", "hypothesis"}
ALLOWED_GAP_STATES = {"not_assessed", "author_claim_only", "compared_to_prior_art"}
ALLOWED_TREND_STATES = {"single_paper", "multi_paper_observation", "historically_compared"}


def _text(value: Any, limit: int = 1200) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _unique_strings(value: Any) -> list[str]:
    return list(dict.fromkeys(str(item) for item in value if isinstance(item, (str, int)) and str(item).strip())) if isinstance(value, list) else []


def _paper_index(papers: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Normalize records without treating model-generated metadata as evidence."""
    index: dict[str, dict[str, Any]] = {}
    for paper in papers:
        if not isinstance(paper, Mapping):
            continue
        ident = str(paper.get("paper_id") or paper.get("id") or "").strip()
        if not ident or ident in index:
            continue
        level = paper.get("evidence_level") or "metadata"
        if level not in ALLOWED_EVIDENCE:
            level = "metadata"
        groups = [group for group in _unique_strings(paper.get("source_groups", []))
                  if group in SOURCE_GROUPS]
        index[ident] = {
            "paper_id": ident,
            "title": _text(paper.get("title"), 400),
            "url": _text(paper.get("url"), 1200),
            "doi": _text(paper.get("doi"), 180),
            "published": _text(paper.get("published"), 60),
            "venue": _text(paper.get("venue"), 200),
            "source_groups": groups,
            "evidence_level": level,
        }
    return index


def build_research_brief(
    papers: list[Mapping[str, Any]],
    proposal: Mapping[str, Any],
    *,
    period: str = "",
    coverage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one L0/L1 draft; reject invented references, not silently omit them.

    Claims are not verified by this function: validation checks whether cited IDs
    exist in the supplied evidence snapshot and whether source membership holds.
    """
    index = _paper_index(papers)
    if not isinstance(proposal, Mapping):
        raise ValueError("model output must be a JSON object")
    candidates = proposal.get("signals", [])
    if not isinstance(candidates, list):
        raise ValueError("signals must be a list")
    signals = []
    for number, raw in enumerate(candidates):
        if not isinstance(raw, Mapping):
            raise ValueError("signal must be a JSON object")
        group = raw.get("source_group")
        if group not in SOURCE_GROUPS:
            raise ValueError("unknown Research Atlas source group")
        paper_ids = _unique_strings(raw.get("paper_ids", []))
        if not paper_ids or any(pid not in index for pid in paper_ids):
            raise ValueError("signal cites a paper absent from evidence snapshot")
        if any(group not in index[pid]["source_groups"] for pid in paper_ids):
            raise ValueError("signal cites a paper outside its claimed source group")
        title = _text(raw.get("title"), 220)
        explanation = _text(raw.get("explanation"), 3000)
        if not title or not explanation:
            raise ValueError("signal needs title and substantive explanation")
        claims = []
        for c in raw.get("claims", []):
            if not isinstance(c, Mapping):
                raise ValueError("claim must be a JSON object")
            linked = _unique_strings(c.get("paper_ids", []))
            if not linked or any(pid not in paper_ids for pid in linked):
                raise ValueError("claim lacks traceable signal references")
            if c.get("kind") not in ALLOWED_CLAIM_KINDS:
                raise ValueError("invalid claim kind")
            statement = _text(c.get("statement"), 1600)
            if not statement:
                raise ValueError("claim statement missing")
            claims.append({"statement": statement, "kind": c["kind"], "paper_ids": linked})
        if not claims:
            raise ValueError("signal must contain evidence-linked claims")
        gap_state = raw.get("gap_status", "not_assessed")
        trend_state = raw.get("trend_status", "multi_paper_observation" if len(paper_ids) > 1 else "single_paper")
        if gap_state not in ALLOWED_GAP_STATES or trend_state not in ALLOWED_TREND_STATES:
            raise ValueError("invalid evidence status")
        if trend_state != "single_paper" and len(paper_ids) < 2:
            raise ValueError("one paper cannot establish a multi-paper trend")
        if trend_state == "historically_compared" and not raw.get("comparison_window"):
            raise ValueError("historical trend needs a recorded comparison window")
        signals.append({
            "signal_id": "signal_" + str(number + 1),
            "source_group": group,
            "title": title,
            "explanation": explanation,
            "paper_ids": paper_ids,
            "claims": claims,
            "gap_status": gap_state,
            "trend_status": trend_state,
            "comparison_window": _text(raw.get("comparison_window"), 200),
            "team_relevance": _text(raw.get("team_relevance"), 1400),
            "team_fit_status": "unverified",
            "action_suggestion": _text(raw.get("action_suggestion"), 700),
            "limitations": _text(raw.get("limitations"), 1300),
            "review_status": "needs_review",
            "depth_level": "L1",
        })
    counts = Counter(group for p in index.values() for group in p["source_groups"])
    return {
        "schema_version": "0.1",
        "period": _text(period, 50),
        "status": "needs_review",
        "sources": {
            group: {"distinct_papers": counts[group]} for group in SOURCE_GROUPS
        },
        "paper_count_unique": len(index),
        "coverage": dict(coverage or {}),
        "papers": list(index.values()),
        "signals": signals,
        "deep_reads": [],
        "research_opportunities": [],
        "notes": "L0/L1 draft only. Paper IDs are verified against input; scientific claims still require human review.",
    }


def render_research_brief(report: Mapping[str, Any]) -> str:
    """Readable three-source draft; no forced single-paper or opportunity sections."""
    labels = {
        "planning_application": "A 规划应用实践",
        "urban_science": "B 城市科学视角",
        "computational_methods": "C 计算机科学方法",
    }
    papers = {p["paper_id"]: p for p in report.get("papers", [])}
    lines = [
        "# Research Atlas 科研信号周报 " + _text(report.get("period"), 50),
        "",
        "> AI 研究草案，待人工审核；论文 ID 存在不代表研究 Gap 或创新性已证实。",
        "",
        "## L0 采集概况",
        "",
        "全局去重论文：" + str(report.get("paper_count_unique", 0)),
    ]
    for group in SOURCE_GROUPS:
        items = [signal for signal in report.get("signals", [])
                 if signal.get("source_group") == group]
        lines.extend(["", "## " + labels[group], "",
                      "本来源论文：" + str(report.get("sources", {}).get(group, {}).get("distinct_papers", 0))])
        if not items:
            lines.append("本期暂无通过结构校验的重点研究信号。")
        for signal in items:
            lines.extend(["", "### " + _text(signal.get("title"), 220), "",
                          _text(signal.get("explanation"), 3000), "",
                          "**研究缺口审查状态：** " + str(signal.get("gap_status", "not_assessed")),
                          "**团队关联（待核验）：** " + (_text(signal.get("team_relevance"), 1400) or "暂无明确关联"),
                          "**建议动作：** " + (_text(signal.get("action_suggestion"), 700) or "持续观察"),
                          "**关键论点及依据：**"])
            for claim in signal.get("claims", []):
                lines.append("- " + _text(claim.get("statement"), 1600) + " [" + ",".join(claim.get("paper_ids", [])) + "]")
            lines.append("**参考文献：**")
            for pid in signal.get("paper_ids", []):
                p = papers[pid]
                title = p.get("title") or pid
                url = p.get("url") or ""
                lines.append("- " + ("[" + title.replace("]", "") + "](" + url + ")" if url.startswith("https://") else title) +
                             " — " + pid + "（" + p.get("evidence_level", "metadata") + "）")
            if signal.get("limitations"):
                lines.append("**局限：** " + signal["limitations"])
    lines.extend(["", "## 审查说明", "",
                  "L2 单篇深读与 L3 研究选题为可选产物；本版仅形成可核验来源的 L0/L1 草案。"])
    return "\n".join(lines) + "\n"
