"use client";

import {ChangeEvent, useCallback, useEffect, useMemo, useState} from "react";
import {
 Activity, ArrowRight, BookOpen, BrainCircuit, CheckCircle2, ChevronLeft, ChevronRight,
 Clock3, Database, FileJson, GitBranch, Layers3, Pause, Play, RefreshCw,
 ShieldAlert, ShieldCheck, Sparkles, Trophy, Upload, Workflow
} from "lucide-react";

type Candidate={
 id:string; title:string; question?:string; mechanism?:string; method?:string;
 falsifiable_prediction?:string; minimal_experiment?:string; limitations?:string[];
 baselines?:string[]; paper_ids?:string[]; dataset_ids?:string[];
 origin?:string; generation?:number; parent_ids?:string[]; elo?:number; status?:string
};
type EventRow={stage:string;generation?:number;retrieved?:number;retained?:number;
 disagreements?:number;created?:string[];children?:{id:string;parent_ids:string[]}[];
 matches?:number;leader?:string;leader_rating?:number;
 decision?:string;reason?:string;winner?:string;pilot_executed?:boolean;
 data_feasible_assessment?:boolean;archived_generation?:number;strategy?:string};
type Opinion={winner_id:string;reason?:string;caveat?:string};
type Match={left_id:string;right_id:string;first:Opinion;reversed:Opinion;
 score_left?:number;delta_left?:number;position_disagreement?:boolean};
type Juror={juror:string;votes:Record<string,boolean>;reasons?:Record<string,string>};
type Result={
 winner_id?:string;winner_title?:string;generation_count?:number;
 event_log?:EventRow[];lineage?:{id:string;parent_ids?:string[];generation?:number;origin?:string;status?:string}[];
 ranked_candidates?:Candidate[];archived_candidates?:Candidate[];matches?:Match[];
 supervisor_decisions?:{action:string;reason:string;expected_gain?:string;hard_guard?:boolean}[];
 screening?:{screened_count?:number;retained_count?:number;disagreements?:number;
 jurors?:Juror[];adjudicated_ids?:string[];adjudication_reasons?:Record<string,string>;
 unresolved_disagreements?:string[];retained_paper_ids?:string[]};
 verification?:{hypothesis_test?:string;primary_metric?:string;
 failure_criteria?:string;split_strategy?:string;ablations?:string[];baselines?:string[];
 evidence_limitations?:string[];data_feasible_assessment?:boolean;
 novelty_verified?:boolean;experimental_claim_verified?:boolean};
 pilot?:{status?:string;n_generated_experiments?:number;warning?:string};
 paper_ids?:string[];provider_calls?:number;cache_hits?:number;
 comparison_context?:{dataset_ids?:string[];model_name?:string}
};
type Run={id:string;line_id:string;status:string;strategy?:string;created_at?:string;
 model_calls?:number;provider_calls?:number;cache_hits?:number;
 winner_title?:string;generation_count?:number;match_count?:number;results?:Result};
type RunsPayload={configured:boolean;items:Run[];detail?:string};
type LiveEvent={run_id:string;step_index:number;stage:string;
 recorded_at:string;details:{generation?:number;retrieved?:number;retained?:number;
 matches?:number;decision?:string;children_count?:number;created_count?:number;
 disagreements?:number;leader?:string;winner?:string}};
type LivePayload={configured:boolean;enabled:boolean;items:LiveEvent[];detail?:string};


const names:Record<string,string>={
 run_started:"实验开始",run_completed:"已完成并保存",run_failed:"运行失败",
 knowledge_discovery:"论文检索",independent_paper_screen:"双 Agent 文献审核",
 generate:"三视角生成",elo_tournament:"双向辩论赛",supervisor:"总控调度",
 hypothesis_evolution:"批评与进化",hypothesis_expansion:"边界扩展",
 rollback:"版本回退",scientific_gate:"科学质量门控"
};
const summary:Record<string,string>={
 knowledge_discovery:"发现相关论文，形成待审核候选池。",
 independent_paper_screen:"两位独立 Agent 对论文逐一投票，意见不同时增加仲裁。",
 generate:"从科研问题、研究方法和现有数据三个视角提出假设。",
 elo_tournament:"每对候选在两种位置顺序下各评一次，记录分歧和相对 Elo。",
 supervisor:"根据预算和研究判断，决定是否修改、扩展、回退或验证。",
 hypothesis_evolution:"独立 Critic 先提出反驳，再产生改进版本，保留父代。",
 hypothesis_expansion:"探索不同于已有候选的新方向。",
 rollback:"封存质量不足的新版本，仍保留历史记录。",
 scientific_gate:"核对基线、可证伪性、实验设计、数据可用性与证据局限。"
};
const displayStatus:Record<string,string>={
 candidate_for_human_review:"待人工评审",needs_more_evidence:"证据不足",
 running:"执行中",failed:"运行失败"
};
const originNames:Record<string,string>={
 problem:"问题视角",method:"方法视角",data:"数据视角",
 refine:"批评改写",fuse:"跨视角融合",boundary:"边界探索"
};

