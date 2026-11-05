"""Durable per-UTC-day guardrail for paid research-discovery LLM work.

This enforces hard limits on *requests*, *paper evaluations* and conservatively
reserved token allowance. It is NOT an exact USD billing limit: cache hits,
provider pricing and actual tokenisation are provider-controlled.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base

DEFAULT_THEMES = 5
DEFAULT_PAPERS = 80
DEFAULT_CALLS = 30
DEFAULT_TOKEN_ALLOWANCE = 350000
PER_THEME_PAPERS = 16

class ResearchDailyBudget(Base):
    __tablename__ = "research_daily_llm_budget"
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    reserved_calls: Mapped[int] = mapped_column(Integer, default=0)
    reserved_papers: Mapped[int] = mapped_column(Integer, default=0)
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0)
    actual_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    actual_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  default=lambda: datetime.now(timezone.utc))


def _cap(name, default, low, high):
    try:
        return max(low, min(high, int(os.getenv(name, str(default)))))
    except (ValueError, TypeError):
        return default


def limits():
    return {
        "themes_per_run": DEFAULT_THEMES,
        "papers_per_day": _cap("RESEARCH_DAILY_PAPER_LIMIT", DEFAULT_PAPERS, 1, 80),
        "model_calls_per_day": _cap("RESEARCH_DAILY_MODEL_CALL_LIMIT", DEFAULT_CALLS, 1, 30),
        "token_reservation_per_day": _cap(
            "RESEARCH_DAILY_TOKEN_ALLOWANCE", DEFAULT_TOKEN_ALLOWANCE, 20000, 350000
        ),
        "papers_per_theme": PER_THEME_PAPERS,
    }


def reserve(factory, *, tokens=0, papers=0, calls=0, day=None):
    """Atomic conditional reservation, safe across concurrent cron/manual workers.

    Never refund failed paid calls: timeouts and failed responses may still bill.
    """
    day = day or datetime.now(timezone.utc).date().isoformat()
    cfg = limits()
    if tokens < 0 or papers < 0 or calls < 0:
        raise ValueError("Negative budget reservation")
    if papers > cfg["papers_per_day"] or calls > cfg["model_calls_per_day"] or tokens > cfg["token_reservation_per_day"]:
        return False
    for _attempt in range(2):
        with factory() as db:
            if db.get(ResearchDailyBudget, day) is None:
                try:
                    db.add(ResearchDailyBudget(day=day))
                    db.commit()
                except IntegrityError:
                    db.rollback()
            values={
                "reserved_calls": ResearchDailyBudget.reserved_calls + calls,
                "reserved_papers": ResearchDailyBudget.reserved_papers + papers,
                "reserved_tokens": ResearchDailyBudget.reserved_tokens + tokens,
                "updated_at": datetime.now(timezone.utc),
            }
            statement=(update(ResearchDailyBudget)
                .where(ResearchDailyBudget.day == day)
                .where(ResearchDailyBudget.reserved_calls + calls <= cfg["model_calls_per_day"])
                .where(ResearchDailyBudget.reserved_papers + papers <= cfg["papers_per_day"])
                .where(ResearchDailyBudget.reserved_tokens + tokens <= cfg["token_reservation_per_day"])
                .values(**values))
            changed = db.execute(statement)
            db.commit()
            if changed.rowcount:
                return True
    return False


def record_usage(factory, usage, day=None):
    day = day or datetime.now(timezone.utc).date().isoformat()
    with factory() as db:
        db.execute(update(ResearchDailyBudget)
            .where(ResearchDailyBudget.day == day)
            .values(
                actual_input_tokens=ResearchDailyBudget.actual_input_tokens + max(0,int(usage.get("input_tokens",0))),
                actual_output_tokens=ResearchDailyBudget.actual_output_tokens + max(0,int(usage.get("output_tokens",0))),
                updated_at=datetime.now(timezone.utc),
            ))
        db.commit()


def status(db, day=None):
    day = day or datetime.now(timezone.utc).date().isoformat()
    row=db.get(ResearchDailyBudget,day)
    return {
        "utc_day": day, "limits": limits(),
        "used": {"model_calls": row.reserved_calls if row else 0,
                 "papers": row.reserved_papers if row else 0,
                 "token_reservation": row.reserved_tokens if row else 0,
                 "input_tokens": row.actual_input_tokens if row else 0,
                 "output_tokens": row.actual_output_tokens if row else 0},
        "notice": "预算为模型请求次数、论文数和预留 Token 上限；非精确美元账单。预算用尽后停止新增付费请求。",
    }
