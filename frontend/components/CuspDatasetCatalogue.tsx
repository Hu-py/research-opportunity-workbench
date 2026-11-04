"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {Database,FileSpreadsheet,RefreshCw,ShieldCheck,Lightbulb,ChevronDown,ChevronUp,Save,History} from "lucide-react";
import {api} from "@/lib/api";

type CuspDataset={
 id:string;category:string;name:string;format:string;coverage:string;
 period:string;source:string;description:string;prior_research:string;custodian:string;
 f_drive:"listed"|"not_listed"|"unknown";
 backup:"confirmed"|"not_confirmed"|"unknown";
 sensitivity:"public"|"internal"|"restricted";note:string;revision:number;updated_at:string;
};
type Summary={
 total:number;by_category:Record<string,number>;by_format:Record<string,number>;
 f_drive_listed:number;backup_confirmed:number;backup_unknown:number;
 formats_missing:number;owners_known:number;research_used:number;restricted:number;
};
type Proposal={
 title:string;question:string;methods:string;
 supporting_data:{id:string;name:string;period:string;coverage:string;sensitivity:string}[];
 critical_checks:string[];evidence_level:string;
};
type ImportRun={id:string;origin:string;new:number;updated:number;unchanged:number;created_at:string};
type HistoryRecord={revision:number;origin:string;created_at:string;snapshot:Record<string,unknown>};

