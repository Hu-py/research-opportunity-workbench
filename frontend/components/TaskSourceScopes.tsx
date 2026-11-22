"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {AlertCircle,BookOpen,Check,ChevronDown,ChevronRight,Loader2,LockKeyhole,Plus,RefreshCw,Search,ShieldCheck,SlidersHorizontal,X} from "lucide-react";
import {api} from "@/lib/api";
import styles from "./TaskSourceScopes.module.css";

export type SourceBand="A"|"B"|"C";
export type SourceGroups=Record<SourceBand,string[]>;
export type ScopeScene="team_weekly"|"personal_weekly"|"directed_research";
type Source={
 id:string;name:string;abbreviation:string;kind:"journal"|"conference";
 domain:string;enabled:boolean;resolution_status:string;openalex_source_id:string;
};
type Scope={
 scene:ScopeScene; groups:SourceGroups; enforced:boolean;configured:boolean;
 version:number;selected_count?:number;resolved_count?:number;
 missing_or_unresolved?:number; available?:boolean;updated_at?:string|null;
};
type SourceResult={items:Source[]};
type ScopeResult={items:Scope[];personal_available:boolean};
const scenes:Record<ScopeScene,{title:string;caption:string;note:string}>={
 team_weekly:{
  title:"团队科研周报",caption:"SC01 / TEAM WEEKLY",
  note:"独立配置团队每周要扫描的应用、前沿和方法期刊。仅管理员可修改。",
 },
 personal_weekly:{
  title:"个人科研周报",caption:"SC02 / PERSONAL WEEKLY",
  note:"每位研究者的专属来源列表，不能自动共享给团队。个人报告生成能力仍需独立接入。",
 },
 directed_research:{
  title:"定向科研任务",caption:"SC03 / DIRECTED RESEARCH",
  note:"保存定向研究的默认来源范围。每次执行时还可以单独覆盖，且会冻结本次清单。",
 },
};
const bands:Record<SourceBand,{title:string;sub:string}>={
 A:{title:"A · 应用场景",sub:"城市规划与具体应用的研究实践"},
 B:{title:"B · 前沿视角",sub:"问题重构、城市科学与空间研究"},
 C:{title:"C · 技术方法",sub:"计算机顶会和可迁移的方法增量"},
};
const blank:SourceGroups={A:[],B:[],C:[]};
function copyGroups(groups:SourceGroups):SourceGroups{
 return {A:[...(groups?.A||[])],B:[...(groups?.B||[])],C:[...(groups?.C||[])]};
}
function sourceState(source?:Source){
 if(!source)return "来源记录已删除";
 if(!source.enabled)return "目录中已停用";
 return source.resolution_status==="resolved"&&source.openalex_source_id?"已核验":"未核验";
}

