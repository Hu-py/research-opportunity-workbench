"""CUSP's private research-dataset catalogue, reversible metadata history, and
transparent hypothesis generation. No raw research samples or files are stored.

Workbook input is parsed in-memory with Python's standard library; neither the
workbook bytes nor the bootstrap metadata are committed into the public repo.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import unicodedata
import uuid
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from research_workbench.core import Base

HEADERS=["数据类型","名称","格式","范围","时间","数据来源","基本信息",
         "用于的研究（关键结果）","数据持有人","F盘","是否备份"]
COLUMNS={
    "数据类型":"category","名称":"name","格式":"format","范围":"coverage",
    "时间":"period","数据来源":"source","基本信息":"description",
    "用于的研究（关键结果）":"prior_research","数据持有人":"custodian",
    "F盘":"f_drive","是否备份":"backup",
}
SENSITIVE=("儿童健康","手机信令","微博签到","通勤od","病例轨迹","疫情数据",
           "个人轨迹","隐私轨迹","个人隐私","个体健康","身份证","患者信息")
MAX_ROWS=1000

def now():
    return datetime.now(timezone.utc)

def normalized_name(name):
    return re.sub(r"\s+","",unicodedata.normalize("NFKC",name).casefold())

def record_id(name):
    return "cusp_"+hashlib.sha256(normalized_name(name).encode()).hexdigest()[:32]

def clean(value, limit=2200):
    if value is None:return ""
    return str(value).strip()[:limit]

def sensitive_level(name, existing=None):
    if existing:return existing
    return "restricted" if any(token in name.lower() for token in SENSITIVE) else "internal"

class CuspDataset(Base):
    __tablename__="cusp_datasets"
    id:Mapped[str]=mapped_column(String(48),primary_key=True)
    category:Mapped[str]=mapped_column(String(80),default="")
    name:Mapped[str]=mapped_column(Text,nullable=False)
    format:Mapped[str]=mapped_column(String(120),default="")
    coverage:Mapped[str]=mapped_column(Text,default="")
    period:Mapped[str]=mapped_column(String(200),default="")
    source:Mapped[str]=mapped_column(Text,default="")
    description:Mapped[str]=mapped_column(Text,default="")
    prior_research:Mapped[str]=mapped_column(Text,default="")
    custodian:Mapped[str]=mapped_column(String(300),default="")
    f_drive:Mapped[str]=mapped_column(String(24),default="unknown")
    backup:Mapped[str]=mapped_column(String(24),default="unknown")
    sensitivity:Mapped[str]=mapped_column(String(24),default="internal")
    note:Mapped[str]=mapped_column(Text,default="")
    origin:Mapped[str]=mapped_column(String(140),default="CUSP数据登记.xlsx")
    revision:Mapped[int]=mapped_column(Integer,default=1)
    content_hash:Mapped[str]=mapped_column(String(64),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class CuspDatasetRevision(Base):
    __tablename__="cusp_dataset_revisions"
    id:Mapped[str]=mapped_column(String(48),primary_key=True)
    dataset_id:Mapped[str]=mapped_column(String(48),nullable=False,index=True)
    revision:Mapped[int]=mapped_column(Integer,nullable=False)
    actor_id:Mapped[str]=mapped_column(String(64),default="")
    origin:Mapped[str]=mapped_column(String(140),default="")
    snapshot_json:Mapped[str]=mapped_column(Text,default="{}")
    recorded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class CuspImportRun(Base):
    __tablename__="cusp_import_runs"
    id:Mapped[str]=mapped_column(String(48),primary_key=True)
    origin:Mapped[str]=mapped_column(String(140),default="")
    imported:Mapped[int]=mapped_column(Integer,default=0)
    updated:Mapped[int]=mapped_column(Integer,default=0)
    unchanged:Mapped[int]=mapped_column(Integer,default=0)
    actor_id:Mapped[str]=mapped_column(String(64),default="")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

def as_dict(item, redact=False):
    result={k:getattr(item,k) for k in
        ("id","category","name","format","coverage","period","source",
         "description","prior_research","custodian","f_drive","backup",
         "sensitivity","note","origin","revision")}
    result["updated_at"]=item.updated_at.isoformat() if item.updated_at else None
    if redact and item.sensitivity=="restricted":
        result["description"]="涉及敏感个体/轨迹数据，详细信息仅对授权成员开放"
        result["custodian"]=""
        result["source"]=""
        result["note"]=""
    return result

def register_revision(db,item,actor_id,origin):
    snap=as_dict(item)
    db.add(CuspDatasetRevision(
        id=str(uuid.uuid4()),dataset_id=item.id,revision=item.revision,
        actor_id=actor_id or "",origin=origin,
        snapshot_json=json.dumps(snap,ensure_ascii=False),
    ))

def _incoming(row):
    if not isinstance(row,dict):raise ValueError("Each workbook row must be an object")
    name=clean(row.get("名称"),350)
    if not name:raise ValueError("Dataset name is required")
    if len(name)<2:raise ValueError("Invalid dataset name")
    output={attr:clean(row.get(header),limit=350 if attr in
                  ("category","name","format","coverage","period","custodian") else 2100)
            for header,attr in COLUMNS.items()
            if attr not in ("f_drive","backup")}
    mark=clean(row.get("F盘"))
    output["f_drive"]="listed" if mark in ("✅","✓","✔","是","有","true") else "unknown" if not mark or mark=="/" else "not_listed"
    mark=clean(row.get("是否备份"))
    output["backup"]="confirmed" if mark in ("✅","✓","✔","是","有") else "unknown" if not mark or mark=="/" else "not_confirmed"
    return output

def import_records(db,records,actor_id="",origin="CUSP数据登记.xlsx"):
    """Merge by normalized dataset name. Reimport is idempotent and auditable."""
    if not isinstance(records,list) or len(records)>MAX_ROWS:
        raise ValueError("Expected a list with at most 1000 dataset rows")
    inserted=updated=unchanged=0
    ids=set()
    for raw in records:
        data=_incoming(raw)
        rid=record_id(data["name"])
        if rid in ids:raise ValueError("Repeated dataset name in one import")
        ids.add(rid)
        canonical=json.dumps(data,ensure_ascii=False,sort_keys=True)
        digest=hashlib.sha256(canonical.encode()).hexdigest()
        existing=db.get(CuspDataset,rid)
        if existing:
            if existing.content_hash==digest:
                unchanged+=1
                continue
            for key,value in data.items():
                setattr(existing,key,value)
            existing.content_hash=digest
            existing.revision+=1
            existing.updated_at=now()
            updated+=1
            register_revision(db,existing,actor_id,origin)
        else:
            obj=CuspDataset(id=rid,**data,sensitivity=sensitive_level(data["name"]),
                            content_hash=digest,origin=origin,revision=1)
            db.add(obj)
            db.flush()
            inserted+=1
            register_revision(db,obj,actor_id,origin)
    run=CuspImportRun(id=str(uuid.uuid4()),origin=origin,imported=inserted,
                      updated=updated,unchanged=unchanged,actor_id=actor_id or "")
    db.add(run)
    db.commit()
    return {"new":inserted,"updated":updated,"unchanged":unchanged,
            "total_processed":len(records),"import_id":run.id}

def update_one(db,record_id,fields,actor_id=""):
    item=db.get(CuspDataset,record_id)
    if item is None:raise ValueError("Dataset not found")
    valid={"category","format","coverage","period","source","description",
           "prior_research","custodian","f_drive","backup","sensitivity","note"}
    if not fields or not set(fields)<=valid:raise ValueError("Unsupported field")
    for key,value in fields.items():
        if key=="sensitivity" and value not in ("public","internal","restricted"):
            raise ValueError("Invalid sensitivity level")
        if key=="f_drive" and value not in ("listed","not_listed","unknown"):
            raise ValueError("Invalid storage status")
        if key=="backup" and value not in ("confirmed","not_confirmed","unknown"):
            raise ValueError("Invalid backup status")
    modified=any(clean(value)!=getattr(item,key) for key,value in fields.items())
    if modified:
        for key,value in fields.items():setattr(item,key,clean(value))
        item.content_hash=""  # next spreadsheet import may reconcile manual changes
        item.updated_at=now()
        item.revision+=1
        register_revision(db,item,actor_id,"web_edit")
        db.commit()
    return as_dict(item)

def summary(db):
    rows=db.scalars(select(CuspDataset)).all()
    groups=dict(sorted(Counter(d.category or "未分类" for d in rows).items()))
    formats=dict(sorted(Counter(d.format or "未注明" for d in rows).items()))
    return {
        "total":len(rows),"by_category":groups,"by_format":formats,
        "f_drive_listed":sum(d.f_drive=="listed" for d in rows),
        "backup_confirmed":sum(d.backup=="confirmed" for d in rows),
        "backup_unknown":sum(d.backup=="unknown" for d in rows),
        "formats_missing":sum(not d.format for d in rows),
        "owners_known":sum(bool(d.custodian) for d in rows),
        "research_used":sum(bool(d.prior_research) for d in rows),
        "restricted":sum(d.sensitivity=="restricted" for d in rows),
        "last_updated":max((d.updated_at.isoformat() for d in rows if d.updated_at),default=None)
    }

def parse_xlsx(content):
    """Read first worksheet only; no xlsx dependencies, no formulas evaluated."""
    if len(content)>2_000_000:raise ValueError("Workbook exceeds 2 MB")
    ns="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            entries=z.infolist()
            if len(entries)>180 or sum(x.file_size for x in entries)>8_000_000:
                raise ValueError("Workbook contents exceed safe limits")
            names=set(z.namelist())
            if "xl/worksheets/sheet1.xml" not in names:
                raise ValueError("The first worksheet is missing")
            strings=[]
            if "xl/sharedStrings.xml" in names:
                root=ET.fromstring(z.read("xl/sharedStrings.xml"))
                for item in root.findall(ns+"si"):
                    strings.append("".join(t.text or "" for t in item.iter(ns+"t")))
            root=ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
            result=[]
            for row in root.iter(ns+"row"):
                cells={}
                for cell in row.findall(ns+"c"):
                    addr=cell.attrib.get("r","")
                    match=re.match(r"([A-Z]+)",addr)
                    if not match:continue
                    col=0
                    for ch in match.group(1):col=col*26+ord(ch)-64
                    if col>80:continue
                    t=cell.attrib.get("t","")
                    v=cell.find(ns+"v")
                    if t=="inlineStr":
                        item=cell.find(ns+"is")
                        value="".join(x.text or "" for x in item.iter(ns+"t")) if item is not None else ""
                    elif t=="s" and v is not None and v.text:
                        value=strings[int(v.text)]
                    else:
                        value=v.text if v is not None and v.text else ""
                    cells[col-1]=value
                if cells:
                    result.append(cells)
                if len(result)>MAX_ROWS+1:
                    raise ValueError("Too many rows in workbook")
            if not result:raise ValueError("Empty worksheet")
            first=result[0]
            keys={clean(v):k for k,v in first.items()}
            if not all(header in keys for header in HEADERS):
                raise ValueError("Unrecognized spreadsheet headers; expected CUSP data register")
            return [{header:row.get(keys[header],"") for header in HEADERS}
                    for row in result[1:] if clean(row.get(keys["名称"],""))]
    except (zipfile.BadZipFile,ET.ParseError,IndexError,KeyError,ValueError) as e:
        raise ValueError("Cannot parse XLSX: "+str(e)[:140]) from e

def bootstrap_from_env(factory):
    """One-time private metadata import; never echo payload or persist upload bytes."""
    payload=os.getenv("CUSP_DATA_BOOTSTRAP_ZB64","").strip()
    if not payload:return None
    if len(payload)>100_000:raise ValueError("Bootstrap metadata too large")
    raw=base64.urlsafe_b64decode(payload)
    decompressor=zlib.decompressobj()
    expanded=decompressor.decompress(raw,500_000)
    if not decompressor.eof or decompressor.unconsumed_tail:
        raise ValueError("Invalid compressed metadata bootstrap")
    records=json.loads(expanded.decode("utf-8"))
    with factory() as db:
        return import_records(db,records,origin="CUSP数据登记.xlsx · initial_private_import")

def propose_from_existing(db):
    """Rule-based, data-specific hypotheses with explicit temporal and data gaps.
    No model novelty, causal identification or access rights are assumed.
    """
    rows=db.scalars(select(CuspDataset)).all()
    by_name={r.name:r for r in rows}
    def has(terms):
        return [r for r in rows if any(term in r.name.lower() for term in terms)]
    def add(title,question,methods,groups,gaps,priority="待核验"):
        matched=[]
        for terms in groups:
            part=has(terms)
            if not part:return
            matched.extend(part[:3])
        dedup={r.id:r for r in matched}
        proposals.append({
            "title":title,"question":question,"methods":methods,
            "supporting_data":[{"id":r.id,"name":r.name,"period":r.period,
                                "coverage":r.coverage,"sensitivity":r.sensitivity}
                               for r in dedup.values()],
            "critical_checks":gaps,"priority":priority,
            "evidence_level":"依据登记表中的名称、时间、范围与描述进行规则推断；未读取原始数据，也未完成模型验证"
        })
    proposals=[]
    add("城市高温背景下的活动空间暴露与绿地可达性",
        "2025年上海高温期间，群体活动空间是否随绿地与建成环境特征发生系统性变化？",
        "时空暴露指标 / 多层网络 / 敏感性分析",
        [["上海_手机信令数据(上海高温)"],["绿地数据","ugs-1m"],["上海_aoi"]],
        ["尚未登记逐小时气温、热暴露与遮阴数据；绿地/AOI为2024而信令为2025；必须先确认轨迹使用授权和去标识化。"])
    add("城市公共空间功能与线上活动表达的错位",
        "上海在线签到的活动地点与城市功能设施之间是否存在时段、群体和空间尺度差异？",
        "地点语义映射 / 时空聚类 / 偏差校正",
        [["上海_微博签到数据_2024"],["上海_aoi","上海_餐饮数据"]],
        ["社交平台样本存在选择偏差；2023餐饮和2024/25签到时点不一致；不能使用可识别用户ID生成公开分析。"])
    add("极端暴雨下的城市出行网络韧性",
        "郑州暴雨期间不同出行方式的空间网络失效与恢复呈现何种差异？",
        "交通网络扰动模拟 / 多尺度韧性 / 情景反事实",
        [["郑州_手机信令数据(暴雨)"],["路网数据"]],
        ["需核实暴雨发生时间与信令年份是否匹配；缺少同一时期郑州地铁网络、积水边界和设备停运记录；出行数据权限待核验。"])
    add("多城市建筑肌理与绿色空间网络的耦合",
        "建成形态、街道网络与城市绿地的连通结构是否共同影响空间韧性？",
        "空间渗流 / 图表示 / 跨城市分层验证",
        [["100个城市_建筑"],["全国_路网"],["全国_绿地","31个城市_ugs"]],
        ["先核实100城市与绿地数据的空间交集、分辨率、投影和年份；建筑边界数据不等于建筑高度或楼层标签。"])
    add("住房价格与城市空间网络的时空非线性关联",
        "如何将房价、POI与街道网络结合，区分区域差异、网络可达性与城市形态效应？",
        "空间图学习 / 固定效应或空间面板 / 跨城泛化",
        [["房价数据"],["poi数据"],["路网数据"]],
        ["2019/2023房价与2020 POI年份不齐；需检查房屋地址关联、重复记录与空间自相关；不能仅凭相关性解释因果。"])
    add("全球超高层增长与城市可达性结构",
        "不同城市高层建筑发展阶段与公共交通、功能密度有何动态关联？",
        "三维城市测度 / 城市层面比较 / 时序模型",
        [["超高层建筑"],["公交和地铁"],["poi数据"]],
        ["全球超高层与全国交通/POI数据空间范围并不一致，只能先匹配中国城市；建筑用途和人口/使用强度尚未核实。"])
    add("儿童健康与建成环境的跨城市外推",
        "在合法合规和聚合尺度下，城市空间环境与儿童健康结局的关联能否跨城市迁移？",
        "空间异质性 / 域泛化 / 组间稳健性",
        [["儿童健康数据"],["poi数据"],["路网数据"]],
        ["高度敏感的儿童与家庭资料：先核实知情同意、伦理审查、访问权限和最小化处理；POI时点/14城覆盖需要对齐；不得直接使用个体身份信息。"])
    add("上海多期流动数据的城市韧性变化",
        "2021与2025不同采集场景下的上海出行网络结构是否具有稳定的可迁移模式？",
        "时空对齐 / 网络基线 / 分布漂移诊断",
        [["上海_手机信令数据_202110"],["上海_手机信令数据(上海高温)"]],
        ["不同年份和采集口径未必可比；2025含高温情景效应，必须区分采样变化和真实结构变化。"])
    return proposals
