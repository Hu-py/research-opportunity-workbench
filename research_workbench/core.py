"""Persistence, source-grounded paper ingestion, and versioned research opportunities."""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def now():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)

class Paper(Base):
    __tablename__ = "papers"
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str] = mapped_column(Text, default="")
    doi: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(Text)
    published: Mapped[str] = mapped_column(String(32), default="")
    venue: Mapped[str] = mapped_column(String(300), default="")
    line_ids: Mapped[str] = mapped_column(Text, default="[]")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Idea(Base):
    __tablename__ = "ideas"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    line_id: Mapped[str] = mapped_column(String(100))
    method: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    hypothesis: Mapped[str] = mapped_column(Text)
    caveat: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="candidate")
    score: Mapped[float] = mapped_column(Float, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_id: Mapped[str] = mapped_column(ForeignKey("ideas.id"))
    paper_id: Mapped[str] = mapped_column(ForeignKey("papers.id"))
    __table_args__ = (UniqueConstraint("idea_id","paper_id",name="uq_idea_paper"),)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_id: Mapped[str] = mapped_column(ForeignKey("ideas.id"))
    version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("idea_id","version",name="uq_idea_version"),)

def session_factory(url=None):
    url = url or os.getenv("DATABASE_URL") or "sqlite:///data/research.db"
    if url.startswith("sqlite:///") and url != "sqlite:///:memory:":
        Path(url[10:]).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)

def validate_profile(profile):
    lines = profile.get("research_lines") if isinstance(profile,dict) else None
    if not isinstance(lines,list) or not lines:
        raise ValueError("research_lines must be a nonempty list")
    ids=set()
    for line in lines:
        if not isinstance(line,dict) or not all(isinstance(line.get(k),str) and line[k].strip() for k in ("id","name","problem")):
            raise ValueError("Each line requires nonempty id, name and problem")
        if line["id"] in ids:
            raise ValueError("Duplicate line id")
        ids.add(line["id"])
        for field in ("keywords","search_queries","method_queries"):
            if not isinstance(line.get(field),list) or not all(isinstance(x,str) for x in line[field]):
                raise ValueError("Each line requires "+field+" as a string list")
        if not line["search_queries"] and not line["method_queries"]:
            raise ValueError("At least one search query is required")

def set_profile(db,profile):
    validate_profile(profile)
    p=db.get(Profile,1)
    if p is None:
        db.add(Profile(id=1,payload=json.dumps(profile,ensure_ascii=False)))
    else:
        p.payload=json.dumps(profile,ensure_ascii=False)
    db.commit()

def get_profile(db):
    p=db.get(Profile,1)
    return json.loads(p.payload) if p else None

def normalize_doi(raw):
    raw=(raw or "").lower().strip()
    for prefix in ("https://doi.org/","http://doi.org/","https://dx.doi.org/","doi:"):
        if raw.startswith(prefix):
            raw=raw[len(prefix):]
            break
    return raw if raw.startswith("10.") and "/" in raw else ""

def decode_abstract(index):
    return " ".join(word for _,word in sorted((int(pos),word) for word,positions in (index or {}).items() for pos in positions))

def normalize_paper(work):
    title=(work.get("title") or work.get("display_name") or "").strip()
    doi=normalize_doi(work.get("doi"))
    key="doi:"+doi if doi else work.get("id") or "title:"+hashlib.sha256(title.lower().encode()).hexdigest()[:24]
    source=(work.get("primary_location") or {}).get("source") or {}
    return dict(id=key,title=title,abstract=decode_abstract(work.get("abstract_inverted_index")),
                doi=doi,url=("https://doi.org/"+doi) if doi else work.get("id") or "",
                published=work.get("publication_date") or "",venue=source.get("display_name") or "")

def query_openalex(query,since,limit=15,client=None):
    params={"search":query,"filter":"from_publication_date:"+since,"sort":"publication_date:desc","per-page":max(1,min(int(limit),100))}
    if os.getenv("OPENALEX_API_KEY"):params["api_key"]=os.environ["OPENALEX_API_KEY"]
    if os.getenv("OPENALEX_MAILTO"):params["mailto"]=os.environ["OPENALEX_MAILTO"]
    own=client is None
    http=client or httpx.Client(timeout=30,headers={"User-Agent":"research-opportunity-workbench/0.1"})
    try:
        for attempt in range(3):
            try:
                r=http.get("https://api.openalex.org/works",params=params)
                if r.status_code in (429,500,502,503,504) and attempt<2:
                    time.sleep(2**attempt);continue
                r.raise_for_status()
                return r.json().get("results",[])
            except (httpx.TransportError,httpx.TimeoutException):
                if attempt==2:raise
                time.sleep(2**attempt)
        return []
    finally:
        if own:http.close()

def ingest(db,profile,days=14,limit=15,client=None):
    if not 1<=days<=3650:raise ValueError("days must be within 1..3650")
    since=(date.today()-timedelta(days=days)).isoformat()
    excluded=[str(x).lower() for x in profile.get("excluded_terms",[]) if str(x).strip()]
    new=0;matched=0;errors=[]
    for line in profile["research_lines"]:
        for q in dict.fromkeys(line["search_queries"]+line["method_queries"]):
            try:
                works=query_openalex(q,since,limit,client)
            except (httpx.HTTPError,ValueError) as ex:
                errors.append({"query":q,"error":str(ex)[:200]});continue
            for work in works:
                data=normalize_paper(work)
                if not data["title"] or any(x in (data["title"]+" "+data["abstract"]).lower() for x in excluded):continue
                matched+=1
                p=db.get(Paper,data["id"])
                if p is None:
                    db.add(Paper(**data,line_ids=json.dumps([line["id"]])));new+=1
                else:
                    ids=set(json.loads(p.line_ids));ids.add(line["id"]);p.line_ids=json.dumps(sorted(ids))
                    for key,value in data.items():
                        if key!="id" and value:setattr(p,key,value)
    db.commit()
    return {"new_papers":new,"matches":matched,"failed_queries":errors,"since":since}