function asObject(x:unknown):Record<string,unknown>{
 return x!==null&&typeof x==="object"&&!Array.isArray(x)?x as Record<string,unknown>:{};
}
function fmtDate(value?:string){
 if(!value)return "时间未知";
 const d=new Date(value);
 return Number.isNaN(d.getTime())?value:d.toLocaleString("zh-CN",{hour12:false});
}
function short(value:string,limit=110){return value.length>limit?value.slice(0,limit)+"…":value;}
function fullCandidateCount(result:Result){return (result.ranked_candidates?.length||0)+(result.archived_candidates?.length||0);}
function synthesizeImport(raw:unknown):Run {
 const obj=asObject(Array.isArray(raw)?raw[0]:raw);
 if(Object.keys(obj).length===0)throw Error("无法识别文件：没有有效的 JSON 对象");
 const row=asObject(obj.results);
 const body=Object.keys(row).length?row:obj;
 const events=(body.event_log||body.execution_chain) as unknown;
 if(!Array.isArray(events))throw Error("缺少 event_log / execution_chain，无法重建过程");
 const results:Result={
  ...body, event_log:events,
  ranked_candidates:(body.ranked_candidates||body.hypotheses||[]) as Candidate[],
  matches:(body.matches||body.agent_debates||[]) as Match[],
  supervisor_decisions:(body.supervisor_decisions||body.decisions||[]) as Result["supervisor_decisions"],
  screening:(body.screening||body.literature_review||{}) as Result["screening"],
  verification:(body.verification||body.scientific_validation||{}) as Result["verification"]
 };
 const candidates=[...(results.ranked_candidates||[]),...(results.archived_candidates||[])];
 const lineage=Array.isArray(body.lineage)?body.lineage as Result["lineage"]:
 candidates.map(c=>({id:c.id,parent_ids:c.parent_ids||[],generation:c.generation||0,
 origin:c.origin||"",status:c.status||"candidate"}));
 results.lineage=lineage;
 results.winner_id=String(body.winner_id||results.ranked_candidates?.[0]?.id||"");
 return {
  id:String(obj.id||"local-file"),line_id:String(obj.line_id||"local-replay"),
  status:String(obj.status||"needs_more_evidence"),created_at:String(obj.created_at||""),
  model_calls:Number(obj.model_calls||0),results
 };
}

function stages(event:EventRow,i:number){
 return (i+1).toString().padStart(2,"0")+" · "+(names[event.stage]||event.stage);
}
function winnerText(value:string){return value==="tie"?"平局":value||"未确定";}
function fact(status:boolean|null|undefined){
 return status===true?"已确认":status===false?"尚未确认":"暂无记录";
}