export default function CuspDatasetCatalogue({canAdmin}:{canAdmin:boolean}){
 const [items,setItems]=useState<CuspDataset[]>([]);
 const [summary,setSummary]=useState<Summary|null>(null);
 const [ideas,setIdeas]=useState<Proposal[]>([]);
 const [runs,setRuns]=useState<ImportRun[]>([]);
 const [category,setCategory]=useState("全部");
 const [search,setSearch]=useState("");
 const [expanded,setExpanded]=useState<string|null>(null);
 const [editing,setEditing]=useState<string|null>(null);
 const [draft,setDraft]=useState<Partial<CuspDataset>>({});
 const [history,setHistory]=useState<HistoryRecord[]>([]);
 const [busy,setBusy]=useState(false);
 const [loaded,setLoaded]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");

 const load=useCallback(async()=>{
   const [a,b,c,d]=await Promise.all([
     api<{items:CuspDataset[]}>("cusp/datasets"),
     api<Summary>("cusp/summary"),
     api<{items:Proposal[]}>("cusp/opportunities"),
     api<{items:ImportRun[]}>("cusp/import-runs")
   ]);
   setItems(a.items);setSummary(b);setIdeas(c.items);setRuns(d.items);setLoaded(true);
 },[]);
 useEffect(()=>{void load().catch(e=>setError(String(e)));},[load]);
 useEffect(()=>{
   const timer=setInterval(()=>{void load().catch(()=>{});},30000);
   return()=>clearInterval(timer);
 },[load]);
 const filtered=useMemo(()=>items.filter(x=>
     (category==="全部"||x.category===category) &&
     (x.name+" "+x.category+" "+x.description+" "+x.prior_research+" "+x.coverage)
       .toLowerCase().includes(search.toLowerCase().trim())
   ),[items,category,search]);

 async function upload(file?:File){
   if(!file)return;
   if(file.size>2_000_000){setError("文件超过 2 MB，请精简登记表后重试。");return;}
   if(!file.name.toLowerCase().endsWith(".xlsx")){setError("只支持 .xlsx 文件。");return;}
   setBusy(true);setError("");setNotice("");
   try{
     const base64=await new Promise<string>((resolve,reject)=>{
       const reader=new FileReader();
       reader.onload=()=>resolve(String(reader.result).split(",").slice(1).join(","));
       reader.onerror=()=>reject(new Error("文件读取失败"));
       reader.readAsDataURL(file);
     });
     const result=await api<{new:number;updated:number;unchanged:number}>(
       "cusp/import-xlsx",{method:"POST",body:JSON.stringify({filename:file.name,file_b64:base64})});
     await load();
     setNotice("Excel 已同步：新增 "+result.new+" 项、更新 "+result.updated+" 项、未变化 "+result.unchanged+" 项。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }

 function edit(row:CuspDataset){setExpanded(row.id);setEditing(row.id);setDraft({...row});}
 async function save(){
   if(!editing)return;
   setBusy(true);setError("");
   try{
     const old=items.find(x=>x.id===editing);
     if(!old)throw new Error("原始记录不存在");
     const keys:(keyof CuspDataset)[]=["category","format","coverage","period",
       "source","description","prior_research","custodian","f_drive","backup","sensitivity","note"];
     const payload:Record<string,string>={};
     for(const key of keys)if(draft[key]!==old[key])payload[key]=String(draft[key]??"");
     if(!Object.keys(payload).length){setEditing(null);return;}
     await api<CuspDataset>("cusp/datasets/"+editing,{method:"PATCH",body:JSON.stringify(payload)});
     await load();setEditing(null);setNotice("数据登记记录已更新并保留修改历史。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function showHistory(id:string){
   try{
     const d=await api<{items:HistoryRecord[]}>("cusp/datasets/"+id+"/history");
     setHistory(d.items);
   }catch(e){setError(e instanceof Error?e.message:String(e));}
 }
 const editField=(name:keyof CuspDataset,value:string)=>setDraft(prev=>({...prev,[name]:value}));
 const textField=(name:keyof CuspDataset,label:string,rows=1)=>(
   <label className="cusp-edit-field"><span>{label}</span>
   {rows===1?<input value={String(draft[name]??"")} onChange={e=>editField(name,e.target.value)}/>:
     <textarea rows={rows} value={String(draft[name]??"")} onChange={e=>editField(name,e.target.value)}/>}
   </label>
 );
 return <section className="cusp-catalogue">
   <div className="panel cusp-heading">
     <div><span className="panel-kicker">CUSP RESEARCH DATA REGISTER</span>
       <h2>团队既有数据总览</h2>
       <p className="small muted">来源：《CUSP数据登记.xlsx》。这里登记数据属性（名称、格式、时间、空间范围、来源及既有研究），不保存 SHP、CSV、影像等原始数据文件。</p>
     </div>
     <div className="cusp-actions">
       <button type="button" className="btn btn-secondary" disabled={busy} onClick={()=>void load()}><RefreshCw size={15}/> 刷新</button>
       {canAdmin&&<label className={"btn btn-primary "+(busy?"cusp-disabled":"")}>
         <FileSpreadsheet size={16}/> {busy?"正在导入":"导入 / 更新 Excel"}
         <input type="file" accept=".xlsx" style={{display:"none"}} disabled={busy}
           onChange={e=>{const file=e.target.files?.[0];void upload(file);e.target.value="";}}/>
       </label>}
     </div>
   </div>
   <div className="repository-stat-row">
     <div><strong>{loaded?(summary?.total??0):"…"}</strong><span>已登记数据集（CUSP）</span></div>
     <div><strong>{summary?.f_drive_listed??0}</strong><span>F盘列已标记（非云端）</span></div>
     <div><strong>{summary?.research_used??0}</strong><span>已记录研究用途</span></div>
     <div><strong>{summary?.backup_unknown??0}</strong><span>备份状态未知</span></div>
   </div>
   {error&&<div className="alert alert-error">{error}</div>}
   {notice&&<div className="alert alert-success">{notice}</div>}
   <div className="panel">
     <div className="panel-header"><div><span className="panel-kicker">COVERAGE</span><h2>分类与信息完整度</h2></div></div>
     <div className="cusp-category-grid">{Object.entries(summary?.by_category||{}).map(([name,count])=>
       <button type="button" key={name}
         className={"cusp-category "+(category===name?"cusp-category-active":"")}
         onClick={()=>setCategory(category===name?"全部":name)}>
         <strong>{count}</strong><span>{name}</span>
       </button>)}</div>
     <p className="small muted">格式未填写：{summary?.formats_missing??0} 项 · 已填写数据持有人：{summary?.owners_known??0} 项 · 敏感元数据标记：{summary?.restricted??0} 项。备份列空白按照“未知”处理，不能视为已备份。</p>
     {!!runs.length&&<p className="small muted">最近一次同步：{runs[0].created_at.slice(0,16).replace("T"," ")} · 新增 {runs[0].new} · 更新 {runs[0].updated} · 未变 {runs[0].unchanged}</p>}
   </div>
   <div className="panel">
     <div className="panel-header"><div><span className="panel-kicker">REGISTER</span><h2>数据集清单</h2></div><Database size={18}/></div>
     <div className="repository-filters">
       <div className="searchbox"><input aria-label="搜索CUSP数据集" placeholder="搜索数据名称、范围、研究用途…" value={search} onChange={e=>setSearch(e.target.value)}/></div>
       <select aria-label="数据分类" value={category} onChange={e=>setCategory(e.target.value)}>
         <option value="全部">全部分类</option>
         {Object.keys(summary?.by_category||{}).map(x=><option key={x} value={x}>{x}</option>)}
       </select>
       <span className="counter">{filtered.length} 项</span>
     </div>
     <div className="cusp-list">{filtered.map(row=><div className="cusp-item" key={row.id}>
       <button className="cusp-item-main" type="button" onClick={()=>{
         setExpanded(expanded===row.id?null:row.id);setEditing(null);setHistory([]);
       }}>
         <span className="cusp-item-title"><strong>{row.name}</strong><small>{row.category} · {row.coverage||"范围未登记"} · {row.period||"时间未登记"}</small></span>
         <span className="cusp-data-chips"><span>{row.format||"格式未知"}</span>
           {row.sensitivity==="restricted"&&<span className="cusp-sensitive">受限元数据</span>}
           {row.f_drive==="listed"&&<span>F盘✓</span>}
         </span>
         {expanded===row.id?<ChevronUp size={16}/>:<ChevronDown size={16}/>}
       </button>
       {expanded===row.id&&<div className="cusp-item-details">
         {editing===row.id?<div className="cusp-edit-grid">
           {textField("category","数据类别")}{textField("format","数据格式")}
           {textField("coverage","空间范围")}{textField("period","时间范围")}
           {textField("source","数据来源",2)}{textField("custodian","数据持有人")}
           {textField("description","字段与基本信息",3)}{textField("prior_research","已用于的研究",3)}
           {textField("note","补充说明",2)}
           <label className="cusp-edit-field"><span>F盘登记</span><select value={draft.f_drive||"unknown"}
             onChange={e=>editField("f_drive",e.target.value)}>
             <option value="listed">已标记</option><option value="not_listed">未标记</option><option value="unknown">未知</option>
           </select></label>
           <label className="cusp-edit-field"><span>备份状态</span><select value={draft.backup||"unknown"}
             onChange={e=>editField("backup",e.target.value)}>
             <option value="confirmed">已确认备份</option><option value="not_confirmed">未确认备份</option><option value="unknown">未知</option>
           </select></label>
           <label className="cusp-edit-field"><span>敏感性</span><select value={draft.sensitivity||"internal"}
             onChange={e=>editField("sensitivity",e.target.value)}>
             <option value="restricted">受限</option><option value="internal">团队内部</option><option value="public">公开元数据</option>
           </select></label>
           <div className="inline-actions"><button className="btn btn-primary" disabled={busy} onClick={()=>void save()}><Save size={15}/> 保存更改</button>
             <button className="btn btn-secondary" onClick={()=>setEditing(null)}>取消</button></div>
         </div>:<>
           <div className="cusp-detail-grid">
             <p><b>基本信息：</b>{row.description||"尚未登记"}</p>
             <p><b>既有研究：</b>{row.prior_research||"尚未登记"}</p>
             <p><b>数据来源：</b>{row.source||"未注明"}</p>
             <p><b>持有人：</b>{row.custodian||"未注明"}</p>
             <p><b>备份：</b>{row.backup==="confirmed"?"已确认":row.backup==="not_confirmed"?"未确认":"未知"}</p>
             <p><b>版本：</b>V{row.revision} · {row.sensitivity==="restricted"?"敏感元数据":"团队内部"}</p>
           </div>
           <div className="inline-actions">
             {canAdmin&&<button className="btn btn-secondary" onClick={()=>edit(row)}>编辑登记</button>}
             <button className="btn btn-secondary" onClick={()=>void showHistory(row.id)}><History size={14}/> 变更记录</button>
           </div>
           {history.length>0&&<div className="cusp-history">{history.map(h=><p key={h.revision}>V{h.revision} · {h.origin} · {h.created_at.slice(0,16).replace("T"," ")}</p>)}</div>}
         </>}
       </div>}
     </div>)}</div>
   </div>
   <section className="panel">
     <div className="panel-header"><div><span className="panel-kicker">DATA-DRIVEN RESEARCH</span><h2>基于既有数据的选题启发</h2></div><Lightbulb size={19}/></div>
     <p className="small muted">下列是由当前登记表自动匹配的可检验研究问题，不是已证明的创新性结论。每项都列出支撑数据和必须核验的缺口；不会自动使用敏感原始数据。</p>
     {ideas.length===0?<p className="small muted">完成数据登记后会生成候选研究问题。</p>:
       <div className="cusp-leads">{ideas.map(p=><article className="data-proposal" key={p.title}>
         <h3>{p.title}</h3><p><b>研究问题：</b>{p.question}</p>
         <p><b>可能方法：</b>{p.methods}</p>
         <div className="repository-tags">{p.supporting_data.map(d=><span key={d.id} title={(d.coverage||"")+" "+(d.period||"")}>{d.name}</span>)}</div>
         {p.critical_checks.map((x,i)=><p key={i} className="small muted"><b>验证条件：</b>{x}</p>)}
         <small>{p.evidence_level}</small>
       </article>)}</div>}
   </section>
   <div className="small-note"><ShieldCheck size={15}/> Excel 重新导入会按数据集名称增量合并并保留历史；网页每 30 秒读取最新登记。若要自动感知 F 盘或网盘文件变化，还需另行连接相应文件系统，当前未实现。</div>
 </section>;
}
