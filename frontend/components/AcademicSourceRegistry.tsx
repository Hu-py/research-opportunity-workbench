"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {Plus,RefreshCw,Search,Download,Upload,CheckCircle2,AlertCircle,Power,Save,X} from "lucide-react";
import {api} from "@/lib/api";

type Source={id:string;name:string;abbreviation:string;kind:"journal"|"conference";domain:string;
 rank_label:string;ranking_system:string;source_url:string;aliases:string[];notes:string;
 enabled:boolean;is_seed:boolean;openalex_source_id:string;resolution_status:string;
 resolution_note:string;openalex_type:string};
type Summary={total:number;enabled:number;resolved:number;unresolved:number;direct_enabled:number;direct_resolved:number;method_enabled:number;method_resolved:number};
type Draft=Omit<Partial<Source>,"name"|"kind"|"domain"|"aliases">&{
 name:string;kind:"journal"|"conference";domain:string;aliases:string[]|string
};
const domains=[
 ["urban_planning","城市规划与城市研究"],["gis_spatial","GIS 与空间计算"],
 ["urban_environment","城市环境"],["urban_health","城市健康"],["transportation","交通与出行"],
 ["heritage","遗产保护"],["water_disaster","水系统与灾害"],["ai_ml","人工智能与机器学习"],
 ["data_mining","数据挖掘与数据库"],["cv_multimodal","计算机视觉与多模态"],["nlp","自然语言处理"],
 ["agents_robotics","Agent 与机器人"],["hci","人机交互"],["graphics_visualization","图形学与可视化"],
 ["systems_software","系统与软件"],["network_security","网络与安全"],
 ["computer_architecture","计算机体系结构"],["theory_algorithms","理论与算法"],
] as const;
const empty:Draft={name:"",abbreviation:"",kind:"journal",domain:"urban_planning",rank_label:"重点",
 ranking_system:"团队自定义来源",source_url:"",aliases:[],notes:"",enabled:true};