export default function AgentGameReplay(){
 const [runs,setRuns]=useState<Run[]>([]);
 const [active,setActive]=useState<Run|null>(null);
 const [chosenId,setChosenId]=useState("");
 const [step,setStep]=useState(0);
 const [playing,setPlaying]=useState(false);
 const [speed,setSpeed]=useState(1800);
 const [candidateId,setCandidateId]=useState("");
 const [matchIndex,setMatchIndex]=useState(0);
 const [mode,setMode]=useState<"ranking"|"lineage"|"papers">("ranking");
 const [loading,setLoading]=useState(false);
 const [error,setError]=useState("");
 const [note,setNote]=useState("");
 const [configured,setConfigured]=useState<boolean|null>(null);
 const [liveEvents,setLiveEvents]=useState<LiveEvent[]>([]);
 const [liveMessage,setLiveMessage]=useState("");
 const [liveEnabled,setLiveEnabled]=useState(false);

 const loadRuns=useCallback(async()=>{
  try{
   const response=await fetch("/api/research-lab/runs",{cache:"no-store"});
   const data=await response.json() as RunsPayload;
   if(!response.ok)throw new Error(data.detail||"实验列表读取失败");
   setConfigured(data.configured);setRuns(data.items||[]);
   setNote(data.detail||"");
   if(!chosenId&&data.items?.length)setChosenId(data.items[0].id);
  }catch(e){
   setConfigured(false);
   setNote(e instanceof Error?e.message:"无法连接实验数据库");
  }
 },[chosenId]);

 useEffect(()=>{void loadRuns();},[loadRuns]);
 useEffect(()=>{
  let canceled=false;
  async function pollLive(){
   try{
    const response=await fetch("/api/research-lab/live",{cache:"no-store"});
    const data=await response.json() as LivePayload;
    if(!response.ok)throw Error(data.detail||"实时事件读取失败");
    if(canceled)return;
    setLiveEnabled(data.enabled);setLiveMessage(data.detail||"");
    setLiveEvents(data.items||[]);
   }catch{
    if(!canceled)setLiveMessage("实时事件暂不可用，历史回放仍可使用。");
   }
  }
  void pollLive();
  const timer=window.setInterval(()=>{void pollLive();},6000);
  return()=>{canceled=true;window.clearInterval(timer);};
 },[]);

 useEffect(()=>{
  if(!chosenId||chosenId==="local-file")return;
  let cancelled=false;
  setLoading(true);setError("");
  void fetch("/api/research-lab/runs/"+encodeURIComponent(chosenId),{cache:"no-store"})
   .then(async r=>{const d=await r.json();if(!r.ok)throw Error(d.detail||"读取失败");return d as Run;})
   .then(d=>{
     if(cancelled)return;
     setActive(d);setStep(0);setCandidateId("");setMatchIndex(0);setPlaying(false);
   })
   .catch(e=>{if(!cancelled)setError(e instanceof Error?e.message:"实验读取失败");})
   .finally(()=>{if(!cancelled)setLoading(false);});
  return()=>{cancelled=true;};
 },[chosenId]);

 const liveGroups=useMemo(()=>{
  const map=new Map<string,LiveEvent[]>();
  for(const event of liveEvents){
   if(!map.has(event.run_id))map.set(event.run_id,[]);
   map.get(event.run_id)?.push(event);
  }
  return [...map.entries()].map(([id,items])=>{
    const sorted=items.sort((a,b)=>a.step_index-b.step_index);
    const last=sorted[sorted.length-1];
    const stopped=last.stage==="run_completed"||last.stage==="run_failed";
    const age=Date.now()-new Date(last.recorded_at).getTime();
    return {id,events:sorted,last,stopped,recent:Number.isFinite(age)&&age<60*60*1000};
  }).filter(g=>g.recent).sort((a,b)=>b.last.recorded_at.localeCompare(a.last.recorded_at)).slice(0,4);
 },[liveEvents]);
 const result=active?.results||{};
 const events=useMemo(()=>result.event_log||[],[result.event_log]);
 const candidates=useMemo(()=>[...(result.ranked_candidates||[]),...(result.archived_candidates||[])],
  [result.ranked_candidates,result.archived_candidates]);
 const byId=useMemo(()=>new Map(candidates.map(c=>[c.id,c])),[candidates]);
 const current=events[Math.min(step,Math.max(0,events.length-1))];
 const visible=events.slice(0,step+1);
 const visibleMatches=useMemo(()=>{
   const n=visible.reduce((total,e)=>total+(e.stage==="elo_tournament"?(e.matches||0):0),0);
   return (result.matches||[]).slice(0,n);
 },[visible,result.matches]);
 const tournamentMatches=useMemo(()=>{
   if(current?.stage!=="elo_tournament")return [];
   const n=visibleMatches.length, count=current.matches||0;
   return visibleMatches.slice(Math.max(0,n-count),n);
 },[current,visibleMatches]);

 const discoveredIds=useMemo(()=>{
   const ids=new Set<string>();
   visible.forEach(e=>{
     if(e.stage==="generate")(e.created||[]).forEach(id=>ids.add(id));
     if(e.stage==="hypothesis_evolution")(e.children||[]).forEach(c=>ids.add(c.id));
     if(e.stage==="hypothesis_expansion"&&typeof (e as EventRow&{created?:string}).created==="string")
       ids.add((e as EventRow&{created:string}).created);
   });
   return ids;
 },[visible]);
 const shownCandidates=candidates.filter(c=>!events.length||discoveredIds.has(c.id));
 const eloMap=useMemo(()=>{
   const ratings=new Map<string,number>();
   for(const c of shownCandidates)ratings.set(c.id,1200);
   for(const m of visibleMatches){
      if(typeof m.delta_left!=="number")continue;
      ratings.set(m.left_id,Number(((ratings.get(m.left_id)||1200)+m.delta_left).toFixed(2)));
      ratings.set(m.right_id,Number(((ratings.get(m.right_id)||1200)-m.delta_left).toFixed(2)));
   }
   return ratings;
 },[shownCandidates,visibleMatches]);
 const ranking=shownCandidates.slice().sort((a,b)=>(eloMap.get(b.id)||1200)-(eloMap.get(a.id)||1200)||a.id.localeCompare(b.id));
 const selected=byId.get(candidateId)||ranking[0]||null;
 const scopeLineage=result.lineage||candidates.map(c=>({id:c.id,parent_ids:c.parent_ids||[],
   generation:c.generation||0,origin:c.origin||"",status:c.status||"candidate"}));
 const lineage=scopeLineage.filter(c=>discoveredIds.has(c.id)||!events.length);
 const groups=Array.from(new Set(lineage.map(c=>c.generation||0))).sort((a,b)=>a-b);
 const winnersInView=visibleMatches.filter(m=>m.position_disagreement).length;

 useEffect(()=>{
  if(!playing||events.length<2)return;
  const timer=window.setInterval(()=>setStep(s=>{
    if(s>=events.length-1){setPlaying(false);return s;}
    return s+1;
  }),speed);
  return()=>window.clearInterval(timer);
 },[playing,events.length,speed]);

 async function upload(event:ChangeEvent<HTMLInputElement>){
  const file=event.target.files?.[0];
  if(!file)return;
  setError("");setPlaying(false);
  try{
   if(file.size>3_000_000)throw Error("本地文件超过 3 MB；请选择一次运行的 JSON 结果");
   const text=await file.text();
   const record=synthesizeImport(JSON.parse(text));
   setChosenId("local-file");setActive(record);setStep(0);
   setCandidateId("");setMatchIndex(0);
   setNote("本地回放模式：文件仅在浏览器中读取，不发送到服务器。");
  }catch(e){setError(e instanceof Error?e.message:"文件无法解析");}
  event.target.value="";
 }

 const screening=result.screening||{};
 const gate=result.verification||{};
 const explanation=current?summary[current.stage]||"从记录中读取该阶段的实际决策。":"选择一次实验开始回放。";
 const showing=Math.max(0,Math.min(step+1,events.length));
 return <div className="game-lab">
  <div className="game-hero">
   <div className="game-hero-content">
    <div className="game-eyebrow"><span className="game-pulse"/> CO-SCIENTIST STUDIO / PROCESS REPLAY</div>
    <h1>多智能体科研博弈<span>可视化实验室</span></h1>
    <p>把文献筛选、生成、辩论、迭代和科学审查还原为可播放的研究过程。点击任一节点，查看实际 Agent 判断依据。</p>
    <div className="game-hero-pills">
     <span><Workflow size={14}/> 阶段回放</span>
     <span><GitBranch size={14}/> 假设谱系</span>
     <span><ShieldCheck size={14}/> 证据审计</span>
    </div>
   </div>
   <div className="game-hero-orbit" aria-hidden="true"><span>H001</span><span>H002</span><span>H003</span><div>AI</div></div>
  </div>

  <section className="game-panel game-live" aria-label="正在执行的多智能体实验">
   <div className="game-live-top">
    <div><span className="game-label">LIVE AGENT EXECUTION · 真实事件流</span>
     <h2><Activity size={19}/> 实时运行监控</h2>
     <p>系统每 6 秒读取最新记录；只有 Agent 完成一个 LangGraph 节点后，这里才更新。</p>
    </div><span className={"game-live-state "+(liveGroups.some(g=>!g.stopped)?"game-live-active":"")}>
     <span/> {liveGroups.some(g=>!g.stopped)?"有实验正在运行":liveEnabled?"实时监听已连接":"待完成连接"}
    </span>
   </div>
   {liveGroups.length?liveGroups.map(group=>
    <div className="game-live-run" key={group.id}>
     <div className="game-live-run-head"><div>
      <strong>{group.stopped?
       group.last.stage==="run_completed"?"实验已完成":"实验执行失败":"运行中"} · {group.id.slice(0,8)}</strong>
      <span>最近事件：{fmtDate(group.last.recorded_at)} · 已记录 {group.events.length} 步</span>
     </div>
      {group.last.stage==="run_completed"&&
       <button type="button" onClick={()=>{setChosenId(group.id);void loadRuns();}}>
        查看完整回放 <ArrowRight size={14}/>
       </button>}
     </div>
     <div className="game-live-events">
      {group.events.map(item=><div className="game-live-event" key={item.step_index}>
       <span className="game-live-marker">{item.step_index}</span>
       <div><strong>{names[item.stage]||item.stage}</strong>
        <small>{fmtDate(item.recorded_at)} · {[
         typeof item.details.generation==="number"?"G"+item.details.generation:"",
         typeof item.details.matches==="number"?item.details.matches+" 场比赛":"",
         item.details.decision?"决策 "+item.details.decision:"",
         typeof item.details.retained==="number"?"保留 "+item.details.retained+" 篇":"",
         item.details.leader?"领先 "+item.details.leader:""
        ].filter(Boolean).join(" · ")||"节点已完成"}</small>
       </div>
      </div>)}
     </div>
    </div>
   ):<p className="game-muted">
      {liveMessage||"目前没有最近一小时的新实验事件。开启 SQL 007 和工作流 stream_live_events 后，新实验会自动显示在这里。"}
     </p>}
  </section>

  <section className="game-panel game-source">
   <div className="game-source-bar">
    <div>
     <span className="game-label">实验记录 / EXPERIMENT RECORD</span>
     <div className="game-source-control">
      <select aria-label="选择实验记录" value={chosenId} onChange={e=>setChosenId(e.target.value)}>
       <option value="">{configured===false?"尚未连接云端数据":"请选择实验"}</option>
       {chosenId==="local-file"&&<option value="local-file">本地导入的实验</option>}
       {runs.map(run=><option key={run.id} value={run.id}>{fmtDate(run.created_at)} · {run.line_id} · {run.id.slice(0,8)}</option>)}
      </select>
      <button type="button" onClick={()=>void loadRuns()} title="刷新实验列表"><RefreshCw size={16}/></button>
     </div>
    </div>
    <label className="game-upload"><Upload size={16}/> 导入本地结果
     <input type="file" accept=".json,.txt,application/json,text/plain" onChange={e=>void upload(e)}/>
    </label>
   </div>
   {note&&<div className="game-notice"><ShieldAlert size={15}/>{note}</div>}
   {error&&<div className="game-error">{error}</div>}
   {loading&&<p className="game-muted">正在读取研究过程…</p>}
  </section>

  {!active? <section className="game-empty">
    <BrainCircuit size={36}/>
    <h2>选择一次实验，就能看到 Agent 如何辩论</h2>
    <p>{configured===false?
      "云端实验尚未连接。也可以直接导入之前从 Supabase 导出的单次实验 JSON 文件，本地即时回放。":
      "尚无实验记录。可以先运行 Research Agent Lab，或者导入以前保存的 JSON 结果。"}</p>
    <p className="game-muted">历史记录的播放是按事件逻辑顺序逐步展开，并非原运行耗时的真实录屏。</p>
  </section> : <>
   <div className="game-stat-grid">
    <div className="game-stat"><BookOpen size={18}/><span>论文审核</span><strong>{screening.retained_count||0}<small> / {screening.screened_count||0}</small></strong><em>保留 / 检索</em></div>
    <div className="game-stat"><Layers3 size={18}/><span>选题版本</span><strong>{scopeLineage.length||fullCandidateCount(result)}</strong><em>含迭代版本</em></div>
    <div className="game-stat"><Trophy size={18}/><span>成对评审</span><strong>{(result.matches||[]).length}</strong><em>双向判断</em></div>
    <div className="game-stat"><GitBranch size={18}/><span>进化代数</span><strong>{result.generation_count||0}</strong><em>0 表示只生成初代</em></div>
    <div className="game-stat"><Activity size={18}/><span>模型调用</span><strong>{active.provider_calls??result.provider_calls??active.model_calls??0}</strong><em>实际 Provider 次数（如有）</em></div>
   </div>

   <div className="game-run-caption">
    <div><strong>{active.line_id.replaceAll("_"," · ")}</strong>
     <span>{fmtDate(active.created_at)} · {active.id==="local-file"?"本地实验":active.id}</span></div>
    <div className={"game-state "+(active.status==="candidate_for_human_review"?"game-state-good":"")}>
      {displayStatus[active.status]||active.status}
    </div>
   </div>

   <section className="game-panel game-timeline">
    <div className="game-panel-head">
     <div><span className="game-label">EXECUTION TIMELINE</span><h2>研究过程回放</h2>
      <p>按实际记录顺序播放每一阶段。事件没有精确时间戳时，只标注执行顺序。</p></div>
     <span className="game-count">步骤 {showing} / {events.length}</span>
    </div>
    <div className="game-steps" role="group" aria-label="选择回放节点">
     {events.map((e,i)=><button key={i} type="button"
       className={"game-step "+(i===step?"game-step-current ":"")+(i<step?"game-step-past":"")}
       onClick={()=>{setStep(i);setPlaying(false);setMatchIndex(0);}}>
       <span className="game-step-dot">{i<step?<CheckCircle2 size={13}/>:i+1}</span>
       <span className="game-step-name">{names[e.stage]||e.stage}</span>
       <small>{e.stage==="elo_tournament"?"第 "+((e.generation||0)+1)+" 轮":
         e.stage==="hypothesis_evolution"?"第 "+((e.children?.length||0))+" 个子版本":
         e.stage==="supervisor"?(e.decision||"调度"):String(i+1).padStart(2,"0")}</small>
      </button>)}
    </div>
    {events.length>0&&<div className="game-player">
     <button type="button" aria-label="上一步" disabled={step<=0} onClick={()=>{setPlaying(false);setStep(x=>Math.max(0,x-1));}}><ChevronLeft size={18}/></button>
     <button type="button" className="game-play" onClick={()=>{
       if(step>=events.length-1){setStep(0);setPlaying(true);}else setPlaying(x=>!x);
     }}>{playing?<Pause size={16}/>:<Play size={16}/>} {playing?"暂停":"播放过程"}</button>
     <button type="button" aria-label="下一步" disabled={step>=events.length-1} onClick={()=>{setPlaying(false);setStep(x=>Math.min(events.length-1,x+1));}}><ChevronRight size={18}/></button>
     <input type="range" min={0} max={Math.max(0,events.length-1)} value={step}
       onChange={e=>{setPlaying(false);setStep(Number(e.target.value));}} aria-label="回放进度"/>
     <select aria-label="回放速度" value={speed} onChange={e=>setSpeed(Number(e.target.value))}>
      <option value={3000}>慢速</option><option value={1800}>标准</option><option value={850}>快速</option>
     </select>
    </div>}
   </section>

   <div className="game-two-column">
    <section className="game-panel game-current">
     <div className="game-panel-head">
      <div><span className="game-label">CURRENT DECISION</span>
       <h2>{current?stages(current,step):"暂无事件"}</h2><p>{explanation}</p></div>
      <span className="game-round-tag">Generation {current?.generation??0}</span>
     </div>
     {!current&&<p className="game-muted">该运行没有保存可回放的事件。</p>}
     {current?.stage==="knowledge_discovery"&&<div className="game-big-result">
       <BookOpen size={26}/><strong>{current.retrieved||0} 篇候选论文</strong>
       <p>检索后将进入独立双评审，后续不允许未登记的论文直接作为证据。</p>
      </div>}
     {current?.stage==="independent_paper_screen"&&<div className="game-review-summary">
       <div><strong>{screening.screened_count||0}</strong><span>参与筛选</span></div>
       <div><strong>{current.retained??screening.retained_count??0}</strong><span>最终保留</span></div>
       <div><strong>{current.disagreements??screening.disagreements??0}</strong><span>存在分歧</span></div>
      </div>}
     {(current?.stage==="generate"||current?.stage==="hypothesis_expansion")&&
      <div className="game-generated">
       {(Array.isArray(current.created)?current.created:
          typeof current.created==="string"?[current.created]:[]).map(id=>
        <button type="button" key={id} onClick={()=>setCandidateId(id)}>
         <Sparkles size={16}/><div><strong>{id}</strong><span>{byId.get(id)?.title||"候选选题"}</span></div>
         <ArrowRight size={16}/>
        </button>
       )}
      </div>}
     {current?.stage==="elo_tournament"&&<>
       <div className="game-debate-heading">本轮 {tournamentMatches.length} 场成对博弈 · 每场交换候选位置评审</div>
       {tournamentMatches.length>0&&<>
        <div className="game-match-list">{tournamentMatches.map((m,i)=><button type="button"
          className={matchIndex===i?"game-match-active":""} key={i} onClick={()=>setMatchIndex(i)}>
          {m.left_id} <span>VS</span> {m.right_id}{m.position_disagreement&&<em>位置分歧</em>}
         </button>)}</div>
        {tournamentMatches[Math.min(matchIndex,tournamentMatches.length-1)]&&
         <DebateDetail match={tournamentMatches[Math.min(matchIndex,tournamentMatches.length-1)]}/>}
       </>}
       <div className="game-footnote">这些判断来自 LLM 裁判，不是实验性科学验证。</div>
      </>}
     {current?.stage==="supervisor"&&<div className="game-verdict">
       <span>Supervisor Decision</span>
       <strong>{current.decision==="verify"?"进入科学验证":current.decision==="evolve"?"继续进化":
         current.decision==="expand"?"探索新方向":current.decision==="rollback"?"回退版本":current.decision}</strong>
       <p>{current.reason||"未记录说明"}</p>
      </div>}
     {current?.stage==="hypothesis_evolution"&&<div className="game-children">
       {(current.children||[]).map(child=><button key={child.id} type="button" onClick={()=>setCandidateId(child.id)}>
        <div><span className="game-child-index">GEN {byId.get(child.id)?.generation??"?"}</span>
         <strong>{child.id} · {byId.get(child.id)?.title||"修订假设"}</strong>
         <small>继承自 {child.parent_ids.join(" + ")}</small></div><GitBranch size={20}/>
       </button>)}
      </div>}
     {current?.stage==="rollback"&&<div className="game-verdict">
       <strong>归档第 {current.archived_generation} 代候选</strong><p>旧版本未删除，可继续追溯父子关系。</p>
      </div>}
     {current?.stage==="scientific_gate"&&<div className="game-gate">
       <div className="game-gate-title"><ShieldCheck size={20}/><strong>科学验证结果 · {current.winner||result.winner_id}</strong></div>
       <div><span>真实数据可行性</span><strong>{fact(gate.data_feasible_assessment)}</strong></div>
       <div><span>预实验执行</span><strong>{current.pilot_executed?"已执行":"未执行"}</strong></div>
       <div><span>新颖性证据</span><strong>{fact(gate.novelty_verified)}</strong></div>
       <div><span>实验性结论</span><strong>{fact(gate.experimental_claim_verified)}</strong></div>
       {!!gate.primary_metric&&<p><b>主评价指标：</b>{gate.primary_metric}</p>}
       {!!gate.failure_criteria&&<p><b>否证标准：</b>{gate.failure_criteria}</p>}
      </div>}
    </section>

    <section className="game-panel game-leaderboard">
     <div className="game-panel-head"><div><span className="game-label">TOURNAMENT</span>
       <h2>候选选题排名</h2><p>截至当前步骤的相对 Elo，不代表科学真实质量。</p></div>
       <Trophy size={21}/>
     </div>
     {!ranking.length?<p className="game-muted">选题尚未生成。</p>:
      ranking.map((c,i)=><button type="button" key={c.id}
       className={"game-rank "+(selected?.id===c.id?"game-rank-active":"")}
       onClick={()=>setCandidateId(c.id)}>
       <span className="game-rank-number">{i+1}</span><div>
         <strong>{c.id} <small>{originNames[c.origin||""]||c.origin||"研究假设"} · G{c.generation||0}</small></strong>
         <p>{short(c.title,74)}</p>
        </div>
       <b>{(eloMap.get(c.id)||1200).toFixed(0)}</b>
      </button>)}
     <div className="game-leaderboard-note"><Activity size={14}/> 已呈现 {visibleMatches.length} 场比赛；其中 {winnersInView} 场正反顺序评价不一致。</div>
    </section>
   </div>

   <section className="game-panel game-explorer">
    <div className="game-panel-head"><div><span className="game-label">EVIDENCE & LINEAGE</span>
     <h2>研究假设及证据追踪</h2>
     <p>点击候选可查看完整研究问题、方法、支持论文和局限。</p></div>
     <div className="game-mode-tabs">
       {([{id:"ranking",label:"假设详情"},{id:"lineage",label:"进化谱系"},{id:"papers",label:"文献评审"}] as const).map(tab=>
        <button type="button" className={mode===tab.id?"game-active-tab":""} key={tab.id} onClick={()=>setMode(tab.id)}>{tab.label}</button>)}
     </div>
    </div>
    {mode==="ranking"&&(!selected?<p className="game-muted">等待生成科研假设。</p>:
     <div className="game-details">
       <div className="game-details-header"><span>{selected.id} · G{selected.generation||0}</span>
        <h3>{selected.title}</h3><p>{selected.question||"未记录完整研究问题"}</p></div>
       <div className="game-detail-grid">
        <div><h4>科学机制 / MECHANISM</h4><p>{selected.mechanism||"未记录"}</p></div>
        <div><h4>研究方法 / METHOD</h4><p>{selected.method||"未记录"}</p></div>
        <div><h4>可证伪预测 / FALSIFIABLE PREDICTION</h4><p>{selected.falsifiable_prediction||"未记录"}</p></div>
        <div><h4>最小实验 / MINIMUM EXPERIMENT</h4><p>{selected.minimal_experiment||"未记录"}</p></div>
       </div>
       <div className="game-evidence-grid">
        <div><h4>文献证据</h4>{(selected.paper_ids||[]).length?
          selected.paper_ids?.map(id=><div key={id} className="game-source-item">
            <BookOpen size={14}/>{/^https:\/\/openalex\.org\/W[0-9]+$/.test(id)?
             <a href={id} target="_blank" rel="noopener noreferrer">{id.split("/").pop()}</a>:
             <span>{id}</span>}</div>):<p className="game-muted">未关联论文</p>}</div>
        <div><h4>登记数据资产</h4>{selected.dataset_ids?.length?
           selected.dataset_ids.map(id=><div className="game-source-item" key={id}><Database size={14}/>{id}</div>):
           <p className="game-muted">未登记可用数据，不等于没有研究潜力</p>}</div>
        <div><h4>局限和风险</h4>{(selected.limitations||[]).map((x,i)=><p key={i} className="game-limitation">{x}</p>)}</div>
       </div>
     </div>)}
    {mode==="lineage"&&<div className="game-lineage">
      {groups.map(gen=><div className="game-lineage-col" key={gen}>
       <span>GENERATION {gen}</span>
       {lineage.filter(x=>(x.generation||0)===gen).map(x=><button type="button"
        className={selected?.id===x.id?"game-lineage-selected":""} key={x.id} onClick={()=>{setCandidateId(x.id);setMode("ranking");}}>
         <b><GitBranch size={15}/>{x.id}</b>
         <strong>{short(byId.get(x.id)?.title||"研究假设",58)}</strong>
         {x.parent_ids?.length?<small>← {x.parent_ids.join(" + ")}</small>:<small>初始假设</small>}
       </button>)}
      </div>)}
      {!groups.length&&<p className="game-muted">尚未保存假设父子版本。</p>}
     </div>}
    {mode==="papers"&&<div className="game-jurors">
      {(screening.jurors||[]).map(j=><div key={j.juror} className="game-juror">
       <h3>{j.juror}</h3>
       {Object.entries(j.votes||{}).map(([pid,keep])=><details key={pid}>
        <summary><span>{keep?"保留":"排除"}</span> {pid.replace("https://openalex.org/","")}</summary>
        <p>{j.reasons?.[pid]||"未记录评审原因"}</p>
       </details>)}
      </div>)}
      {screening.adjudicated_ids?.length?<div className="game-juror game-adjudication">
       <h3>第三方仲裁</h3>
       {screening.adjudicated_ids.map(pid=><p key={pid}><b>{pid.replace("https://openalex.org/","")}：</b>{screening.adjudication_reasons?.[pid]||"仲裁意见未记录"}</p>)}
      </div>:null}
      {!screening.jurors?.length&&<p className="game-muted">本轮未保存逐篇的独立投票明细。</p>}
     </div>}
   </section>

   <div className="game-final-note">
     <ShieldAlert size={18}/>
     <p><strong>科研审查说明</strong>：回放仅呈现已保存的 Agent 输出与决策依据，不包含模型私有推理过程。Elo 是 LLM 相对偏好，不能替代新颖性检索、数据许可核验或真实实验。历史记录只有逻辑步骤，没有完整的逐秒时间戳。</p>
   </div>
  </>}
 </div>;
}

function DebateDetail({match}: {match:Match}){
 return <div className="game-debate">
  <div className="game-debate-score"><b>{match.left_id}</b><span>VS</span><b>{match.right_id}</b></div>
  <div className="game-judge-grid">
   <div><span>裁判 A · 原始顺序</span><strong>选择：{winnerText(match.first?.winner_id)}</strong>
    <p>{match.first?.reason||"未记录原因"}</p>
    {!!match.first?.caveat&&<small>保留意见：{match.first.caveat}</small>}</div>
   <div><span>裁判 B · 候选位置对调</span><strong>选择：{winnerText(match.reversed?.winner_id)}</strong>
    <p>{match.reversed?.reason||"未记录原因"}</p>
    {!!match.reversed?.caveat&&<small>保留意见：{match.reversed.caveat}</small>}</div>
  </div>
  <div className="game-debate-result">
   <span>{match.position_disagreement?"两次判断不一致，已记录位置敏感性":"两次判断一致或均认可平局"}</span>
   <b>{match.left_id} Elo {typeof match.delta_left==="number"?(match.delta_left>=0?"+":"")+match.delta_left:"未知"}</b>
  </div>
 </div>;
}
