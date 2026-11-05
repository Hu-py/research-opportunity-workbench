"use client";

import {useCallback,useEffect,useState} from "react";
import {BrainCircuit,ExternalLink,Play,RefreshCw,RotateCcw,ShieldCheck,Wrench} from "lucide-react";
import {api} from "@/lib/api";

type Tool={name:string;purpose:string;provider:string};
type Summary={
 id:string;line_id:string;question:string;status:string;steps:number;
 model_calls:number;tool_calls:number;input_tokens:number;output_tokens:number;
 error:string;novelty_verified:boolean;human_review_required:boolean
};
type Evidence={
 id:string;paper_id:string;title:string;doi:string;url:string;source_tool:string;
 provider:string;evidence_level:string
};
type Hypothesis={
 research_question?:string;mechanism?:string;falsifiable_prediction?:string;
 methods?:string;baselines?:string[];minimal_experiment?:string;
 supporting_evidence_ids?:string[];counter_evidence_ids?:string[];
 limitations?:string[];next_searches?:string[];novelty_status?:string
};
type Detail=Summary&{
 evidence:Evidence[];
 hypothesis:Hypothesis;
 trace:{step:number;action:string;tool?:string;reason?:string;
         status?:string;evidence_ids?:string[];cited_evidence_ids?:string[]}[]
};
type Line={line_id:string;line_name:string};

const labels:Record<string,string>={
 queued:"排队中",running:"探索中",completed:"生成待审研究假设",
 failed:"执行失败",incomplete:"探索轮次已耗尽",insufficient_evidence:"证据不足"
};