export default function AcademicSourceRegistry({canAdmin}:{canAdmin:boolean}){
 const [items,setItems]=useState<Source[]>([]),[summary,setSummary]=useState<Summary|null>(null);
 const [q,setQ]=useState(""),[domain,setDomain]=useState("all"),[kind,setKind]=useState("all"),[status,setStatus]=useState("all");
 const [draft,setDraft]=useState<Draft|null>(null),[editing,setEditing]=useState<string|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 function patchDraft(patch:Partial<Draft>){setDraft(d=>d?{...d,...patch}:d);}
 function patchDraftText(key:keyof Draft,value:string){setDraft(d=>d?{...d,[key]:value}:d);}
 const load=useCallback(async()=>{const d=await api<{items:Source[];summary:Summary}>("research-sources");setItems(d.items);setSummary(d.summary);},[]);
 useEffect(()=>{void load().catch(e=>setError(String(e)));},[load]);
 const visible=useMemo(()=>items.filter(x=>(domain==="all"||x.domain===domain)&&(kind==="all"||x.kind===kind)&&
 (status==="all"||(status==="enabled"&&x.enabled)||(status==="disabled"&&!x.enabled)||
 (status==="unresolved"&&x.enabled&&x.resolution_status!=="resolved"))&&
 (x.name+" "+x.abbreviation+" "+x.aliases.join(" ")+" "+x.notes).toLowerCase().includes(q.toLowerCase())),
 [items,domain,kind,status,q]);
 function edit(x:Source){setEditing(x.id);setDraft({...x});setError("");setNotice("");}
 async function save(){
  if(!draft)return;setBusy(true);setError("");setNotice("");
  try{
   const payload={...draft,aliases:Array.isArray(draft.aliases)?draft.aliases:[]};
   if(editing)await api("research-sources/"+editing,{method:"PATCH",body:JSON.stringify(payload)});
   else await api("research-sources",{method:"POST",body:JSON.stringify(payload)});
   setDraft(null);setEditing(null);await load();setNotice("来源信息已保存。");
  }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 async function toggle(x:Source){
  setBusy(true);setError("");try{await api("research-sources/"+x.id,{method:"PATCH",body:JSON.stringify({enabled:!x.enabled})});await load();}
  catch(e){setError(String(e));}finally{setBusy(false);}
 }
 async function resolve(ids:string[],force=false){
  setBusy(true);setError("");setNotice("");
  try{const result=await api<{checked:number;resolved:number;ambiguous:number;not_found:number;errors:number}>("research-sources/resolve",
   {method:"POST",body:JSON.stringify({ids,force})});await load();
   setNotice("核验完成：本次检查 "+result.checked+"，已匹配 "+result.resolved+"，歧义 "+result.ambiguous+"，未找到 "+result.not_found+"，请求错误 "+result.errors+"。");
  }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 function exportCsv(){
  const cols=["name","abbreviation","kind","domain","rank_label","ranking_system","source_url","enabled","openalex_source_id","aliases","notes"];
  const quote=(v:unknown)=>'"'+String(Array.isArray(v)?v.join("|"):v??"").replace(/"/g,'""')+'"';
  const csv=[cols.join(","),...items.map(x=>cols.map(k=>quote((x as any)[k])).join(","))].join("\n");
  const blob=new Blob(["\\ufeff",csv],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="academic-source-registry.csv";a.click();URL.revokeObjectURL(url);
 }
 async function importCsv(file:File){
  const text=await file.text();const lines=text.replace(/^\\ufeff/,"").split(/\\r?\\n/).filter(Boolean);
  if(lines.length<2)return;
  const parse=(line:string)=>{const out:string[]=[];let cur="",quoted=false;for(let i=0;i<line.length;i++){const c=line[i];if(c==='"'&&line[i+1]==='"'){cur+='"';i++;}else if(c==='"')quoted=!quoted;else if(c===","&&!quoted){out.push(cur);cur="";}else cur+=c;}out.push(cur);return out;};
  const headers=parse(lines[0]);const rows=lines.slice(1).map(line=>Object.fromEntries(parse(line).map((v,i)=>[headers[i],v])));
  setBusy(true);setError("");let added=0,failed=0;
  try{for(const row of rows){try{await api("research-sources",{method:"POST",body:JSON.stringify({...row,enabled:row.enabled!=="false",aliases:(row.aliases||"").split("|").filter(Boolean)})});added++;}catch{failed++;}}
   await load();setNotice("导入完成：新增 "+added+" 条，失败/重复 "+failed+" 条。");
  }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 const field=(label:string,key:keyof Draft)=><label className="field"><span>{label}</span><input value={String(draft?.[key]??"")} onChange={e=>patchDraftText(key,e.target.value)}/></label>;
 return <div className="page">
  <div className="page-header"><div><div className="eyebrow">ACADEMIC INTELLIGENCE / REGISTRY</div><h1>学术来源管理</h1><p>统一维护期刊、会议、学科标签与检索来源核验。来源等级是检索先验，不是单篇论文质量结论。</p></div>
   <div className="actions"><button className="btn" onClick={()=>void load()} disabled={busy}><RefreshCw size={15}/>刷新</button>{canAdmin&&<button className="btn primary" onClick={()=>{setEditing(null);setDraft({...empty});}}><Plus size={15}/>新增来源</button>}</div>
  </div>
  {summary&&<div className="stats-grid">
   <div className="stat-card"><span>来源总数</span><strong>{summary.total}</strong></div><div className="stat-card"><span>启用来源</span><strong>{summary.enabled}</strong></div>
   <div className="stat-card"><span>OpenAlex 已核验</span><strong>{summary.resolved}</strong></div><div className="stat-card"><span>待核验</span><strong>{summary.unresolved}</strong></div>
  </div>}
  <div className="panel">
   <div className="toolbar"><div className="search-box"><Search size={16}/><input placeholder="搜索期刊、会议、简称或别名" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <select value={domain} onChange={e=>setDomain(e.target.value)}><option value="all">全部领域</option>{domains.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>
    <select value={kind} onChange={e=>setKind(e.target.value)}><option value="all">期刊 + 会议</option><option value="journal">期刊</option><option value="conference">会议</option></select>
    <select value={status} onChange={e=>setStatus(e.target.value)}><option value="all">全部状态</option><option value="enabled">启用</option><option value="disabled">停用</option><option value="unresolved">待核验</option></select>
   </div>
   <div className="toolbar secondary">{canAdmin&&<><button className="btn" disabled={busy} onClick={()=>void resolve(items.filter(x=>x.enabled&&x.resolution_status!=="resolved").map(x=>x.id))}><CheckCircle2 size={15}/>核验待处理来源</button><button className="btn" disabled={busy} onClick={()=>void resolve([],true)}><RefreshCw size={15}/>强制重新核验</button><label className="btn"><Upload size={15}/>导入 CSV<input hidden type="file" accept=".csv,text/csv" onChange={e=>{const f=e.target.files?.[0];if(f)void importCsv(f);e.currentTarget.value="";}}/></label></>}
    <button className="btn" onClick={exportCsv}><Download size={15}/>导出 CSV</button>
   </div>
   {error&&<div className="alert alert-error">{error}</div>}{notice&&<div className="alert alert-success">{notice}</div>}
   <div className="source-table-wrap"><table className="source-table"><thead><tr><th>来源</th><th>领域</th><th>类型 / 等级</th><th>OpenAlex 核验</th><th>状态</th><th>操作</th></tr></thead><tbody>
   {visible.map(x=><tr key={x.id}><td><strong>{x.name}</strong><small>{x.abbreviation} · {x.ranking_system}</small>{x.source_url&&<a href={x.source_url} target="_blank" rel="noreferrer">官方网站 ↗</a>}</td>
    <td>{domains.find(d=>d[0]===x.domain)?.[1]||x.domain}</td><td>{x.kind==="journal"?"期刊":"会议"} · {x.rank_label}</td>
    <td>{x.resolution_status==="resolved"?<><span className="tag good">已核验</span><small>{x.openalex_source_id}</small></>:<span className="tag warn">{x.resolution_status==="ambiguous"?"匹配歧义":x.resolution_status==="not_found"?"未找到":"待核验"}</span>}</td>
    <td><span className={"tag "+(x.enabled?"good":"muted")}>{x.enabled?"启用":"停用"}</span></td>
    <td className="row-actions">{canAdmin&&<><button className="btn small" onClick={()=>edit(x)}>编辑</button><button className="btn small" onClick={()=>void toggle(x)}>{x.enabled?"停用":"启用"}</button>{x.resolution_status!=="resolved"&&<button className="btn small" onClick={()=>void resolve([x.id],true)}>核验</button>}</>}</td>
   </tr>)}
   {!visible.length&&<tr><td colSpan={6} className="empty-cell">没有符合条件的来源</td></tr>}
   </tbody></table></div>
  </div>
  {draft&&<div className="modal-backdrop"><div className="modal source-modal"><div className="modal-head"><div><div className="eyebrow">SOURCE RECORD</div><h2>{editing?"编辑学术来源":"新增学术来源"}</h2></div><button className="icon-btn" onClick={()=>{setDraft(null);setEditing(null);}}><X size={18}/></button></div>
   <div className="form-grid">{field("来源全称","name")}{field("简称","abbreviation")}
    <label className="field"><span>来源类型</span><select value={draft.kind} onChange={e=>patchDraft({kind:e.target.value as "journal"|"conference"})}><option value="journal">期刊</option><option value="conference">会议</option></select></label>
    <label className="field"><span>研究领域</span><select value={draft.domain} onChange={e=>patchDraft({domain:e.target.value})}>{domains.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
    {field("等级标签","rank_label")}{field("等级依据 / 评价体系","ranking_system")}
    {field("官方主页 HTTPS","source_url")}
    <label className="field"><span>别名（用 | 分隔）</span><input value={Array.isArray(draft.aliases)?draft.aliases.join(" | "):String(draft.aliases||"")} onChange={e=>patchDraft({aliases:e.target.value})}/></label>
    <label className="field full"><span>研究主题说明</span><textarea value={draft.notes||""} onChange={e=>patchDraft({notes:e.target.value})}/></label>
    <label className="field"><span>OpenAlex Source ID</span><input value={draft.openalex_source_id||""} onChange={e=>patchDraft({openalex_source_id:e.target.value})} placeholder="可留空，之后自动核验"/></label>
    <label className="field check"><input type="checkbox" checked={draft.enabled!==false} onChange={e=>patchDraft({enabled:e.target.checked})}/>启用该来源</label>
   </div>
   <div className="modal-foot"><button className="btn" onClick={()=>{setDraft(null);setEditing(null);}}>取消</button><button className="btn primary" disabled={busy||!draft.name?.trim()} onClick={()=>void save()}><Save size={15}/>保存</button></div>
  </div></div>}
 </div>;
}