METHODS={
 "self-supervised learning":("self-supervised","contrastive learning","masked modeling"),
 "graph neural networks":("graph neural network","graph transformer","graphsage","heterogeneous graph"),
 "domain adaptation":("domain adaptation","domain generalization","out-of-distribution"),
 "spatiotemporal learning":("spatiotemporal","spatio-temporal","temporal graph"),
 "multi-agent systems":("multi-agent","multi agent","agentic workflow"),
 "world models":("world model","model-based reinforcement learning"),
 "causal inference":("causal inference","counterfactual","causal discovery"),
 "optimization":("mixed-integer","combinatorial optimization","constraint programming"),
 "retrieval augmented generation":("retrieval-augmented","knowledge graph","graph rag")
}

def propose(db,profile):
    papers=db.scalars(select(Paper)).all()
    created=0;updated=0
    for line in profile["research_lines"]:
        methods={}
        for paper in papers:
            if line["id"] not in json.loads(paper.line_ids):continue
            content=(paper.title+" "+paper.abstract).lower()
            fit=sum(k.lower() in content for k in line["keywords"] if k.strip())
            for method,aliases in METHODS.items():
                if any(alias in content for alias in aliases):
                    methods.setdefault(method,[]).append((paper,fit))
        for method,pairs in methods.items():
            key=hashlib.sha256((line["id"]+"\x00"+method).encode()).hexdigest()[:20]
            idea=db.get(Idea,key)
            if idea and idea.status in ("rejected","archived"):continue
            fresh=idea is None
            if fresh:
                idea=Idea(id=key,line_id=line["id"],method=method,title="Evaluate "+method+" for "+line["name"],
                          hypothesis="Test whether "+method+" can address: "+line["problem"],
                          caveat="Method-transfer hypothesis only. Prior-art, scientific novelty and data suitability are NOT verified.",version=1)
                db.add(idea);db.flush()
            existing=set(db.scalars(select(Evidence.paper_id).where(Evidence.idea_id==key)).all())
            pairs.sort(key=lambda x:(x[1],x[0].published),reverse=True)
            missing=[paper for paper,fit in pairs[:10] if paper.id not in existing]
            if not fresh and not missing:continue
            for p in missing:db.add(Evidence(idea_id=key,paper_id=p.id))
            idea.score=min(100,30+7*min(len(existing)+len(missing),5)+4*min(max((f for p,f in pairs),default=0),5))
            if not fresh:idea.version+=1;updated+=1
            else:created+=1
            idea.updated_at=now()
            db.add(Event(idea_id=key,version=idea.version,action="created" if fresh else "evidence_added",
                         detail=json.dumps({"new_paper_ids":[p.id for p in missing]})))
    db.commit()
    return {"new_ideas":created,"revised_ideas":updated}

DECISIONS={"candidate","watch","shortlist","experiment","rejected","archived"}

def feedback(db,idea_id,status,note=""):
    if status not in DECISIONS:raise ValueError("Invalid status")
    idea=db.get(Idea,idea_id)
    if not idea:raise ValueError("Idea not found")
    idea.status=status;idea.version+=1;idea.updated_at=now()
    db.add(Event(idea_id=idea.id,version=idea.version,action="feedback",
                 detail=json.dumps({"status":status,"note":note},ensure_ascii=False)))
    db.commit()

def weekly_report(db,profile,days=7):
    cutoff=(date.today()-timedelta(days=days)).isoformat()
    papers=db.scalars(select(Paper).where(Paper.published>=cutoff).order_by(Paper.published.desc()).limit(20)).all()
    ideas=db.scalars(select(Idea).order_by(Idea.score.desc()).limit(10)).all()
    report=["# Research Opportunity Brief — "+date.today().isoformat(),"",
            "> Evidence-based triage, NOT verified novelty. Dates reflect publication, not indexing.","",
            "## Recent indexed papers",""]
    if not papers:report.append("No recent indexed papers; run ingestion or increase the look-back period.")
    for p in papers:report.append("- ["+p.title.replace("[","\\[").replace("]","\\]")+"]("+p.url+") · "+p.published+" · "+(p.venue or "unverified venue"))
    report+=["","## Rolling method-transfer hypotheses",""]
    if not ideas:report.append("No ideas yet.")
    for idea in ideas:
        report+=["### "+idea.title,"","**Status:** "+idea.status+" · **Version:** "+str(idea.version)+" · **Screening priority:** "+str(round(idea.score))+"/100","",
                 idea.hypothesis,"","**Limitations:** "+idea.caveat,"","**Evidence:**"]
        for pid in db.scalars(select(Evidence.paper_id).where(Evidence.idea_id==idea.id).limit(5)):
            p=db.get(Paper,pid)
            if p:report.append("- ["+p.title+"]("+p.url+")")
        report.append("")
    report+=["## Recommended next steps","","1. Read primary source papers.","2. Search prior art and competing baselines.","3. Update idea status and record experiment outcomes."]
    return "\n".join(report)