export function SourceGroupPicker({sources,groups,onChange,disabled=false,compact=false}:{
 sources:Source[];groups:SourceGroups;onChange:(next:SourceGroups)=>void;disabled?:boolean;compact?:boolean;
}){
 const [active,setActive]=useState<SourceBand>("A");
 const [query,setQuery]=useState("");
 const [expanded,setExpanded]=useState(!compact);
 const map=useMemo(()=>new Map(sources.map(s=>[s.id,s])),[sources]);
 const filtered=useMemo(()=>sources.filter(s=>s.enabled&&
   (s.name+" "+s.abbreviation+" "+s.domain).toLowerCase().includes(query.toLowerCase())
 ).sort((a,b)=>(a.domain=== "urban_planning"?0:1)-(b.domain==="urban_planning"?0:1)||a.name.localeCompare(b.name)).slice(0,80),
 [sources,query]);
 const selectedIds=groups?.[active]||[];
 const move=(id:string)=>{
   if(disabled)return;
   const wasSelected=selectedIds.includes(id);
   const next=copyGroups(groups);
   for(const band of ["A","B","C"] as SourceBand[])next[band]=next[band].filter(x=>x!==id);
   if(!wasSelected)next[active]=[...next[active],id];
   onChange(next);
 };
 return <div className={styles.picker}>
   <div className={styles.bandTabs}>
    {(["A","B","C"] as SourceBand[]).map(band=><button key={band} type="button"
      className={active===band?styles.bandActive:""}
      onClick={()=>{setActive(band);setExpanded(true);}}>
      <strong>{bands[band].title}</strong><small>{groups?.[band]?.length||0} 个来源</small>
    </button>)}
   </div>
   <div className={styles.bandContent}>
    <div className={styles.bandTitle}><div><strong>{bands[active].title}</strong><p>{bands[active].sub}</p></div>
      <button type="button" className={styles.textAction} onClick={()=>setExpanded(!expanded)}>
        <ChevronDown size={14}/>{expanded?"收起来源选择":"选择期刊或会议"}
      </button>
    </div>
    <div className={styles.selectedSources}>
     {selectedIds.length?selectedIds.map(id=>{
       const source=map.get(id);
       return <span className={styles.sourceChip} key={id}>
         <BookOpen size={12}/><span>{source?.abbreviation||source?.name||id}</span>
         {sourceState(source)!=="已核验"&&<i title={sourceState(source)}><AlertCircle size={12}/></i>}
         {!disabled&&<button type="button" aria-label={"移除 "+(source?.name||id)} onClick={()=>move(id)}><X size={12}/></button>}
       </span>;
     }):<p className={styles.blankText}>尚未选择此类别的来源。严格模式下不会从该类别无约束扩展检索。</p>}
    </div>
    {expanded&&<div className={styles.sourceChoices}>
      <label className={styles.sourceSearch}><Search size={14}/><input value={query} onChange={e=>setQuery(e.target.value)}
        placeholder="搜索统一目录中的期刊、会议、简称" /></label>
      <div className={styles.choicesList}>
       {filtered.length?filtered.map(source=>{
        const inBand=selectedIds.includes(source.id);
        const other=(["A","B","C"] as SourceBand[]).find(b=>b!==active&&groups?.[b]?.includes(source.id));
        return <button type="button" key={source.id} disabled={disabled}
          className={styles.choice+(inBand?" "+styles.choiceSelected:"")} onClick={()=>move(source.id)}>
          <span className={styles.choiceCheck}>{inBand?<Check size={13}/>:<Plus size={13}/>}</span>
          <span className={styles.choiceTitle}><strong>{source.name}</strong><small>
           {source.kind==="journal"?"期刊":"会议"} · {source.abbreviation||source.domain} · {sourceState(source)}
           {other?" · 当前在 "+other+" 组":""}
          </small></span>
         </button>;
       }):<div className={styles.blankText}>来源总目录中没有匹配结果。可以先在「来源总目录」新增并核验。</div>}
      </div>
      {sources.length>80&&<p className={styles.footnote}>为避免页面过长，每次最多显示 80 条；可输入名称进一步筛选。</p>}
    </div>}
   </div>
 </div>;
}

