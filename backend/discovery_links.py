"""P0: metadata-grounded, reviewable research-line associations."""
import hashlib
import json
import re
from datetime import datetime,timezone
from sqlalchemy import String,Text,Float,DateTime,select
from sqlalchemy.orm import Mapped,mapped_column
from research_workbench.core import Base
from backend.cusp import CuspDataset
from backend.repository import TeamAchievement
from backend.team import add_audit

def utcnow():return datetime.now(timezone.utc)

def link_id(line,kind,rid):
    return "rel_"+hashlib.sha256((line+"|"+kind+"|"+rid).encode()).hexdigest()[:32]

class ResearchLineRelation(Base):
    __tablename__="research_line_relations"
    id:Mapped[str]=mapped_column(String(42),primary_key=True)
    line_id:Mapped[str]=mapped_column(String(110),index=True)
    kind:Mapped[str]=mapped_column(String(22))
    reference_id:Mapped[str]=mapped_column(String(80))
    label:Mapped[str]=mapped_column(Text,default="")
    score:Mapped[float]=mapped_column(Float,default=0)
    reason:Mapped[str]=mapped_column(Text,default="")
    status:Mapped[str]=mapped_column(String(20),default="suggested")
    reviewer_id:Mapped[str]=mapped_column(String(64),default="")
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

def _score(line,source):
    topic=" ".join([line.get("name",""),line.get("problem","")]+line.get("keywords",[])).lower()
    source=source.lower()
    hits=sum(bool(any(k in topic for k in a) and any(k in source for k in b))
             for a,b in THEMES)
    common=sorted(tokens(topic)&tokens(source))[:4]
    if not hits and not common:return None
    score=min(90,42+17*hits+5*len(common))
    reason=(("主题关联"+str(hits)+" 类；" if hits else "")+
            ("文本共同词："+", ".join(common) if common else "基于主题词")+
            "。仅基于登记元数据，尚未经人工确认。")
    return score,reason

def suggestions(db,profile):
    """Return persisted LLM-generated links only; never synthesize lexical matches."""
    lines={x["id"]:x["name"] for x in (profile or {}).get("research_lines",[])}
    rows=db.scalars(select(ResearchLineRelation).order_by(
        ResearchLineRelation.updated_at.desc())).all()
    return [{
        "id":row.id,"line_id":row.line_id,
        "line_name":lines.get(row.line_id,"历史主线"),
        "kind":row.kind,"reference_id":row.reference_id,
        "label":row.label,"score":row.score,"reason":row.reason,
        "status":row.status,
    } for row in rows]

def list_links(db,profile):
    output=suggestions(db,profile)
    saved={x.id:x for x in db.scalars(select(ResearchLineRelation)).all()}
    for item in output:
        row=saved.pop(item["id"],None)
        item["status"]=row.status if row else "suggested"
    for row in saved.values():
        if row.status=="confirmed":
            output.append({"id":row.id,"line_id":row.line_id,
                "line_name":next((x["name"] for x in (profile or {}).get("research_lines",[])
                                  if x["id"]==row.line_id),"历史主线"),
                "kind":row.kind,"reference_id":row.reference_id,
                "label":row.label,"score":row.score,"reason":row.reason,
                "status":row.status})
    return output

def review_link(db,profile,ident,status,actor_id):
    if status not in ("confirmed","rejected","suggested"):
        raise ValueError("Invalid relation decision")
    suggestion=next((x for x in suggestions(db,profile) if x["id"]==ident),None)
    row=db.get(ResearchLineRelation,ident)
    if not row and not suggestion:raise ValueError("Unknown relation")
    if not row:
        row=ResearchLineRelation(id=ident,line_id=suggestion["line_id"],
            kind=suggestion["kind"],reference_id=suggestion["reference_id"],
            label=suggestion["label"],score=suggestion["score"],reason=suggestion["reason"])
        db.add(row)
    row.status=status;row.reviewer_id=actor_id or "";row.updated_at=utcnow()
    add_audit(db,"research_relation.review",actor_id,ident,status)
    db.commit()
    return {"id":ident,"status":status}
