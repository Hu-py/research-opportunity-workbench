"""Evidence-bounded topic advice and auditable, cumulative experiment accounting."""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base
from backend.ai_lab import PROMPTS, _validated
from backend.model_gateway import request_json


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class TopicArtifact(Base):
    __tablename__ = "topic_advisor_artifacts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40))


def save(factory, kind, content):
    with factory() as db:
        row = TopicArtifact(id=str(uuid.uuid4()), kind=kind, content=encode(content),
                            created_at=datetime.now(timezone.utc).isoformat())
        db.add(row)
        db.commit()
        return row.id


def artifacts(factory, kind):
    with factory() as db:
        return [{"id": x.id, "created_at": x.created_at, "content": json.loads(x.content)}
                for x in db.scalars(select(TopicArtifact).where(TopicArtifact.kind == kind)
                                    .order_by(TopicArtifact.created_at)).all()]


def build_context(factory, line_id):
    """Reuse approved bibliography/metadata and explicitly confirmed decision memory."""
    from backend.ai_lab import _snapshot
    with factory() as db:
        snapshot = _snapshot(db, line_id)
    snapshot["captured_at"] = datetime.now(timezone.utc).isoformat()
    snapshot["availability"] = "metadata_only; data access not verified"
    snapshot["decision_memory"] = [
        {"ref": row["id"], "recorded_at": row["created_at"], **row["content"]}
        for row in artifacts(factory, "decision") if row["content"].get("confirmed")][-20:]
    snapshot["claim_policy"] = "Bibliographic records are sources; model deductions are hypotheses; human decisions are judgments, not verified findings."
    return snapshot


class ExperimentModel:
    """Single-process experiment runner. A file lock serializes all reservations/calls.

    Peak, cache-miss CNY prices checked 2026-11-07 at
    https://api-docs.deepseek.com/zh-cn/quick_start/pricing/.
    UTF-8 bytes + overhead upper-bound input tokens for bounded text-only requests.
    Failed calls retain their entire reservation. Ledger is durable before HTTP.
    """
    def __init__(self, factory, lock_path):
        self.factory, self.lock_path = factory, lock_path

    def call(self, system, payload, model="deepseek-flash", max_tokens=3500):
        import fcntl
        import signal
        import threading
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Paid experiments require the CLI main-thread deadline guard")
        if model not in ("deepseek-flash", "deepseek-v4-pro"):
            raise ValueError("Unsupported priced model")
        if not 1 <= max_tokens <= 4000:
            raise ValueError("Output budget invalid")
        # Cardinality belongs to the stage contract: the reader must cover all
        # supplied papers, and the critic all candidates. Do not truncate either.
        request = {"system": system, "payload": payload, "model": model,
                   "max_tokens": max_tokens, "gateway_version": 1}
        digest = hashlib.sha256(encode(request).encode()).hexdigest()
        input_bound = len(encode(request).encode()) + 2048
        if input_bound > 80000:
            raise ValueError("Input budget exceeded")
        rates = (2, 8) if model == "deepseek-flash" else (9, 27)
        reserve = (input_bound * rates[0] + max_tokens * rates[1]) / 1e6
        with open(self.lock_path, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            records = artifacts(self.factory, "model_call")
            for row in records:
                c = row["content"]
                if c["digest"] == digest and c.get("status") == "completed":
                    return c["result"]
            spent = sum(r["content"].get("charged_bound", r["content"]["reservation"]) for r in records)
            if len(records) >= 60 or spent + reserve > 10:
                raise RuntimeError("Experiment cumulative budget exhausted")
            record = {"digest": digest, "model": model, "reservation": reserve,
                      "status": "reserved", "input_hash": digest, "max_tokens": max_tokens}
            ident = save(self.factory, "model_call", record)
            def deadline(signum, frame):
                raise TimeoutError("Model wall-clock deadline exceeded")
            prior_handler = signal.signal(signal.SIGALRM, deadline)
            signal.alarm(90)
            def observed_usage(usage):
                record["usage"] = usage
            try:
                result, usage = request_json(os.environ["DEEPSEEK_API_KEY"], model,
                                             system, payload, max_tokens=max_tokens, on_usage=observed_usage)
                cost = (usage["input_tokens"] * rates[0] + usage["output_tokens"] * rates[1]) / 1e6
                if usage["input_tokens"] <= 0 or usage["output_tokens"] <= 0:
                    cost = reserve
                record.update(status="completed", result=result, usage=usage,
                              charged_bound=cost, estimated_cny=cost)
            except Exception as exc:
                record.update(status="failed", error=type(exc).__name__,
                              reason=str(exc)[:200] if type(exc).__name__ == "ModelCallError" else "")
                raise
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, prior_handler)
                with self.factory() as db:
                    db.get(TopicArtifact, ident).content = encode(record)
                    db.commit()
            return result


