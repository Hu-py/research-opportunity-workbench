"use client";
import {useCallback,useEffect,useMemo,useState} from "react";
import {BookOpen,BrainCircuit,CheckCircle2,ChevronDown,Database,FilePenLine,RefreshCw,ShieldCheck,Sparkles,Target,Workflow,XCircle} from "lucide-react";
import {api} from "@/lib/api";
import type {Profile} from "@/lib/types";

type Insight={
 line_id:string;bottleneck:string;next_experiment:string;
 data_requirements:string[];evidence_status:string
};
type Analysis={
 positioning:string;method_capabilities:string[];line_insights:Insight[];
 cross_line_opportunities:string[];evidence_gaps:string[];scope_cautions:string[]
};
type Draft={
 id:string;source:"llm"|"curated_example";scope:string;status:string;
 base_version:number;revision:number;profile:Profile;analysis:Analysis;
 provenance:string[];note:string;model:string;applied_version:number|null;
 created_at:string
};
type Run={id:string;status:string;error:string;model:string;draft_id:string;
 input_tokens:number;output_tokens:number;created_at:string};
type Studio={
 profile_version:number;drafts:Draft[];runs:Run[];model_configured:boolean;note:string
};

const explainStatus=(s:string)=>s==="described"?"既往讨论":s==="planned"?"计划中":
  s==="verified"?"已核实":s==="inferred"?"推断待核":"待确认";

