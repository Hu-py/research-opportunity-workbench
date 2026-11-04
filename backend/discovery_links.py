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

THEMES=[
 (("building","vertical","floor","3d","morphology","function","三维","垂直","建筑","楼层","功能","城市肌理"),
  ("建筑","楼层","高度","三维","poi","aoi","形态","功能","超高层","building","floor")),
 (("road","street","network","graph","mobility","traffic","路网","网络","出行","韧性","渗流"),
  ("路网","交通","街道","地铁","公交","od","道路","信令","流动","轨迹","network")),
 (("green","vegetation","urban heat","ecology","绿地","生态","热","暴露"),
  ("绿地","植被","生态","热","ndvi","遥感","环境","ugs","green")),
 (("ses","inequality","segregation","social","population","health","housing","社会","分异","儿童","住房"),
  ("人口","社会","住房","房价","儿童","健康","ses","收入","就业")),
 (("flood","fire","hazard","disaster","resilience","risk","消防","暴雨","韧性","灾害","风险"),
  ("雨","水位","泵","闸","火灾","消防","flood","暴雨","积水","drone","韧性")),
]
STOP={"urban","city","model","method","research","study","spatial","cities"}
def tokens(s):return set(re.findall(r"[a-z][a-z0-9_-]{2,}",s.lower()))-STOP
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
    if not profile:return []
    assets=db.scalars(select(CuspDataset)).all()
    works=db.scalars(select(TeamAchievement).where(TeamAchievement.status=="verified")).all()
    rows=[]
    for line in profile.get("research_lines",[]):
        for kind,entries in (("dataset",assets),("achievement",works)):
            items=[]
            for x in entries:
                label=x.name if kind=="dataset" else x.title
                context=(x.category+" "+x.format+" "+x.description[:120]+" "+x.prior_research[:120]) if kind=="dataset" else x.tags_json+" "+x.venue
                result=_score(line,label+" "+context)
                if not result:continue
                value,reason=result
                items.append({"id":link_id(line["id"],kind,x.id),"line_id":line["id"],
                    "line_name":line["name"],"kind":kind,"reference_id":x.id,
                    "label":label,"score":value,"reason":reason})
            rows.extend(sorted(items,key=lambda v:-v["score"])[:8])
    return rows

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