def validate_topics(raw, context):
    ideas = raw.get("ideas")
    if ideas == []:
        return {"ideas": [], "reason": str(raw.get("reason", "证据不足"))[:1000]}
    return _validated("generator", raw, context)


GENERATION_LIMITS = "输出简洁：每个文本字段不超过120字。ideas最多一个，必须包含所有要求字段，包括why_now；其他列表按科学需要完整填写。"
ADVISOR = PROMPTS["generator"] + "允许 ideas 为空并给出 reason。不要为了凑数推荐。" + GENERATION_LIMITS
PATHS = ("已有研究深化", "跨领域方法与数据迁移", "新兴学术前沿")


def advise(model, context, strategy="C", revision=1):
    """A is the existing four-stage prompts/validators, B one call, C three paths plus critic/revision.

    Paths are logically independent; execution is serial to enforce concurrency=1.
    """
    trace = {}
    if strategy == "A":
        for stage in ("planner", "reader", "generator", "critic"):
            payload = {**context, "previous": trace}
            if stage == "critic":
                payload["ideas"] = trace["generator"]["ideas"]
            # Preserve A's existing prompts for an honest baseline replay.
            raw = model.call(PROMPTS[stage], payload)
            trace[stage] = _validated(stage, raw, payload)
        result = trace["generator"]
    elif strategy == "B":
        result = validate_topics(model.call(ADVISOR, context, max_tokens=3500), context)
    elif strategy == "C":
        candidates = []
        for path in PATHS:
            raw = model.call(ADVISOR + "只沿指定路径提出最多一个选题。", {**context, "path": path})
            checked = validate_topics(raw, context)
            candidates.extend(checked["ideas"][:1])
            trace[path] = checked
        if not candidates:
            return {"ideas": [], "trace": trace, "reason": "三条路径均无足够证据"}
        if revision >= 2:
            from backend.scientific_tools import OpenAlexSearchArgs, openalex_search
            plan = model.call("为每个选题生成一个最接近先前研究的英文检索式。返回 JSON queries 字符串数组，最多3项。", {"ideas": candidates})
            retrieved = []
            for query in plan.get("queries", [])[:3]:
                try:
                    response = openalex_search(OpenAlexSearchArgs(query=query, since="2000-01-01", limit=3))
                    retrieved.extend(response["papers"])
                except Exception as exc:
                    trace.setdefault("retrieval_errors", []).append(type(exc).__name__)
            trace["targeted_search"] = {"queries": plan.get("queries", []), "papers": retrieved}
            # Supplement the critic's evidence, but retain original citations for final strict validation.
            context = {**context, "nearest_prior_art": retrieved}
        critique = model.call(PROMPTS["critic"], {**context, "ideas": candidates})
        trace["critic"] = _validated("critic", critique, {"ideas": candidates})
        instruction = ADVISOR + "独立审查后修订，最多三个推荐；严重缺口未解决则删除候选。"
        if revision >= 2:
            instruction += "逐项回答最接近论文已经做了什么、剩余可证伪增量、真实可得最小数据；不要将摘要未提及当作研究缺口。不能解决就返回空列表。"
        result = validate_topics(model.call(instruction, {**context, "candidates": candidates,
                                                         "reviews": trace["critic"]}, max_tokens=3500), context)
    else:
        raise ValueError("Unknown strategy")
    return {**result, "trace": trace, "novelty_status": "unverified",
            "context_hash": hashlib.sha256(encode(context).encode()).hexdigest()}
