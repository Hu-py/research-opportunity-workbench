"""Offline reproducible Research Atlas urban-health/graph-learning trial.

Input is pinned REAL OpenAlex bibliographic metadata from an existing public
radar snapshot. Outputs are explicitly TITLE-LEVEL RESEARCH HYPOTHESES, not
abstract/full-text scientific validation or an actual ML experiment.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .runner import prepare_paper_snapshot
from .signals import build_research_brief, render_research_brief

CASE_ID = "urban_health_graph_method_transfer"
GROUPS = ("planning_application", "urban_science", "computational_methods")

# Bibliographic evidence anchors deliberately chosen without assuming any result
# beyond the titles of publicly archived OpenAlex records.
CLAIM_BLUEPRINT = {
    "planning_application": {
        "paper_ids": ["W7225271958", "W7225460501", "W7225236930", "W7224775604"],
        "title": "健康目标与环境外推边界需要分别评估",
        "explanation": (
            "四篇题名分别涉及绿色基础设施健康收益、健康公平异质性、"
            "热环境模型时间迁移及空间验证。仅可提出联合审查这些概念的"
            "研究问题，不能据题名断言任何数值结果或迁移方法有效。"
        ),
        "claim": "这些题名共同提示健康目标、空间异质性与模型迁移边界值得分别审查。",
    },
    "urban_science": {
        "paper_ids": ["W7225335274", "W7225455390", "W7223030539"],
        "title": "空间验证、预测不确定性与稀疏标签",
        "explanation": (
            "题名涉及城市感知预测不确定性、少标注半监督空间制图、"
            "及留出街区空间借用的研究设计。需核对摘要和全文才可判断"
            "对街道儿童健康标签的可迁移性。"
        ),
        "claim": "相关题名分别提出不确定性、低标签监督及留区验证这一组待核验的技术问题。",
    },
    "computational_methods": {
        "paper_ids": ["W7220974393", "W7223085329", "W7223225359"],
        "title": "图表示冷启动、噪声标签与域泛化的潜在方法来源",
        "explanation": (
            "三篇题名分别涉及异构图嵌入冷启动、噪声标签学习和零样本域泛化。"
            "这些并非城市健康方法的验证证据；迁移需要证明输入、输出、监督条件"
            "和评估分割与本场景兼容。"
        ),
        "claim": "现有题名提供三个不同的潜在方法切入点，尚无法判断实用性或创新性。",
    },
}

METHOD_TRANSFER = {
    "title": "松江训练到上海其他地区的儿童健康道路预测：空间图学习能否改善可信外推？",
    "status": "hypothesis_not_empirically_tested",
    "problem": "源区域与目标区域环境分布不同、外部道路健康标签稀疏且关联噪声较大。",
    "method_hypothesis": "测试周边统计聚合、图表征和不确定性估计是否分别改善空间留出预测与可靠性。",
    "research_questions": [
        "简单邻域聚合能否在独立空间块及独立城市上稳定优于无图基线？",
        "GraphSAGE 相对于均值/距离加权邻居聚合是否有边际收益？",
        "低有效样本量和训练域外(AOA)条件下，校准与性能差异有多大？",
    ],
    "minimum_baselines": [
        "环境变量 XGBoost（不使用图）",
        "距离/均值邻域聚合 + XGBoost",
        "GraphSAGE embedding + XGBoost",
        "GraphSAGE direct supervised",
    ],
    "validation_protocol": [
        "按独立城市或独立空间区块严格留出，报告与随机道路划分的差异",
        "半径和邻居数量预先指定，验证/测试标签不得参与聚合或训练",
        "分辨样本量差异、标签连接误差与真实域偏移",
        "分别报告 R²、RMSE、MAE、适用域 AOA片区以及置信区间",
        "图节点特征跨区可传播，但目标标签禁止泄漏；记录节点来源",
    ],
    "failure_conditions": [
        "图传播提升仅出现在随机混合划分，不在独立空间或城市留出重现",
        "邻域特征反映目标标签构建过程导致的信息泄漏",
        "图模型效果不超过简单邻域均值且计算成本明显增加",
        "外部健康标签噪声过大，无法形成有效的独立验证",
    ],
    "evidence_boundary": "只有题录级论文输入；本文件未复现实验、未核验文献全文、未证明科学创新性。",
    "evidence_paper_ids": [
        "W7225236930", "W7224775604", "W7223030539",
        "W7220974393", "W7223085329", "W7223225359",
    ],
    "next_review": "选择最近邻论文精读，并以已冻结的模型和外部城市验证协议做预注册对照。",
}


def _registry_for_fixture(papers):
    """Explicit venue aliases; do not classify by topic keyword or prior Radar stream."""
    aliases = {
        "Cities": "Cities",
        "Sustainable Cities and Society": "SCS",
        "Environment and Planning B Urban Analytics and City Science": "EPB",
        "Computers Environment and Urban Systems": "CEUS",
        "IEEE Transactions on Knowledge and Data Engineering": "TKDE",
        "International Journal of Computer Vision": "IJCV",
    }
    return [
        {"name": str(p.get("venue", "")),
         "abbreviation": aliases.get(str(p.get("venue", "")), ""),
         "domain": ""}
        for p in papers if p.get("venue")
    ]


def _proposal(papers):
    indexed = {p["paper_id"]: p for p in papers}
    signals = []
    for group in GROUPS:
        spec = CLAIM_BLUEPRINT[group]
        selected = [pid for pid in spec["paper_ids"]
                    if pid in indexed and group in indexed[pid]["source_groups"]]
        if len(selected) < 2:
            # Do not invent a cross-paper signal if the source pool lacks enough evidence.
            continue
        signals.append({
            "source_group": group,
            "title": spec["title"],
            "explanation": spec["explanation"],
            "paper_ids": selected,
            "gap_status": "not_assessed",
            "trend_status": "multi_paper_observation",
            "team_relevance": "候选方法与场景关联尚未独立验证。",
            "action_suggestion": "先精读相关摘要及原文，再做空间阻断对照实验。",
            "limitations": "本轮仅有 OpenAlex 题名、日期、DOI、期刊等元数据；跨论文结论是研究问题归纳，不是已证实结果。",
            "claims": [{
                "kind": "hypothesis", "statement": spec["claim"], "paper_ids": selected
            }],
        })
    return {"signals": signals}


def build_case(fixture: dict) -> dict:
    if fixture.get("scenario") != CASE_ID:
        raise ValueError("Unexpected scenario")
    raw = fixture.get("papers")
    if not isinstance(raw, list) or not raw:
        raise ValueError("Source snapshot is empty or invalid")
    if any(p.get("abstract") for p in raw):
        raise ValueError("This fixed metadata-only pilot must not silently add abstracts")
    if any(p.get("evidence_level") != "metadata" for p in raw):
        raise ValueError("Metadata-only evidence levels must be explicit")
    if any(not str(p.get("paper_id", "")).startswith("W") or
           not str(p.get("url", "")).startswith("https://doi.org/")
           for p in raw):
        raise ValueError("Every sample requires a plausible OpenAlex work ID and DOI URL")
    registry = _registry_for_fixture(raw)
    papers, coverage = prepare_paper_snapshot(raw, registry, per_group_limit=30)
    if len(papers) != len(raw):
        raise ValueError("Missing or unclassified records in diagnostic sample")
    report = build_research_brief(
        papers, _proposal(papers), period="2026-11-14", coverage=coverage)
    referenced = {pid for signal in report["signals"] for pid in signal["paper_ids"]}
    transfer = dict(METHOD_TRANSFER)
    if not set(transfer["evidence_paper_ids"]).issubset({p["paper_id"] for p in papers}):
        raise ValueError("Method transfer cites an unknown paper")
    digest = hashlib.sha256(
        json.dumps(fixture, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "case_id": CASE_ID,
        "snapshot_sha256": digest,
        "origin": fixture["origin"],
        "sampling_limitations": fixture["limitations"],
        "paper_count": len(papers),
        "signal_count": len(report["signals"]),
        "research_signal_review": report,
        "method_transfer": transfer,
        "signal_reference_ids": sorted(referenced),
        "run_mode": "offline_replay_real_public_metadata",
        "has_live_openalex_retrieval": False,
        "has_paid_model_calls": False,
        "has_empirical_health_model_run": False,
        "scientific_review_status": "needs_review",
    }


def render_case(case: dict) -> str:
    lines = [
        "# 城市健康 × 空间图学习：Research Atlas 科研闭环离线试验",
        "",
        "**状态：** 已走通真实题录快照到科研信号和方法迁移建议的离线流程；"
        "尚未做真实模型调用、全文证据核验或健康模型实验。",
        "",
        "**公开题录数量：** " + str(case["paper_count"]),
        "**三个来源信号数量：** " + str(case["signal_count"]),
        "**快照 SHA256：** \`" + case["snapshot_sha256"] + "\`",
        "",
        "## L0/L1 公开证据",
        "",
        render_research_brief(case["research_signal_review"]),
        "",
        "## 方法迁移待验证协议",
        "",
        case["method_transfer"]["title"],
        "",
        "**研究假设（未验证）：** " + case["method_transfer"]["method_hypothesis"],
        "",
        "### 预注册对照基线",
    ]
    lines.extend("- " + x for x in case["method_transfer"]["minimum_baselines"])
    lines.extend(["", "### 评估协议"])
    lines.extend("- " + x for x in case["method_transfer"]["validation_protocol"])
    lines.extend(["", "### 否证/停止条件"])
    lines.extend("- " + x for x in case["method_transfer"]["failure_conditions"])
    lines.extend(["", "**人工审查：** " + case["method_transfer"]["next_review"],
                  "", "**证据红线：** " + case["method_transfer"]["evidence_boundary"]])
    return "\n".join(lines) + "\n"


def replay_file(path: str | Path) -> dict:
    return build_case(json.loads(Path(path).read_text(encoding="utf-8")))
