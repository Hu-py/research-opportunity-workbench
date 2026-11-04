"""CUSP metadata import does not ingest research samples or publish raw workbook."""
import base64
import io
import json
import zipfile
import zlib

import pytest
from sqlalchemy import select

from backend.cusp import (
    HEADERS,CuspDataset,CuspDatasetRevision,import_records,parse_xlsx,
    bootstrap_from_env,propose_from_existing,summary,update_one,record_id,
)
from research_workbench.core import session_factory


def make_row(name,category="城市功能与设施",period="2025",drive="✅"):
    return {"数据类型":category,"名称":name,"格式":"csv","范围":"上海",
        "时间":period,"数据来源":"测试数据源","基本信息":"测试字段",
        "用于的研究（关键结果）":"","数据持有人":"测试成员",
        "F盘":drive,"是否备份":""}


def xlsx_bytes(records):
    cols="ABCDEFGHIJK"
    xml=['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for idx,values in enumerate([HEADERS]+[[r.get(k,"") for k in HEADERS] for r in records],1):
        xml.append('<row r="%d">'%idx)
        for j,content in enumerate(values):
            xml.append('<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>'%
                (cols[j],idx,str(content).replace("&","&amp;")))
        xml.append("</row>")
    xml.append("</sheetData></worksheet>")
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w",zipfile.ZIP_DEFLATED) as zipfile_out:
        zipfile_out.writestr("xl/worksheets/sheet1.xml","".join(xml))
    return stream.getvalue()


def test_xlsx_upsert_revision_and_statistics(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"cusp.db"))
    values=[make_row("全国_poi数据_2020"),make_row("全国_路网数据","地理与空间单元")]
    assert len(parse_xlsx(xlsx_bytes(values)))==2
    with factory() as db:
        assert import_records(db,values)["new"]==2
        assert import_records(db,values)["unchanged"]==2
        assert summary(db)["total"]==2
        assert summary(db)["backup_unknown"]==2
        assert summary(db)["f_drive_listed"]==2
        values[1]["时间"]="2026"
        assert import_records(db,values)["updated"]==1
        item=db.get(CuspDataset,record_id("全国_路网数据"))
        assert item.period=="2026" and item.revision==2
        assert len(db.scalars(select(CuspDatasetRevision)).all())==3
        assert update_one(db,item.id,{"backup":"confirmed"})["backup"]=="confirmed"
        assert item.revision==3
        assert len(db.scalars(select(CuspDataset)).all())==2


def test_bootstrap_runs_only_with_private_env_variable(tmp_path,monkeypatch):
    factory=session_factory("sqlite:///"+str(tmp_path/"bootstrap.db"))
    rows=[make_row("上海_绿地数据_2024")]
    payload=base64.urlsafe_b64encode(zlib.compress(json.dumps(rows,ensure_ascii=False).encode())).decode()
    monkeypatch.setenv("CUSP_DATA_BOOTSTRAP_ZB64",payload)
    assert bootstrap_from_env(factory)["new"]==1
    assert bootstrap_from_env(factory)["unchanged"]==1
    monkeypatch.delenv("CUSP_DATA_BOOTSTRAP_ZB64")
    assert bootstrap_from_env(factory) is None


def test_parser_rejects_invalid_file_and_ideas_are_not_claimed_as_verified(tmp_path):
    with pytest.raises(ValueError):parse_xlsx(b"random")
    factory=session_factory("sqlite:///"+str(tmp_path/"idea.db"))
    with factory() as db:
        import_records(db,[
            make_row("全国_房价数据_2019(2023)","社会经济"),
            make_row("全国_poi数据_2020"),
            make_row("全国_路网数据","地理与空间单元"),
        ])
        ideas=propose_from_existing(db)
        assert any("房价" in x["title"] for x in ideas)
        assert all(x["supporting_data"] and x["critical_checks"] and
                   "未读取原始数据" in x["evidence_level"] for x in ideas)
