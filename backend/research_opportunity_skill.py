"""Versioned, bounded research capability bridge for Research Atlas V0.6.

Runs only through the pre-existing team-shared research task worker. This is
not a chat engine, not a private-user memory system, and not a replacement
for the separate experimental three-source L1 pipeline.
"""
from __future__ import annotations

import json
from typing import Any

VERSION = "1.0.0"
TASK_KIND = "research_opportunity"
SCOPE = "team_shared"

CAPABILITIES = {
    "paper_discovery": {
        "label": "论文发现",
        "description": "检索已保存论文与 OpenAlex 元数据，保留真实来源与检索限制。",
        "skills": ("literature_discovery", "paper_reader", "cross_paper_synthesis", "report_templates", "research_opportunity"),
        "instruction": "先列出检索证据，区分已检查摘要与仅有元数据。不得从少量论文推断领域增长趋势。",
    },
    "evidence_review": {
        "label": "证据审查",
        "description": "审阅研究问题、方法、结果主张和证据级别，不冒充全文阅读。",
        "skills": ("paper_reader", "report_templates", "research_opportunity"),
        "instruction": "逐篇给出问题、方法、作者主张、局限和未核验细节；不得推断摘要没有说明的实验结果。",
    },
    "method_transfer": {
        "label": "方法迁移",
        "description": "将计算方法映射到城市问题，识别假设、基线、数据合同与失败条件。",
        "skills": ("literature_discovery", "method_transfer", "report_templates", "research_opportunity"),
        "instruction": "按照问题瓶颈、方法能力、输入输出、简化基线、验证指标和失效条件提出最小实验。",
    },
    "idea_review": {
        "label": "科研选题批判性评估",
        "description": "将研究假设与最近相关工作比较；建议可以为零，不自动认定创新。",
        "skills": ("literature_discovery", "cross_paper_synthesis", "idea_discovery", "idea_critic", "method_transfer", "report_templates", "research_opportunity"),
        "instruction": "首先提出最接近的现有工作与反证，再给出至多三个可证伪假设与 GO/HOLD/REJECT 理由。",
    },
}


def catalog() -> dict[str, Any]:
    return {
        "id": "research_opportunity",
        "version": VERSION,
        "scope": SCOPE,
        "status": "quality_v1_draft",
        "entrypoint": TASK_KIND,
        "capabilities": [
            {"id": code, "label": spec["label"], "description": spec["description"]}
            for code, spec in CAPABILITIES.items()
        ],
        "limits": [
            "团队共享科研任务，不允许用于私聊或敏感个体记录",
            "三源采集与来源强制过滤仍需独立执行链路集成；当前仅为质量规范与Skill装配升级",
            "科研结果是待审草案，不自动批准、发表或更改研究资产",
            "未配置模型密钥时明确显示无模型的文献证据预览",
        ],
    }


def make_payload(capability: str, question: str) -> str:
    if capability not in CAPABILITIES:
        raise ValueError("Unknown research opportunity capability")
    if not isinstance(question, str) or not 6 <= len(question.strip()) <= 1500:
        raise ValueError("Research question must be 6..1500 characters")
    return json.dumps(
        {"version": VERSION, "scope": SCOPE,
         "capability": capability, "question": question.strip()},
        ensure_ascii=False,
    )


def parse_payload(value: str) -> tuple[str, str]:
    try:
        data = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid research opportunity payload") from exc
    if not isinstance(data, dict):
        raise ValueError("Invalid research opportunity payload")
    if data.get("version") != VERSION or data.get("scope") != SCOPE:
        raise ValueError("Unsupported research opportunity version or scope")
    capability = data.get("capability")
    question = data.get("question")
    make_payload(capability, question)  # validate even when reading persisted tasks
    return capability, question.strip()


def task_prompt(capability: str, question: str) -> str:
    spec = CAPABILITIES[capability]
    return (
        "科研任务：" + spec["label"] + "\n"
        "专业要求：" + spec["instruction"] + "\n"
        "证据红线：所有论文主张需保留可核查标题与 URL；明确标记作者声称、"
        "科研假设及核验缺口；不能假定团队数据已获得使用授权；"
        "不能编造模型运行、复现或人工评审。输出仅为待审核草案。\n"
        "研究问题：\n" + question
    )


def execute(db, payload: str, *, log=lambda step, msg: None,
            openalex_client=None, model_client=None, source_context=None) -> dict[str, Any]:
    """Use the existing limited, read-only ResearchAgent; never publish results."""
    capability, question = parse_payload(payload)
    from backend.agent import ResearchAgent

    agent = ResearchAgent(
        db, log=log, openalex_client=openalex_client,
        model_client=model_client, source_context=source_context,
        skill_names=CAPABILITIES[capability]["skills"],
    )
    result = agent.run(task_prompt(capability, question))
    return {
        "skill": "research_opportunity",
        "version": VERSION,
        "scope": SCOPE,
        "capability": capability,
        "review_status": "needs_review",
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "usage": result.get("usage", {}),
        "model_mode": result.get("mode", "unknown"),
        "result": result,
    }
