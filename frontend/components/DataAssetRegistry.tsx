"use client";

import {useCallback,useEffect,useState} from "react";
import {ArrowRight,Database,FileArchive,FileSpreadsheet,Layers3,Lightbulb,Save,ShieldCheck} from "lucide-react";
import {api} from "@/lib/api";
import CuspDatasetCatalogue from "@/components/CuspDatasetCatalogue";

type Asset={
  id:string;name:string;path:string;format:string;fields:string[];
  spatial_scale:string;time_range:string;description:string;sensitivity:string;
};
type Proposal={
  title:string;hypothesis:string;caveat:string;
  related_data:{id:string;name:string}[];related_research?:{id:string;title:string;url:string}[];evidence_level:string;
};
export default function DataAssetRegistry({canAdmin}:{canAdmin:boolean}){
  const [assets,setAssets]=useState<Asset[]>([]);
  const [proposals,setProposals]=useState<Proposal[]>([]);
  const [directory,setDirectory]=useState("");
  const [selected,setSelected]=useState<string|null>(null);
  const [fields,setFields]=useState("");
  const [spatial,setSpatial]=useState("");
  const [period,setPeriod]=useState("");
  const [description,setDescription]=useState("");
  const [sensitivity,setSensitivity]=useState<"public"|"internal"|"restricted">("internal");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");

  const load=useCallback(async()=>{
    const [a,b]=await Promise.all([
      api<{items:Asset[]}>("data-assets"),
      api<{items:Proposal[]}>("data-assets/opportunities"),
    ]);
    setAssets(a.items);setProposals(b.items);
  },[]);
  useEffect(()=>{void load().catch(e=>setError(String(e)));},[load]);
  async function importTree(){
    setBusy(true);setError("");setNotice("");
    try{
      const res=await api<{new:number;skipped:number;note:string}>("data-assets/import-directory",{
        method:"POST",body:JSON.stringify({listing:directory})
      });
      setNotice("已登记 "+res.new+" 项数据资产（仅目录与格式）。"+res.note);
      setDirectory("");await load();
    }catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  }
  function edit(asset:Asset){
    setSelected(asset.id);setFields(asset.fields.join(", "));
    setSpatial(asset.spatial_scale);setPeriod(asset.time_range);
    setDescription(asset.description);setSensitivity(asset.sensitivity as typeof sensitivity);
  }
  async function save(){
    if(!selected)return;
    setBusy(true);setError("");setNotice("");
    try{
      await api<Asset>("data-assets/"+selected,{method:"PATCH",body:JSON.stringify({
        fields:fields.split(/[,，\n]+/).map(x=>x.trim()).filter(Boolean),
        spatial_scale:spatial,time_range:period,description,sensitivity,
      })});
      setSelected(null);setNotice("数据字典与研究元信息已保存，未上传数据文件。");
      await load();
    }catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  }
  return <div className="repository-root">
    <CuspDatasetCatalogue canAdmin={canAdmin}/>
    <details className="cusp-extra-details">
      <summary>其他目录补充登记（独立于 CUSP 既有数据总表）</summary>
      <div className="repository-root">
    <div className="page-heading"><span className="panel-kicker">TEAM DATA INVENTORY</span>
      <h1>其他目录补充登记</h1>
      <p>此处仅用于新补充的文件目录元信息，不等同于上面的 CUSP 数据登记，也不上传原始数据文件。</p>
    </div>
    <div className="repository-stat-row">
      <div><strong>{assets.length}</strong><span>已登记数据集</span></div>
      <div><strong>{new Set(assets.map(x=>x.format)).size}</strong><span>文件格式类型</span></div>
      <div><strong>{proposals.length}</strong><span>可讨论的方向</span></div>
      <div><strong>{assets.filter(x=>x.fields.length>0).length}</strong><span>已有字段字典</span></div>
    </div>
    <section className="panel">
      <div className="panel-header"><div><span className="panel-kicker">METADATA ONLY</span><h2>导入数据目录</h2></div><FileArchive size={22}/></div>
      <p className="small muted">粘贴文件夹中的相对路径或文件名，每行一项。例如 buildings_2022.shp、POI_floor.csv、OD_2024.parquet。系统不会读取硬盘文件或上传数据内容。</p>
      <textarea className="code-editor" spellCheck={false} rows={7} maxLength={50000}
        readOnly={!canAdmin} value={directory} onChange={e=>setDirectory(e.target.value)}
        placeholder={"Shanghai/buildings_2022.shp\nShanghai/POI_floor.csv\nMobility/OD_2024.parquet\nFlood/pump_stations.geojson"}/>
      <div className="panel-actions">
        <button className="btn btn-primary" onClick={()=>void importTree()} disabled={!canAdmin||busy||!directory.trim()}>
          <FileSpreadsheet size={16}/> 保存目录元数据
        </button>
      </div>
      <p className="small muted"><ShieldCheck size={14} style={{verticalAlign:"middle"}}/> 请不要粘贴人员姓名、密码、原始个人信息或包含秘密标识的目录路径。真正的数据文件可在后续安全存储方案中接入。</p>
    </section>
    {error&&<div className="alert alert-error">{error}</div>}
    {notice&&<div className="alert alert-success">{notice}</div>}
    <div className="content-grid">
      <section className="panel">
        <div className="panel-header"><div><span className="panel-kicker">AVAILABLE INVENTORY</span><h2>数据资产清单</h2></div><Database size={18}/></div>
        {!assets.length?<div className="empty"><Layers3 size={26}/><h3>尚无目录记录</h3><p>先导入文件名，再逐项补充字段、时空覆盖与访问权限。</p></div>:
          <div className="data-asset-list">{assets.map(a=><div className="data-asset-card" key={a.id}>
            <div className="data-asset-heading"><strong>{a.name}</strong><span>{a.format}</span></div>
            <small>{a.path}</small>
            {(a.spatial_scale||a.time_range)&&<p className="small muted">{a.spatial_scale||"空间尺度待填"} · {a.time_range||"时间范围待填"}</p>}
            {!!a.fields.length&&<p className="small muted">字段：{a.fields.slice(0,8).join("、")}</p>}
            {a.description&&<p className="small">{a.description}</p>}
            {canAdmin&&<button className="text-link" onClick={()=>edit(a)}>完善数据字典 <ArrowRight size={14}/></button>}
          </div>)}</div>}
        {selected&&<div className="data-asset-editor">
          <h3>完善数据字典</h3>
          <label>主要字段（用逗号分隔）<textarea rows={3} value={fields} onChange={e=>setFields(e.target.value)}/></label>
          <label>空间尺度<input value={spatial} onChange={e=>setSpatial(e.target.value)} placeholder="例如建筑 / 250m网格 / 街道"/></label>
          <label>时间范围<input value={period} onChange={e=>setPeriod(e.target.value)} placeholder="例如2020–2024，月尺度"/></label>
          <label>数据说明<textarea rows={3} value={description} onChange={e=>setDescription(e.target.value)} placeholder="采集方式、质量、已知限制"/></label>
          <label>敏感级别<select value={sensitivity} onChange={e=>setSensitivity(e.target.value as typeof sensitivity)}>
            <option value="public">公开元数据</option><option value="internal">团队内部</option><option value="restricted">限制访问</option>
          </select></label>
          <div className="inline-actions"><button className="btn btn-primary" disabled={busy} onClick={()=>void save()}><Save size={15}/> 保存</button>
            <button className="btn btn-secondary" onClick={()=>setSelected(null)}>取消</button></div>
        </div>}
      </section>
      <section className="panel">
        <div className="panel-header"><div><span className="panel-kicker">DATA-DRIVEN IDEAS</span><h2>数据可能支持的研究</h2></div><Lightbulb size={18}/></div>
        <p className="small muted">以下为基于目录名称和文件格式的可解释假设，不代表模型已检验数据质量、空间范围或研究可行性。</p>
        {!proposals.length?<div className="empty"><Lightbulb size={26}/><h3>等待数据目录</h3><p>导入 POI、建筑、路网、出行或水系统等数据后，将显示可能的研究方向。</p></div>:
          <div className="data-proposals">{proposals.map(p=><article className="data-proposal" key={p.title}>
            <h3>{p.title}</h3><p>{p.hypothesis}</p><p className="small muted"><b>前提：</b>{p.caveat}</p>
            <div className="repository-tags">{p.related_data.slice(0,4).map(a=><span key={a.id}>{a.name}</span>)}</div>
            {!!p.related_research?.length&&<p className="small muted"><strong>可参考团队已有成果：</strong>{p.related_research.map((o,i)=>
              <span key={o.id}>{i?"；":""}<a href={o.url} rel="noopener noreferrer" target="_blank">{o.title}</a></span>
            )}</p>}
            <small>目录推断 · 待核验</small>
          </article>)}</div>}
      </section>
    </div>
      </div>
    </details>
  </div>;
}