export default function TaskSourceScopeSettings({canAdmin,canEdit}:{
 canAdmin:boolean;canEdit:boolean;
}){
 const [scopes,setScopes]=useState<Scope[]>([]);
 const [sources,setSources]=useState<Source[]>([]);
 const [scene,setScene]=useState<ScopeScene>("team_weekly");
 const [groups,setGroups]=useState<SourceGroups>(copyGroups(blank));
 const [enforced,setEnforced]=useState(false);
 const [busy,setBusy]=useState(false);
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");

 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{
   const [profiles,catalog]=await Promise.all([
     api<ScopeResult>("task-source-scopes"),
     api<SourceResult>("research-sources"),
   ]);
   setScopes(profiles.items);
   setSources(catalog.items);
  }catch(cause){
   setError(cause instanceof Error?cause.message:"读取任务来源配置失败");
  }finally{setLoading(false);}
 },[]);
 useEffect(()=>{void load();},[load]);
 const current=scopes.find(s=>s.scene===scene);
 useEffect(()=>{
  if(current){
   setGroups(copyGroups(current.groups));
   setEnforced(current.enforced);
   setNotice("");
  }
 },[current?.scene,current?.version,scene,scopes]);
 const available=scene!=="personal_weekly"||current?.available!==false;
 const editable=scene==="personal_weekly"?canEdit&&available:canAdmin;
 const selected=Object.values(groups).flat().length;
 const byId=useMemo(()=>new Map(sources.map(s=>[s.id,s])),[sources]);
 const unresolved=Object.values(groups).flat().filter(id=>{
  const source=byId.get(id);
  return !source?.enabled||source?.resolution_status!=="resolved"||!source?.openalex_source_id;
 }).length;
 const isDirty=Boolean(current&&(JSON.stringify(current.groups)!==JSON.stringify(groups)||enforced!==current.enforced));
 async function save(){
  if(!current||!editable)return;
  setBusy(true);setError("");setNotice("");
  try{
   const updated=await api<Scope>("task-source-scopes/"+scene,{method:"PUT",
    body:JSON.stringify({groups,enforced,expected_version:current.version})
   });
   setScopes(xs=>xs.map(x=>x.scene===scene?updated:x));
   setNotice("该科研场景的专属来源清单已保存，未修改其他场景的配置。");
  }catch(cause){setError(cause instanceof Error?cause.message:"保存失败");}
  finally{setBusy(false);}
 }
 return <div className={styles.root}>
  <div className={styles.heading}>
    <div><div className={styles.kicker}>TASK-SPECIFIC SOURCES</div><h2>任务专属期刊清单</h2>
      <p>共用期刊目录只负责维护来源身份与质量标签；各科研场景独立决定使用哪些期刊和会议。</p>
    </div>
    <button type="button" className={styles.ghostButton} disabled={busy} onClick={()=>void load()}>
      <RefreshCw size={14}/>刷新
    </button>
  </div>
  <div className={styles.scopeCards}>
   {(["team_weekly","personal_weekly","directed_research"] as ScopeScene[]).map(sc=><button key={sc}
      className={styles.scopeCard+(sc===scene?" "+styles.scopeActive:"")}
      onClick={()=>setScene(sc)} type="button">
    <small>{scenes[sc].caption}</small><strong>{scenes[sc].title}</strong>
    <span>{scopes.find(x=>x.scene===sc)?.configured?"已保存独立清单":"使用建议初始清单"}</span>
   </button>)}
  </div>
  {loading?<div className={styles.message}><Loader2 className={styles.spinner} size={16}/>正在读取来源目录与任务配置…</div>:
   error&&scopes.length===0?<div className={styles.message}>
    <AlertCircle size={16}/>任务来源配置接口尚未接入当前 Render 后端；不能在此页面假装已保存。请在服务端部署本分支后使用。
   </div>:
   <div className={styles.editor}>
     <div className={styles.scopeTop}><div><div className={styles.kicker}>{scenes[scene].caption}</div>
      <h3>{scenes[scene].title}</h3><p>{scenes[scene].note}</p>
     </div><span className={styles.version}>{current?.configured?"V"+current.version:"未保存"}</span></div>
     {!available&&<div className={styles.message}><LockKeyhole size={16}/>个人专属来源需要登录独立成员账号；当前模式不支持保存私人配置。</div>}
     <div className={styles.scopeSummary}>
      <span><strong>{selected}</strong> 已选择来源</span><span><strong>{Math.max(0,selected-unresolved)}</strong> 已核验</span>
      <span><strong>{unresolved}</strong> 待处理</span>
     </div>
     <SourceGroupPicker sources={sources} groups={groups} onChange={setGroups} disabled={!editable}/>
     <div className={styles.controlRow}>
      <label className={styles.toggleRow}><input type="checkbox" checked={enforced}
        onChange={e=>setEnforced(e.target.checked)} disabled={!editable}/>
       <span><strong>本场景执行时严格使用此清单</strong>
         <small>开启后不会自动扩大到总目录；未核验来源将使任务失败并明确提示。</small>
       </span></label>
     </div>
     {enforced&&unresolved>0&&<div className={styles.warning}>
       <AlertCircle size={16}/>有 {unresolved} 个来源尚未完成 OpenAlex 核验或已停用。清单可以保存，但实际运行前必须完成核验。
     </div>}
     {!enforced&&<div className={styles.message}><ShieldCheck size={16}/>当前为配置草稿模式；保存不会改变原有检索范围。打开严格模式才会约束后续任务。</div>}
     {error&&<div className={styles.warning}>{error}</div>}
     {notice&&<div className={styles.success}><Check size={15}/>{notice}</div>}
     <div className={styles.saveRow}><span>{!editable?"当前账户没有此场景的修改权限":isDirty?"尚未保存的变更":"各任务的清单相互独立"}</span>
      <button type="button" className={styles.darkButton} onClick={()=>void save()}
        disabled={!editable||busy||!current||!isDirty||(enforced&&selected===0)}>
       {busy?<Loader2 className={styles.spinner} size={14}/>:<Check size={14}/>}保存该场景清单
      </button></div>
   </div>}
  <div className={styles.footerNote}>
   <ShieldCheck size={15}/>团队周报、个人周报和定向任务分别存储；定向任务执行时会冻结来源快照，之后修改默认清单不会改变历史任务。
  </div>
 </div>;
}

