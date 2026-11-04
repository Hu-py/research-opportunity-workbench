"""Team-owned public research output registry and metadata-only dataset inventory.

Never infer researcher identity from author name alone. Confirmed works come
from curated institutional/publisher sources. Automated OpenAlex ORCID results
are ALWAYS pending-review; they cannot contaminate the verified catalogue.
"""
from __future__ import annotations
import hashlib
import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base, normalize_doi
from backend.team import add_audit

CURATED_PATH=Path(__file__).parent/"data"/"shen_yao_verified.json"
ORCID="0000-0002-7261-4234"
ACADEMIC_API="https://api.openalex.org/works"

def utcnow():
    return datetime.now(timezone.utc)

class TeamAchievement(Base):
    __tablename__="team_achievements"
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    kind:Mapped[str]=mapped_column(String(25),default="paper")
    owner:Mapped[str]=mapped_column(String(100),default="沈尧")
    title:Mapped[str]=mapped_column(Text,nullable=False)
    year:Mapped[int]=mapped_column(Integer,default=0)
    authors:Mapped[str]=mapped_column(Text,default="")
    venue:Mapped[str]=mapped_column(Text,default="")
    doi:Mapped[str]=mapped_column(String(300),default="")
    url:Mapped[str]=mapped_column(Text,default="")
    source_url:Mapped[str]=mapped_column(Text,default="")
    source_kind:Mapped[str]=mapped_column(String(30),default="institution")
    status:Mapped[str]=mapped_column(String(25),default="verified",index=True)
    tags_json:Mapped[str]=mapped_column(Text,default="[]")
    added_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    last_checked:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class ResearchDataAsset(Base):
    __tablename__="team_data_assets"
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    path:Mapped[str]=mapped_column(Text,nullable=False)
    name:Mapped[str]=mapped_column(Text,nullable=False)
    format:Mapped[str]=mapped_column(String(32),default="unknown")
    fields_json:Mapped[str]=mapped_column(Text,default="[]")
    spatial_scale:Mapped[str]=mapped_column(Text,default="")
    time_range:Mapped[str]=mapped_column(Text,default="")
    description:Mapped[str]=mapped_column(Text,default="")
    sensitivity:Mapped[str]=mapped_column(String(24),default="internal")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class ResearchRefreshRun(Base):
    __tablename__="team_research_refresh_runs"
    id:Mapped[str]=mapped_column(String(48),primary_key=True)
    status:Mapped[str]=mapped_column(String(24),default="queued")
    source:Mapped[str]=mapped_column(String(24),default="manual")
    inserted:Mapped[int]=mapped_column(Integer,default=0)
    scanned:Mapped[int]=mapped_column(Integer,default=0)
    error:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

def title_key(raw):
    norm=unicodedata.normalize("NFKC",raw or "").casefold()
    return re.sub(r"[^\w]+","",norm)

def output_id(kind,title):
    key=(kind+"|"+title_key(title)).encode("utf-8")
    return "ach_"+hashlib.sha256(key).hexdigest()[:32]

def public_output(p):
    return {"id":p.id,"kind":p.kind,"owner":p.owner,"title":p.title,
            "year":p.year,"authors":p.authors,"venue":p.venue,"doi":p.doi,
            "url":p.url,"source_url":p.source_url,"source_kind":p.source_kind,
            "status":p.status,"tags":json.loads(p.tags_json or "[]"),
            "added_at":p.added_at.isoformat() if p.added_at else None}

def seed_verified(db):
    """Idempotent insert; never overwrite an already reviewed record."""
    seed=json.loads(CURATED_PATH.read_text(encoding="utf-8"))
    count=0
    for x in seed["items"]:
        rid=output_id(x["kind"],x["title"])
        if db.get(TeamAchievement,rid):
            continue
        db.add(TeamAchievement(id=rid,kind=x["kind"],owner=seed["person"]["name"],
                               title=x["title"],year=x["year"],
                               authors=x.get("authors",""),venue=x.get("venue",""),
                               doi=normalize_doi(x.get("doi","")),url=x.get("url") or x.get("source_url",""),
                               source_url=x.get("source_url",seed["person"]["official_url"]),
                               source_kind="curated_public",status="verified",
                               tags_json=json.dumps(x.get("tags",[]),ensure_ascii=False)))
        count+=1
    db.commit()
    return count

def list_outputs(db,status=None,kind=None,limit=200):
    rows=db.scalars(select(TeamAchievement).order_by(
        TeamAchievement.year.desc(),TeamAchievement.added_at.desc()
    ).limit(400)).all()
    if status:rows=[x for x in rows if x.status==status]
    if kind:rows=[x for x in rows if x.kind==kind]
    return [public_output(x) for x in rows[:limit]]