export default function ResearchProfileStudio({canAdmin,onApplied}:{
 canAdmin:boolean;onApplied:()=>void
}){
 const [data,setData]=useState<Studio|null>(null);
 const [selected,setSelected]=useState("");
 const [notes,setNotes]=useState("");
 const [editing,setEditing]=useState(false);
 const [jsonText,setJsonText]=useState("");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const load=useCallback(async()=>{
   const x=await api<Studio>("profile-intelligence");
   setData(x);
   setSelected(current=>current&&x.drafts.some(d=>d.id===current)?
     current:x.drafts.find(d=>d.status==="draft")?.id||x.drafts[0]?.id||"");
 },[]);
 useEffect(()=>{void load().catch(e=>setError(String(e)));},[load]);
 const draft=useMemo(()=>data?.drafts.find(d=>d.id===selected),[data,selected]);
 useEffect(()=>{
   setJsonText(JSON.stringify(draft?.profile||{},null,2));
   setEditing(false);
 },[draft?.id,draft?.revision]);
 const latest=data?.runs[0];
 const running=data?.runs.some(x=>x.status==="queued"||x.status==="running")||false;
 useEffect(()=>{
   if(!running)return;
   const timer=setInterval(()=>{void load().catch(()=>{});},5000);
   return()=>clearInterval(timer);
 },[load,running]);

 async function generate(){
   setBusy(true);setError("");setNotice("");
   try{
     const result=await api<{id:string}>("profile-intelligence/generate",{
       method:"POST",body:JSON.stringify({notes})});
     setNotes("");
     setNotice("已启动 LLM 科研画像归纳："+result.id.slice(0,8)+
       "。完成后产生新的待审核草稿，不修改正式画像。");
     await load();
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function saveDraft(){
   if(!draft)return;
   setBusy(true);setError("");setNotice("");
   try{
     const profile=JSON.parse(jsonText);
     await api("profile-intelligence/drafts/"+draft.id,{
       method:"PUT",body:JSON.stringify({
         expected_revision:draft.revision,profile
       })});
     setNotice("画像草稿已修订，原版本有审计记录。正式团队画像尚未更改。");
     await load();setEditing(false);
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function apply(){
   if(!draft||!data)return;
   if(!window.confirm("确认将这份草稿应用到共享团队科研画像？所有团队成员会看到更新后的研究主线。请先核对个人/合作课题的归属。"))return;
   setBusy(true);setError("");setNotice("");
   try{
     const result=await api<{profile_version:number}>(
       "profile-intelligence/drafts/"+draft.id+"/apply",{
         method:"POST",body:JSON.stringify({expected_version:data.profile_version})});
     setNotice("已应用为团队画像 V"+result.profile_version+"；论文检索将使用更新后的研究主线。");
     await load();onApplied();
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function discard(){
   if(!draft||!window.confirm("放弃这份画像草稿？正式团队画像不会变化。"))return;
   setBusy(true);setError("");setNotice("");
   try{
     await api("profile-intelligence/drafts/"+draft.id+"/discard",{
       method:"POST",body:"{}"});
     setNotice("草稿已归档，正式画像未更改。");await load();
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }

 return <section className="panel research-profile-studio">
   <div className="panel-header">
     <div><span className="panel-kicker">RESEARCH PROFILE INTELLIGENCE · REUSABLE SKILL</span>
       <h2>结构化科研画像分析原型</h2></div>
     <BrainCircuit size={21}/>
   </div>
   <p className="small muted">
     将科研问题、研究方法、数据条件与技术瓶颈分层梳理。下面的首次示例来自既往讨论，
     仅代表个人与合作研究线索，不自动等同于团队已完成成果。后台可使用可复用
     <code> research_profile </code>Skill 生成新版草稿。
   </p>
   {error&&<div className="alert alert-error">{error}</div>}
   {notice&&<div className="alert alert-success">{notice}</div>}
   <div className="profile-studio-toolbar">
     <label>
       画像草稿版本
       <select value={selected} onChange={e=>setSelected(e.target.value)}>
         {data?.drafts.map(d=><option key={d.id} value={d.id}>{
           d.source==="curated_example"?"首次整理实例":"LLM 生成"
         } · {d.profile.research_lines.length} 条主线 · {
           d.status==="applied"?"已发布 V"+d.applied_version:
           d.status==="discarded"?"已归档":"待审核"} · 修订 {d.revision}</option>)}
       </select>
     </label>
     <button className="btn btn-secondary" onClick={()=>void load()} disabled={busy}>
       <RefreshCw size={14}/> 刷新
     </button>
   </div>
   {draft?<>
     <div className="profile-studio-tags">
       <span><ShieldCheck size={14}/> {draft.source==="llm"?"LLM 归纳草稿":"基于既往资料手工整理"}</span>
       <span><Database size={14}/> {draft.scope==="team"?"候选团队画像":"个人／合作研究画像"}</span>
       <span><Workflow size={14}/> 当前正式画像 V{data?.profile_version??0} · 草稿基于 V{draft.base_version}</span>
     </div>
     {draft.note&&<p className="small muted">{draft.note}</p>}
     <div className="profile-studio-positioning"><Target size={19}/><div>
       <strong>研究定位 · Positioning</strong>
       <p>{draft.analysis.positioning}</p>
     </div></div>
     <h3 className="profile-studio-subtitle">研究主线 × 技术瓶颈 × 下一步实验</h3>
     <div className="profile-studio-lines">
       {draft.profile.research_lines.map((line,i)=>{
         const insight=draft.analysis.line_insights?.find(x=>x.line_id===line.id);
         return <article className="profile-studio-line" key={line.id}>
           <div className="profile-studio-line-top">
             <span className="profile-studio-number">{String(i+1).padStart(2,"0")}</span>
             <div><h4>{line.name}</h4><p>{line.problem}</p></div>
             {insight&&<span className="profile-studio-evidence">{explainStatus(insight.evidence_status)}</span>}
           </div>
           <div className="profile-studio-line-details">
             <p><b>技术瓶颈：</b>{insight?.bottleneck||"需要确认"}</p>
             <p><b>最小实验：</b>{insight?.next_experiment||"待定义"}</p>
             <p><b>数据条件：</b>{insight?.data_requirements?.join("；")||"待核查"}</p>
             <p><b>方法检索：</b>{line.method_queries.join(" · ")}</p>
           </div>
         </article>;
       })}
     </div>
     <div className="profile-studio-analysis">
       <div><h3><BookOpen size={15}/> 方法能力</h3>
         <p>{draft.analysis.method_capabilities?.join(" · ")||"未归纳"}</p></div>
       <div><h3><Sparkles size={15}/> 跨主线研究机会（待验证）</h3>
         {(draft.analysis.cross_line_opportunities||[]).map((x,i)=><p key={i}>· {x}</p>)}</div>
       <div><h3><ShieldCheck size={15}/> 关键缺口与证据边界</h3>
         {(draft.analysis.evidence_gaps||[]).map((x,i)=><p key={i}>· {x}</p>)}
         {(draft.analysis.scope_cautions||[]).map((x,i)=><p key={"scope"+i}>· {x}</p>)}</div>
     </div>
     {!!draft.provenance?.length&&<details className="profile-studio-source">
       <summary>查看本版画像的依据与限制 <ChevronDown size={15}/></summary>
       {draft.provenance.map((x,i)=><p key={i}>{x}</p>)}
     </details>}
     {canAdmin&&draft.status==="draft"&&<div className="profile-studio-edit-area">
       <div className="inline-actions">
         <button className="btn btn-secondary" disabled={busy} onClick={()=>setEditing(v=>!v)}>
           <FilePenLine size={15}/> {editing?"关闭 JSON 编辑器":"编辑这份画像草稿"}
         </button>
         <button className="btn btn-primary" disabled={busy} onClick={()=>void apply()}>
           <CheckCircle2 size={15}/> 确认并应用到团队画像
         </button>
         <button className="btn btn-secondary" disabled={busy} onClick={()=>void discard()}>
           <XCircle size={15}/> 暂不采用
         </button>
       </div>
       {editing&&<div className="profile-studio-json">
         <p className="small muted">此处修改研究主线、检索词、方法、目标等兼容字段。保存仅修改草稿，不会直接覆盖团队画像。</p>
         <textarea spellCheck={false} value={jsonText} onChange={e=>setJsonText(e.target.value)} rows={20}/>
         <button className="btn btn-primary" disabled={busy} onClick={()=>void saveDraft()}>
           保存草稿修订
         </button>
       </div>}
     </div>}
   </>:<div className="small-note">尚未导入初始科研画像实例；可从下方进行 LLM 归纳。</div>}
   <div className="profile-studio-generate">
     <div><strong>让 LLM 重新归纳科研画像</strong>
       <p className="small muted">使用现有正式画像、上述示例、已核验团队成果题名及非受限 CUSP 数据属性，
       生成新的分层画像草稿，保留证据边界，绝不自动发布。</p></div>
     <textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={3} maxLength={2000}
       placeholder="可补充更新：例如某条主线已经结题、一个课题属于合作研究、想优先关注的技术等…"/>
     <div className="inline-actions">
       <button className="btn btn-primary" disabled={busy||running||!canAdmin||!data?.model_configured}
         onClick={()=>void generate()}><Sparkles size={15}/> LLM 重新生成画像草稿</button>
       {!data?.model_configured&&<span className="small muted">
         先到「AI 选题实验台」填写 DeepSeek Key；首次静态原型无需 Key。
       </span>}
     </div>
     {latest&&<div className="profile-studio-run">
       <strong>最近一次生成：{latest.status==="completed"?"已完成":
         latest.status==="failed"?"失败":latest.status==="running"?"正在生成":"等待处理"}</strong>
       <span>模型 {latest.model} · 输入 {latest.input_tokens} / 输出 {latest.output_tokens} Tokens</span>
       {latest.error&&<p className="alert alert-error">{latest.error}</p>}
     </div>}
   </div>
 </section>;
}