export default function ScientificExplorationPanel({
 selectedLine,lines,canEdit,modelConfigured
}:{
 selectedLine:string;lines:Line[];canEdit:boolean;modelConfigured:boolean
}){
 const [lineId,setLineId]=useState("");
 const [question,setQuestion]=useState("");
 const [tools,setTools]=useState<Tool[]>([]);
 const [runs,setRuns]=useState<Summary[]>([]);
 const [detail,setDetail]=useState<Detail|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 useEffect(()=>{if(!lineId&&selectedLine)setLineId(selectedLine);},[selectedLine,lineId]);
 const refresh=useCallback(async()=>{
   const [catalog,history]=await Promise.all([
     api<{items:Tool[]}>("scientific-tools"),
     api<{items:Summary[]}>("scientific-explorations")
   ]);
   setTools(catalog.items);setRuns(history.items);
   if(history.items.length){
     const active=history.items[0];
     const result=await api<Detail>("scientific-explorations/"+active.id);
     setDetail(result);
   }else setDetail(null);
 },[]);
 useEffect(()=>{void refresh().catch(e=>setError(String(e)));},[refresh]);
 const active=runs.some(x=>x.status==="queued"||x.status==="running");
 useEffect(()=>{
   if(!active)return;
   const timer=setInterval(()=>{void refresh().catch(()=>{});},6000);
   return()=>clearInterval(timer);
 },[active,refresh]);

 async function start(){
   if(!lineId||question.trim().length<10)return;
   setBusy(true);setError("");setNotice("");
   try{
     await api("scientific-explorations",{method:"POST",
       body:JSON.stringify({line_id:lineId,question:question.trim()})});
     setNotice("已建立人工触发的科研证据探索任务，模型与学术 API 用量受限制。");
     await refresh();
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function resume(id:string){
   setBusy(true);setError("");setNotice("");
   try{
     await api("scientific-explorations/"+id+"/resume",{method:"POST",body:"{}"});
     await refresh();setNotice("已提交恢复任务，将沿用之前保存的证据。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function show(id:string){
   setError("");
   try{setDetail(await api<Detail>("scientific-explorations/"+id));}
   catch(e){setError(e instanceof Error?e.message:String(e));}
 }
 return <section className="panel" aria-label="科研证据探索智能体">
   <div className="panel-header"><div>
     <span className="panel-kicker">SCIENTIFIC AGENT · EVIDENCE EXPLORATION</span>
     <h2>科研工具智能体 · 实验版</h2>
   </div><BrainCircuit size={20}/></div>
   <p className="small muted">独立于旧的 Planner → Reader → Generator → Critic 流程。Agent 根据研究问题自行选择已授权学术工具，探索相似研究及证据矛盾，输出带证据编号的可证伪研究假设。不运行代码、不自动批准选题。</p>
   <div className="ai-lab-controls">
     <label>研究主线
       <select value={lineId} onChange={e=>setLineId(e.target.value)}>
         <option value="">选择研究主线</option>
         {lines.map(line=><option key={line.line_id} value={line.line_id}>{line.line_name}</option>)}
       </select>
     </label>
     <label style={{flex:"2 1 320px"}}>需要探索的科研问题
       <input value={question} maxLength={600} onChange={e=>setQuestion(e.target.value)}
         placeholder="例如：哪些空间泛化假设在真实城市间会失效？"/>
     </label>
     <button className="btn btn-primary" disabled={busy||active||!canEdit||!modelConfigured||
       !lineId||question.trim().length<10} onClick={()=>void start()}>
       <Play size={15}/> 开始证据探索
     </button>
     <button className="btn btn-secondary" disabled={busy} onClick={()=>void refresh()}>
       <RefreshCw size={15}/> 刷新
     </button>
   </div>
   {!modelConfigured&&<div className="small-note">需先由管理员配置 DeepSeek Key。该实验仅允许登录团队的研究人员手动运行。</div>}
   {error&&<div className="alert alert-error">{error}</div>}
   {notice&&<div className="alert alert-success">{notice}</div>}
   <div className="small-note"><Wrench size={15}/> 已注册 {tools.length} 项工具：
     {tools.map(t=>t.name).join(" · ")||"正在加载"}。每轮最多 5 次模型决策、3 次学术工具调用；API 账本限制每日额度。
   </div>
   {runs.length>0&&<div className="inline-actions" style={{flexWrap:"wrap"}}>
     {runs.slice(0,8).map(r=><button key={r.id}
        className="btn btn-secondary" type="button" onClick={()=>void show(r.id)}>
        {labels[r.status]||r.status} · {r.id.slice(0,8)}
     </button>)}
   </div>}
   {detail&&<div className="ai-lab-run-box">
     <div className="ai-lab-run-head"><strong>{detail.question}</strong>
       <span>{labels[detail.status]||detail.status}</span></div>
     <p className="small muted">模型决策 {detail.model_calls} 次 · 工具调用 {detail.tool_calls} 次 ·
       输入 {detail.input_tokens} / 输出 {detail.output_tokens} tokens</p>
     {detail.trace.length>0&&<div className="ai-lab-card-list">
       {detail.trace.map((event,i)=><div className="small-note" key={i}>
         <strong>步骤 {event.step}：</strong>
         {event.action==="call_tool"
            ?<>{event.tool} · {event.status} · {event.reason||"查询证据"}
              {event.evidence_ids?.length?" · 证据 "+event.evidence_ids.join(", "):""}</>
            :"形成科研假设 · 引用证据 "+(event.cited_evidence_ids||[]).join(", ")}
       </div>)}
     </div>}
     {detail.error&&<div className="alert alert-error">{detail.error}</div>}
     {detail.status==="failed"&&canEdit&&
       <button className="btn btn-secondary" disabled={busy} onClick={()=>void resume(detail.id)}>
         <RotateCcw size={14}/> 从已保存证据恢复
       </button>}
     {detail.hypothesis?.research_question&&<article className="ai-lab-card">
       <h3>{detail.hypothesis.research_question}</h3>
       <p><b>假设机制：</b>{detail.hypothesis.mechanism}</p>
       <p><b>可证伪预测：</b>{detail.hypothesis.falsifiable_prediction}</p>
       <p><b>验证方法：</b>{detail.hypothesis.methods}</p>
       <p><b>对照基线：</b>{detail.hypothesis.baselines?.join("、")}</p>
       <p><b>最小实验：</b>{detail.hypothesis.minimal_experiment}</p>
       <p><b>未解决风险：</b>{detail.hypothesis.limitations?.join("；")||"待人工审查"}</p>
       <div className="small-note"><ShieldCheck size={15}/>
         创新性未核验、数据访问未核验，所有结果需科研人员复查。
       </div>
     </article>}
     {detail.evidence.length>0&&<div className="ai-lab-paper-list">
       <strong>检索证据（目前仅有学术元数据，尚非全文证据）</strong>
       {detail.evidence.map(e=><div key={e.id}>
         <b>{e.id} · </b>
         {/^https:\/\//.test(e.url)?
           <a href={e.url} target="_blank" rel="noopener noreferrer">{e.title||e.doi} <ExternalLink size={12}/></a>:
           <span>{e.title||e.doi}</span>}
         <span className="small muted"> · {e.provider}</span>
       </div>)}
     </div>}
   </div>}
 </section>;
}