def update_output_status(db,record_id,status,actor_id):
    if status not in ("verified","review","rejected"):
        raise ValueError("Invalid review status")
    record=db.get(TeamAchievement,record_id)
    if not record:raise ValueError("Research output not found")
    record.status=status
    add_audit(db,"achievement.review",actor_id,record.id,"status="+status)
    db.commit()
    return public_output(record)

def create_refresh(db,source):
    entry=ResearchRefreshRun(id=str(uuid.uuid4()),source=source,status="queued")
    db.add(entry);db.commit()
    return entry

def refresh_public_works(factory,run_id,client=None):
    """ORCID-scoped recent search, never auto-approve newly discovered output."""
    with factory() as db:
        record=db.get(ResearchRefreshRun,run_id)
        if record is None:return
        record.status="running";db.commit()
    try:
        params={
            "filter":"authorships.author.orcid:"+ORCID+",from_publication_date:2022-01-01",
            "sort":"publication_date:desc","per-page":100,
            "select":"id,title,display_name,doi,publication_year,publication_date,authorships,primary_location,type"
        }
        import os
        if os.getenv("OPENALEX_API_KEY"):params["api_key"]=os.environ["OPENALEX_API_KEY"]
        with httpx.Client(timeout=22,headers={"User-Agent":"research-atlas-team-repository/0.1"}) if client is None else _passthrough(client) as http:
            response=http.get(ACADEMIC_API,params=params)
            response.raise_for_status()
            rows=response.json().get("results",[])
        if not isinstance(rows,list):raise ValueError("Unexpected OpenAlex response")
        inserted=0;scanned=0
        with factory() as db:
            existing=db.scalars(select(TeamAchievement)).all()
            known_titles={title_key(r.title) for r in existing}
            known_dois={r.doi.lower() for r in existing if r.doi}
            for work in rows[:100]:
                if not isinstance(work,dict):continue
                # The ORCID filter is necessary but not sufficient; the work
                # must explicitly show the same ORCID on the author entry.
                authorships=work.get("authorships") or []
                owner_authorships=[a for a in authorships if any(
                    ORCID in str(v or "") for v in (
                        (a.get("author") or {}).get("orcid",""),
                        a.get("raw_orcid",""),
                        * ((a.get("author") or {}).get("observed_orcids") or [])
                    )
                )]
                if not owner_authorships:
                    continue
                scanned+=1
                title=(work.get("title") or work.get("display_name") or "").strip()
                if not title:continue
                doi=normalize_doi(work.get("doi",""))
                if title_key(title) in known_titles or doi and doi in known_dois:
                    continue
                year=int(work.get("publication_year") or 0)
                # Ignore records dated in the future.
                if year>utcnow().year or year<2000:continue
                info=work.get("primary_location") or {}
                source=info.get("source") or {}
                kind="paper"
                rid=output_id(kind,title)
                if db.get(TeamAchievement,rid):continue
                author_list="; ".join(
                    (a.get("author") or {}).get("display_name") or ""
                    for a in authorships[:20]
                )
                url=("https://doi.org/"+doi) if doi else str(work.get("id") or "")
                db.add(TeamAchievement(id=rid,kind=kind,owner="沈尧",
                    title=title,year=year,authors=author_list,
                    venue=source.get("display_name") or "",doi=doi,url=url,
                    source_url=str(work.get("id") or url),
                    source_kind="openalex_orcid",status="review",
                    tags_json="[]"))
                known_titles.add(title_key(title))
                if doi:known_dois.add(doi)
                inserted+=1
            run=db.get(ResearchRefreshRun,run_id)
            run.scanned=scanned;run.inserted=inserted;run.status="completed"
            run.finished_at=utcnow()
            db.commit()
    except Exception as exc:
        with factory() as db:
            run=db.get(ResearchRefreshRun,run_id)
            run.status="failed";run.error=str(exc)[:300]
            run.finished_at=utcnow();db.commit()

from contextlib import contextmanager
@contextmanager
def _passthrough(client):
    yield client

FILE_TYPES={
    "csv":"CSV","xlsx":"Excel","xls":"Excel","parquet":"Parquet",
    "shp":"Shapefile","geojson":"GeoJSON","gpkg":"GeoPackage",
    "gdb":"GeoDatabase","tif":"GeoTIFF","tiff":"GeoTIFF",
    "json":"JSON","db":"SQLite","sqlite":"SQLite","nc":"NetCDF",
    "h5":"HDF5","hdf5":"HDF5","zip":"ZIP","pdf":"PDF",
    "txt":"TXT","dwg":"CAD","dxf":"CAD",
}
SHAPE_SIDECARS={"dbf","shx","prj","cpg","qix","sbn","sbx"}