export function TaskSourceRunPicker({disabled,onChange}:{
 disabled?:boolean;onChange:(groups:SourceGroups|null)=>void;
}){
 const [open,setOpen]=useState(false);
 const [custom,setCustom]=useState(false);
 const [groups,setGroups]=useState<SourceGroups>(copyGroups(blank));
 const [sources,setSources]=useState<Source[]>([]);
 const [configured,setConfigured]=useState<Scope|null>(null);
 const [error,setError]=useState("");
 useEffect(()=>{
  let live=true;
  Promise.all([api<ScopeResult>("task-source-scopes"),api<SourceResult>("research-sources")])
   .then(([profiles,catalog])=>{
    if(!live)return;
    const scope=profiles.items.find(x=>x.scene==="directed_research");
    setSources(catalog.items);setConfigured(scope||null);
    if(scope)setGroups(copyGroups(scope.groups));
   }).catch(()=>{if(live)setError("当前后端尚不支持单次任务来源配置，暂使用原有任务流程。");});
  return()=>{live=false;};
 },[]);
 function setMode(value:boolean){
  setCustom(value);
  if(value&&configured){const next=copyGroups(configured.groups);setGroups(next);onChange(next);}
  else onChange(null);
 }
 function changeGroups(next:SourceGroups){setGroups(next);if(custom)onChange(next);}
 return <div className={styles.runPicker}>
   <button type="button" className={styles.runPickerHead} onClick={()=>setOpen(!open)}>
     <SlidersHorizontal size={14}/><strong>本次文献来源</strong>
     <span>{custom?"仅本次自定义严格来源":configured?.enforced?"使用定向研究严格清单":"沿用当前默认检索范围"}</span>
     {open?<ChevronDown size={13}/>:<ChevronRight size={13}/>}
   </button>
   {open&&<div className={styles.runPickerBody}>
     {error?<div className={styles.warning}><AlertCircle size={14}/>{error}</div>:<>
      <label className={styles.radioLine}><input type="radio" checked={!custom} onChange={()=>setMode(false)} disabled={disabled}/>
       使用定向任务默认配置 <small>{configured?.enforced?"已开启严格来源约束":"尚未开启严格来源约束"}</small></label>
      <label className={styles.radioLine}><input type="radio" checked={custom} onChange={()=>setMode(true)} disabled={disabled||!configured}/>
       本次临时自定义期刊（严格检索）</label>
      {custom&&<><SourceGroupPicker sources={sources} groups={groups} onChange={changeGroups} disabled={disabled} compact/>
       <p className={styles.footnote}>只应用于本次任务，后台保存独立快照，不会改变 SC01/SC02 或定向任务的默认配置。</p></>}
     </>}
   </div>}
 </div>;
}
