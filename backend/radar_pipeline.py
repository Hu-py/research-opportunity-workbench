"""Persistent Radar layer connecting reviewed AI hypotheses to weekly research briefs.

Safeguards:
- Only sourced, database-backed paper IDs may enter Radar.
- Five review gates are screening evidence, never a claim of novelty.
- AI draft cards stay drafts until a human reviews them.
- Similar cards are merged without overwriting manually assigned statuses.
- No unpublished research report is automatically committed to a public repository.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone, date
from difflib import SequenceMatcher
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base, Paper
from backend.ai_lab import AIOpportunity


def now():
    return datetime.now(timezone.utc)


def loads(value, fallback=None):
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, list if isinstance(fallback, list) else dict) else fallback
    except (TypeError, ValueError):
        return fallback if fallback is not None else {}


def dump(value):
    return json.dumps(value, ensure_ascii=False)


class RadarTopic(Base):
    __tablename__ = "radar_topics"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    line_id: Mapped[str] = mapped_column(String(110), index=True)
    title: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text)
    grade: Mapped[str] = mapped_column(String(1), default="C")
    gates_json: Mapped[str] = mapped_column(Text, default="{}")
    paper_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    dataset_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    ai_card_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(24), default="candidate")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RadarTopicEvent(Base):
    __tablename__ = "radar_topic_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RadarReport(Base):
    __tablename__ = "radar_reports"
    period: Mapped[str] = mapped_column(String(12), primary_key=True)
    markdown: Mapped[str] = mapped_column(Text)
    topic_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def _clean(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE)[:500]


def _similar(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(a=a, b=b).ratio()


def assess(card):
    """Conservative five-gate pre-review based ONLY on known input fields.

    A registered dataset means it exists in the inventory, NOT that it is
    legally accessible, has sufficient coverage or has been inspected.
    """
    paper_ids = loads(card.paper_ids_json, [])
    dataset_ids = loads(card.dataset_ids_json, [])
    baselines = loads(card.baselines_json, [])
    risks = loads(card.risks_json, [])
    review = loads(card.critic_json, {})
    question = (card.question or "").strip()
    experiment = (card.experiment or "").strip()
    verdict = review.get("verdict", "需要补充证据")
    possible_construct_errors = ["健康效应", "因果效应", "居民置换", "实际使用", "causal effect", "displacement"]
    construct_flag = any(w in (question + " " + experiment).casefold() for w in possible_construct_errors)
    gates = {
        "planning_question": {
            "status": "初步通过" if len(question) >= 12 else "待完善",
            "note": "已提出研究问题；是否具有规划意义须由研究者审核",
        },
        "data_access": {
            "status": "待预检" if dataset_ids else "阻断",
            "note": "关联了数据台账，但并未验证数据权限、粒度、质量、可下载性" if dataset_ids else
                    "未关联可用的数据资产；不得把假定可以获取的数据当作已拥有",
        },
        "construct_validity": {
            "status": "待核验" if construct_flag else "初步通过",
            "note": "涉及健康、因果、置换或实际使用构念，须核对直接测量和识别设计" if construct_flag else
                    "尚未核对变量与构念的一致性，初步通过不等于构念已验证",
        },
        "prior_art": {
            "status": "未核验",
            "note": "有参考论文不等于完成先前研究检索；不能以检索结果少证明新颖性",
        },
        "scope": {
            "status": "待完善" if not (experiment and baselines) else "待预检",
            "note": "需要限定最小样本、对照指标、失败标准；有基线和实验文字不等于可执行",
        },
    }
    if verdict == "暂缓" or card.status == "rejected":
        grade = "D"
    elif not paper_ids or not dataset_ids:
        grade = "C"
    else:
        # Without an independently checked acquisition path + prior-art search,
        # an automatic pipeline MUST NOT award A.
        grade = "B"
    return {
        "grade": grade,
        "gates": gates,
        "verdict": verdict,
        "novelty": "未核验",
        "fatal_gaps": [str(x)[:350] for x in review.get("fatal_gaps", []) if isinstance(x, str)][:8],
        "risks": [str(x)[:350] for x in risks if isinstance(x, str)][:8],
        "minimum_data": [str(x)[:350] for x in review.get("minimum_data", []) if isinstance(x, str)][:8],
        "stop_conditions": [str(x)[:350] for x in review.get("stop_conditions", []) if isinstance(x, str)][:8],
        "note": "A 级需人工完成数据预检、近邻文献核验和研究设计审核；B 为有条件候选，C 为待解决前置条件，D 为暂缓。",
    }


def _as_list(raw):
    return list(dict.fromkeys(str(s) for s in loads(raw, []) if isinstance(s, str)))[:100]


def sync_ai_opportunities(db, limit=180):
    """Idempotent import of AI cards into the long-lived topic pool.

    Matching uses conservative near-identical wording within a research line.
    More semantic clustering requires explicit human review.
    """
    if not 1 <= limit <= 500:
        raise ValueError("Invalid limit")
    existing = list(db.scalars(select(RadarTopic)).all())
    cards = db.scalars(select(AIOpportunity).order_by(AIOpportunity.created_at.asc()).limit(limit)).all()
    added = updated = skipped = 0
    for card in cards:
        if not card.title or not card.question or not _as_list(card.paper_ids_json):
            skipped += 1
            continue
        valid_paper_ids = [x for x in _as_list(card.paper_ids_json) if db.get(Paper, x)]
        if not valid_paper_ids:
            skipped += 1
            continue
        title_key = _clean(card.title)
        match = next((x for x in existing if x.line_id == card.line_id and (
            _clean(x.title) == title_key or
            (_similar(_clean(x.title), title_key) >= 0.9 and
             _similar(_clean(x.question), _clean(card.question)) >= 0.82)
        )), None)
        checked = assess(card)
        if match is None:
            ident = "radar_" + hashlib.sha256((card.line_id + "|" + title_key).encode()).hexdigest()[:24]
            match = RadarTopic(
                id=ident, line_id=card.line_id, title=card.title, question=card.question,
                method=card.method or "", grade=checked["grade"],
                gates_json=dump(checked), paper_ids_json=dump(valid_paper_ids),
                dataset_ids_json=dump(_as_list(card.dataset_ids_json)),
                ai_card_ids_json=dump([card.id]), version=1,
                status=("shortlist" if card.status=="shortlist" else
                        "rejected" if card.status=="rejected" else "candidate"),
            )
            db.add(match)
            db.flush()
            existing.append(match)
            db.add(RadarTopicEvent(
                topic_id=ident, version=1, action="created",
                detail_json=dump({"card_id": card.id, "papers_added": valid_paper_ids}),
            ))
            added += 1
            continue
        old_ids = _as_list(match.ai_card_ids_json)
        old_papers = _as_list(match.paper_ids_json)
        if card.id in old_ids:
            continue
        newly_added = [x for x in valid_paper_ids if x not in old_papers]
        match.ai_card_ids_json = dump((old_ids + [card.id])[:100])
        match.paper_ids_json = dump((old_papers + newly_added)[:100])
        match.dataset_ids_json = dump(list(dict.fromkeys(
            _as_list(match.dataset_ids_json) + _as_list(card.dataset_ids_json)))[:100])
        # Human status never overwritten; grade may downgrade, never
        # automatically upgrade based on unverified AI evidence.
        if checked["grade"] == "D":
            match.grade = "D"
        elif match.grade not in ("D",):
            match.grade = min(match.grade, checked["grade"])
        match.version += 1
        match.updated_at = now()
        db.add(RadarTopicEvent(
            topic_id=match.id, version=match.version, action="new_evidence",
            detail_json=dump({"card_id": card.id, "papers_added": newly_added}),
        ))
        updated += 1
    db.commit()
    return {"new_topics": added, "revised_topics": updated, "skipped_cards": skipped}


ALLOWED_TOPIC_STATUSES = {"candidate", "watch", "shortlist", "experiment", "rejected", "archived"}


def review_topic(db, topic_id, status, note=""):
    """Human feedback is versioned and never erased by later AI imports."""
    if status not in ALLOWED_TOPIC_STATUSES:
        raise ValueError("Unsupported Radar status")
    if not isinstance(note, str) or len(note) > 1500:
        raise ValueError("Radar note exceeds limit")
    topic = db.get(RadarTopic, topic_id)
    if topic is None:
        raise ValueError("Radar topic not found")
    if topic.status == status and not note.strip():
        return topic_dict(topic, db)
    topic.status = status
    topic.version += 1
    topic.updated_at = now()
    db.add(RadarTopicEvent(
        topic_id=topic.id, version=topic.version, action="human_review",
        detail_json=dump({"status":status,"note":note.strip()}),
    ))
    db.commit()
    return topic_dict(topic, db)


def topic_dict(topic, db):
    ids = _as_list(topic.paper_ids_json)
    papers = [db.get(Paper, x) for x in ids[:12]]
    return {
        "id": topic.id, "title": topic.title, "question": topic.question,
        "line_id": topic.line_id, "method": topic.method,
        "grade": topic.grade, "status": topic.status, "version": topic.version,
        "review": loads(topic.gates_json, {}),
        "papers": [
            {"id":p.id, "title":p.title, "url":p.url, "doi":p.doi, "venue":p.venue}
            for p in papers if p
        ],
        "related_ai_cards": len(_as_list(topic.ai_card_ids_json)),
        "history": [
            {"version":e.version,"action":e.action,
             "detail":loads(e.detail_json,{}),
             "created_at":e.created_at.isoformat() if e.created_at else None}
            for e in db.scalars(select(RadarTopicEvent).where(
                RadarTopicEvent.topic_id==topic.id
            ).order_by(RadarTopicEvent.version.desc()).limit(20))
        ],
        "updated_at": topic.updated_at.isoformat() if topic.updated_at else None,
    }


def list_topics(db, limit=100):
    return [topic_dict(x, db) for x in db.scalars(
        select(RadarTopic).order_by(RadarTopic.updated_at.desc()).limit(min(max(1,limit),200))
    ).all()]


def generate_weekly(db, period=None, persist=True):
    """Generate a private Markdown digest; DB is the durable source of truth."""
    period = period or f"{date.today().isocalendar().year}-W{date.today().isocalendar().week:02d}"
    topics = db.scalars(select(RadarTopic).order_by(RadarTopic.updated_at.desc()).limit(100)).all()
    counts = {g: sum(t.grade == g for t in topics) for g in "ABCD"}
    lines = [
        "# 科研雷达 · " + period, "",
        "> 来源：数据库中经过 AI 初步分析的论文及候选选题；不是原创性查重报告。", "",
        f"累计候选 {len(topics)} 项 · A {counts['A']} / B {counts['B']} / C {counts['C']} / D {counts['D']}", "",
        "## 滚动选题池与五道评审门", "",
    ]
    if not topics:
        lines.append("尚无已完成 AI 分析的候选题。本期保留空报告，不生成虚构论文或研究选题。")
    for topic in topics[:20]:
        reviewed = loads(topic.gates_json, {})
        lines.extend([
            f"### [{topic.grade}] {topic.title} · v{topic.version}", "",
            f"- 研究问题：{topic.question}",
            f"- 研究方向 ID：{topic.line_id}",
            f"- 当前状态：{topic.status}（需要研究者人工审核）",
            f"- 创新性：未核验；AI 评审结论：{reviewed.get('verdict','需要补充证据')}",
        ])
        for key, label in (
            ("planning_question","规划问题"), ("data_access","数据可得"),
            ("construct_validity","构念有效"), ("prior_art","文献增量"),
            ("scope","研究规模"),
        ):
            gate = reviewed.get("gates", {}).get(key, {})
            lines.append(f"- {label}：{gate.get('status','未知')} — {gate.get('note','')}")
        for gap in reviewed.get("fatal_gaps", [])[:3]:
            lines.append(f"- 风险：{gap}")
        if reviewed.get("minimum_data"):
            lines.append("- 最小数据要求：" + "；".join(reviewed["minimum_data"][:3]))
        if reviewed.get("stop_conditions"):
            lines.append("- 停止条件：" + "；".join(reviewed["stop_conditions"][:3]))
        lines.append("- 原始文献：")
        for pid in _as_list(topic.paper_ids_json)[:6]:
            paper = db.get(Paper,pid)
            if paper and paper.url.startswith("https://"):
                lines.append(f"  - [{paper.title}]({paper.url})")
        lines.append("")
    lines.extend(["## 使用说明", "",
                  "- A 级不会由当前自动化流程直接授予；人工核验数据、文献后才可以升级。",
                  "- 已登记数据不代表已合法获取，也不代表足以支撑模型或因果推断。",
                  "- 语义聚类仅做高置信度相似合并，其他相关选题需人工合并。",
                  "- 本报告默认仅保存于私有数据库和受控运行产物，公开 GitHub 不存放研究计划。", ""])
    markdown = "\n".join(lines)
    if persist:
        item = db.get(RadarReport, period)
        if item is None:
            db.add(RadarReport(period=period, markdown=markdown, topic_count=len(topics)))
        else:
            if item.markdown != markdown:
                item.markdown = markdown
                item.topic_count = len(topics)
                item.updated_at = now()
        db.commit()
    return markdown


def recent_reports(db, limit=12):
    return [
        {"period":x.period, "topic_count":x.topic_count,
         "created_at":x.created_at.isoformat() if x.created_at else None,
         "updated_at":x.updated_at.isoformat() if x.updated_at else None}
        for x in db.scalars(select(RadarReport).order_by(RadarReport.period.desc()).limit(limit))
    ]


def get_report(db, period):
    record = db.get(RadarReport, period)
    return record.markdown if record else None