def asset_id(path):
    return "asset_"+hashlib.sha256(path.casefold().encode()).hexdigest()[:32]

def public_asset(a):
    return {"id":a.id,"path":a.path,"name":a.name,"format":a.format,
            "fields":json.loads(a.fields_json or "[]"),"spatial_scale":a.spatial_scale,
            "time_range":a.time_range,"description":a.description,
            "sensitivity":a.sensitivity}

def import_directory_listing(db,listing,actor_id=None):
    """Ingest dataset *metadata*, not file bytes; tree indents are not trusted paths."""
    if len(listing)>50000:raise ValueError("Directory listing exceeds 50,000 characters")
    created=0;skipped=0
    unique=set()
    for raw in listing.splitlines()[:600]:
        line=re.sub(r"^[\s│├└─+|*]+","",raw).strip()
        if not line or len(line)>380 or line.startswith(("#","//")):
            continue
        # Accept either relative paths or the leaf names of a tree listing.
        line=line.strip(" \t").replace("\\","/")
        if line.startswith("/") or re.match(r"^[A-Za-z]:/",line) or ".." in line.split("/"):
            skipped+=1;continue
        suffix=line.rsplit(".",1)[-1].casefold() if "." in line else ""
        if suffix in SHAPE_SIDECARS or suffix not in FILE_TYPES:
            continue
        path=line.strip("/")
        if not path or path.casefold() in unique:continue
        unique.add(path.casefold())
        if db.get(ResearchDataAsset,asset_id(path)):
            skipped+=1;continue
        db.add(ResearchDataAsset(id=asset_id(path),path=path,name=path.split("/")[-1],
            format=FILE_TYPES[suffix],sensitivity="internal"))
        created+=1
    if actor_id:add_audit(db,"data_assets.import",actor_id,"","new="+str(created))
    db.commit()
    return {"new":created,"skipped":skipped,"note":"仅保存文件目录与格式，不上传原始数据"}

def inferred_opportunities(db):
    """Transparent hypothesis templates based only on path metadata."""
    assets=db.scalars(select(ResearchDataAsset)).all()
    if not assets:return []
    text=" ".join((a.path+" "+a.description+" "+a.format) for a in assets).lower()
    rules=[
        (["poi","建筑","building","楼层","floor"],"建筑功能与垂直利用","结合建筑与 POI/楼层信息，探索跨时间的建筑垂直功能识别与空间使用效率。","需要楼层真值、空间关联精度和实际使用验证。"),
        (["路网","street","road","network","networkx","步行"],"时变街道网络与城市韧性","尝试将静态道路拓扑与出行时段数据结合，识别高频网络瓶颈和空间不平等。","需核实道路拓扑连通性、时间戳和流量是否可得。"),
        (["od","信令","gps","mobility","轨迹","刷卡","flow"],"城市流动与功能联系","利用流动网络分析时段功能中心、跨区联系或交通可达性分异。","需核实流动数据的聚合尺度、隐私合规与代表性。"),
        (["雨","泵","闸","淹","flood","water","waterlogging","river"],"防汛调度与时空风险","结合降雨、水位、闸泵记录与路网，提出情景推演和多智能体调度假设。","需明确水动力边界、控制变量、事件记录与验证数据。"),
        (["文物","heritage","保护","历史建筑"],"遗产脆弱性与空间关联","结合建筑状态、环境暴露和群体空间关系，探索可解释的文物风险分级及保护优先序。","需确认文物本体风险标签、邻近关系及保护约束。"),
        (["火灾","fire","消防","drone","无人机"],"低空消防与设施选址","结合火灾事件、风险网格、路网和飞行条件，验证多时段巡检—救援协同选址。","需有真实事件时空信息、飞行净空与建站可行性约束。"),
    ]
    results=[]
    for terms,title,hypothesis,caveat in rules:
        matched=[a for a in assets if any(k in (a.path+" "+a.description+" "+a.format).lower() for k in terms)]
        if not matched:continue
        results.append({"title":title,"hypothesis":hypothesis,"caveat":caveat,
                        "related_data":[{"id":x.id,"name":x.name} for x in matched[:10]],
                        "evidence_level":"仅基于目录名称的初步推测，未经数据内容验证"})
    return results
