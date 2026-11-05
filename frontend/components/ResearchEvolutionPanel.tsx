"use client";
import {useCallback,useEffect,useState} from "react";
import {BrainCircuit,BookOpen,CheckCircle2,ChevronDown,ChevronUp,Play,RefreshCw,RotateCcw,ShieldCheck,GitBranch,Star} from "lucide-react";
import {api} from "@/lib/api";

type ResearchLine={line_id:string;line_name:string};
type Paper={id:string;title:string;doi:string;url:string;published:string;venue:string;abstract:string};
type Hypothesis={id:string;title:string;question:string;method:string;prediction:string;experiment:string;
  paper_ids:string[];dataset_ids:string[];baselines:string[];parent_ids:string[];limitations:string[];
  papers?:Paper[];research_path?:string[];machine_score?:number};
type Round={stage:string;value:unknown};
type Trial={id:string;line_id:string;status:string;stage:string;strategy:string;model_calls:number;
 tool_calls:number;input_tokens:number;output_tokens:number;error:string;created_at:string};
type Details=Trial&{papers:Paper[];paper_assessments:{paper_id:string;priority:string;evidence_role:string}[];
 paper_referee:{selected_ids:string[];reason:string;contradictions:string[]};
 versions:Round[];recommendation:{items:Hypothesis[];selection_reason:string;risks:string[]}|null;
 trace:{stage:string;model:string|null;tool_calls:number;at:string}[];
 quality:{ratings:{id:string;score:number;reason:string}[]}};
type Ready={ready:boolean;reasons:string[];max_model_calls:number;paper_human_approval_required:boolean;
 minimum_quality_score:number;line:{name:string;problem:string}|null};
type Policy={policies:{strategy:string;trials:number;mean_reward:number|null}[]};

const statusText:Record<string,string>={
 queued:"准备执行",running:"机器自主探索中",failed:"阶段失败，待恢复",
 held:"未达到推送条件，已内部存档",review_ready:"完成机器质量门控 · 待人工评价"
};
const stageNames:Record<string,string>={
 plan:"科研检索规划",retrieve:"真实学术检索",screen:"论文语义评估",
 paper_referee:"独立证据审查",seed_problem:"问题视角假设",seed_method:"方法视角假设",
 seed_data:"数据视角假设",score_initial:"初始机器评分",
 challenge:"先前研究反驳",counter_search:"反证论文检索",counter_referee:"第二轮独立论文审查",
 revise:"科研假设修订",score_final:"独立终审",
 package:"生成论文与研究路径包",done:"结束"
};
const evidenceStage=new Set(["seed_problem","seed_method","seed_data","revise"]);
const defaultScores={scientific_value:3,novelty:3,feasibility:3,testability:3};

export default function ResearchEvolutionPanel({lines,selectedLine,canEdit,modelConfigured}:{
 lines:ResearchLine[];selectedLine:string;canEdit:boolean;modelConfigured:boolean
}){
 const [lineId,setLineId]=useState("");
 const [ready,setReady]=useState<Ready|null>(null);
 const [tasks,setTasks]=useState<Trial[]>([]);
 const [current,setCurrent]=useState<Details|null>(null);
 const [expand,setExpand]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [message,setMessage]=useState("");
 const [feedback,setFeedback]=useState<"adopt"|"revise"|"defer"|"reject">("revise");
 const [scores,setScores]=useState(defaultScores);
 const [comment,setComment]=useState("");
 const [policies,setPolicies]=useState<Policy|null>(null);
 useEffect(()=>{if(selectedLine&&!lineId)setLineId(selectedLine);},[selectedLine,lineId]);
 const refresh=useCallback(async(runId?:string)=>{
  const list=await api<{items:Trial[]}>("research-evolution");
  setTasks(list.items);
  const id=runId||list.items[0]?.id;
  if(id)setCurrent(await api<Details>("research-evolution/"+id));
  else setCurrent(null);
  setPolicies(await api<Policy>("research-evolution/policy"));
 },[]);
 useEffect(()=>{void refresh().catch(e=>setError(String(e)));},[refresh]);
 useEffect(()=>{
  if(!lineId)return;
  setReady(null);
  void api<Ready>("research-evolution/readiness?line_id="+encodeURIComponent(lineId))
   .then(setReady).catch(e=>setError(String(e)));
 },[lineId]);
 useEffect(()=>{
  if(!tasks.some(t=>t.status==="queued"||t.status==="running"))return;
  const timer=setInterval(()=>{void refresh(current?.id).catch(()=>{});},6500);
  return()=>clearInterval(timer);
 },[tasks,current?.id,refresh]);

 async function start(){
  if(!lineId)return;
  setBusy(true);setError("");setMessage("");
  try{
   const check=await api<Ready>("research-evolution/readiness?line_id="+encodeURIComponent(lineId));
   setReady(check);
   if(!check.ready){setError(check.reasons.join("；"));return;}
   const r=await api<{id:string}>("research-evolution",{
    method:"POST",body:JSON.stringify({line_id:lineId})});
   setMessage("已启动机器自主检索、论文复核与多轮选题演化。最终不达标将自动存档，不推送人工。");
   await refresh(r.id);
  }catch(e){setError(String(e));}
  finally{setBusy(false);}
 }
 async function resume(){
  if(!current)return;setBusy(true);setError("");
  try{
   await api("research-evolution/"+current.id+"/resume",{method:"POST",body:"{}"});
   await refresh(current.id);
  }catch(e){setError(String(e));}
  finally{setBusy(false);}
 }
 async function rate(){
  if(!current)return;setBusy(true);setError("");setMessage("");
  try{
   await api("research-evolution/"+current.id+"/feedback",{
    method:"POST",body:JSON.stringify({decision:feedback,...scores,comment})});
   setMessage("已保存最终科研批阅并更新可解释的探索策略权重；没有微调模型或自动修改团队画像。");
   setComment("");await refresh(current.id);
  }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 const stopped=current?.status==="review_ready"||current?.status==="held";
 return <section className="panel" aria-label="自主科研演化引擎">
  <div className="panel-header"><div>
    <span className="panel-kicker">AUTONOMOUS RESEARCH EVOLUTION</span>
    <h2>自主科研探索与选题演化</h2>
  </div><BrainCircuit size={20}/></div>
  <p className="small muted">自主文献检索与互相审查 → 科学问题、方法、数据三视角竞争 → 反证文献补充与假设演化 → 独立终审 → 合格推荐包 → 人工最终批阅。初始阶段不需要人工选文献。</p>
  {error&&<div className="alert alert-error">{error}</div>}
  {message&&<div className="alert alert-success">{message}</div>}
  <div className="ai-lab-controls">
   <label>选择研究主线
    <select value={lineId} onChange={e=>setLineId(e.target.value)}>
     <option value="">请选择</option>
     {lines.map(x=><option key={x.line_id} value={x.line_id}>{x.line_name}</option>)}
    </select>
   </label>
   <button className="btn btn-primary" disabled={!canEdit||!modelConfigured||!ready?.ready||busy||
      tasks.some(t=>t.status==="queued"||t.status==="running")} onClick={()=>void start()}>
    <Play size={15}/> 自主科研探索
   </button>
  </div>
  {ready&&<div className="small-note"><ShieldCheck size={15}/>
   {ready.ready?"已具备自动科研试验条件":"暂不能启动："+ready.reasons.join("；")}
   {" · "}单轮最多 {ready.max_model_calls} 次模型请求，机器推送阈值 {ready.minimum_quality_score}/100
  </div>}
  {tasks.length>0&&<div className="inline-actions">
    <label>查看历史演化任务
    <select value={current?.id||""} onChange={e=>void refresh(e.target.value)}>
     {tasks.map(x=><option key={x.id} value={x.id}>{x.created_at.slice(0,16)} · {statusText[x.status]||x.status}</option>)}
    </select></label>
    <button className="btn btn-secondary" onClick={()=>void refresh(current?.id)}><RefreshCw size={14}/> 刷新</button>
  </div>}
  {current&&<div className="ai-lab-card">
    <div className="ai-lab-card-top"><span>{statusText[current.status]||current.status}</span>
      <span>探索策略：{current.strategy}</span></div>
    <h3>{stageNames[current.stage]||current.stage}</h3>
    <p className="small muted">模型调用 {current.model_calls} · 学术检索 {current.tool_calls} · 输入 {current.input_tokens} Tokens · 输出 {current.output_tokens} Tokens</p>
    <div className="ai-lab-stage-flow">
     {Object.entries(stageNames).filter(([x])=>x!=="done").map(([id,label],index)=>{
      const stageIndex=Object.keys(stageNames).indexOf(id);
      const currentIndex=Object.keys(stageNames).indexOf(current.stage);
      const done=stopped||stageIndex<currentIndex;
      return <div key={id} className={"ai-lab-stage "+(done?"ai-lab-stage-done":id===current.stage?"ai-lab-stage-current":"")}>
       <span>{done?<CheckCircle2 size={15}/>:index+1}</span><div><strong>{label}</strong></div>
      </div>;
     })}
    </div>
    {current.error&&<p className="alert alert-error">{current.error}</p>}
    {canEdit&&current.status==="failed"&&<button className="btn btn-secondary" disabled={busy} onClick={()=>void resume()}><RotateCcw size={14}/> 从检查点恢复</button>}
    <button className="btn btn-secondary" onClick={()=>setExpand(x=>!x)}>
      <GitBranch size={14}/>{expand?"收起":"查看"}文献审查、反驳与版本谱系
      {expand?<ChevronUp size={14}/>:<ChevronDown size={14}/>}
    </button>
    {expand&&<div>
      <h3>机器选文献与审查记录（共 {current.papers.length} 篇）</h3>
      {current.papers.map(p=><p key={p.id} className="small">
       <BookOpen size={13}/> <a href={p.url} target="_blank" rel="noopener noreferrer">{p.title}</a>
       {" · "}{p.venue||"来源待核验"}{p.doi?" · DOI: "+p.doi:""}
       {" · "}{current.paper_assessments.find(x=>x.paper_id===p.id)?.evidence_role||"待机器审查"}
      </p>)}
      <p className="small muted">论文复核：{current.paper_referee?.reason||"尚未完成"}</p>
      {current.versions.map((r,i)=><div className="ai-lab-critic" key={i}>
        <strong>{stageNames[r.stage]||r.stage}</strong>
        {evidenceStage.has(r.stage)?
          ((r.value as Hypothesis[])||[]).map(c=><p key={c.id}>{c.title} · {c.question}</p>):
          <pre style={{whiteSpace:"pre-wrap",fontSize:12}}>{JSON.stringify(r.value,null,2).slice(0,2500)}</pre>}
      </div>)}
    </div>}
  </div>}
  {current?.status==="held"&&<div className="small-note">本轮候选方案未满足独立评分、反证检索或证据门控要求，保留过程记录供未来检索，不向人工推送。</div>}
  {current?.status==="review_ready"&&current.recommendation&&<div className="ai-lab-card-list">
   <h3>通过机器审查的最终科研推荐</h3>
   {current.recommendation.items.map(idea=><article className="ai-lab-card" key={idea.id}>
    <div className="ai-lab-card-top"><span>待人工科研评价</span><span>机器评分 {idea.machine_score}/100</span></div>
    <h3>{idea.title}</h3>
    <p><b>研究问题：</b>{idea.question}</p>
    <p><b>方法：</b>{idea.method}</p>
    <p><b>可证伪预测：</b>{idea.prediction}</p>
    <p><b>最小实验：</b>{idea.experiment}</p>
    <p><b>对照基线：</b>{idea.baselines.join("、")}</p>
    <strong>推荐研究路径</strong>
    <ol>{(idea.research_path||[]).map((x,i)=><li key={i}>{x}</li>)}</ol>
    <strong>配套学术论文（真实检索所得）</strong>
    {(idea.papers||[]).map(p=><p key={p.id} className="small">
      <BookOpen size={14}/><a href={p.url} target="_blank" rel="noopener noreferrer">
        {p.title}</a> · {p.venue||"OpenAlex"} {p.doi&&" · DOI: "+p.doi}</p>)}
    <p className="small muted">科研创新性尚未全面核验；论文元数据或模型自评分不证明研究结论可靠。</p>
   </article>)}
   {canEdit&&<div className="ai-lab-card">
    <h3>人工最终评价与策略反馈</h3>
    <label>推荐结论
      <select value={feedback} onChange={e=>setFeedback(e.target.value as typeof feedback)}>
       <option value="adopt">值得推进</option><option value="revise">需要修订</option>
       <option value="defer">暂缓考虑</option><option value="reject">拒绝推荐</option>
      </select>
    </label>
    <div className="ai-lab-controls">
     {(["scientific_value","novelty","feasibility","testability"] as const).map(k=>
      <label key={k}>{({scientific_value:"科学价值",novelty:"创新增量",feasibility:"可行性",testability:"可证伪性"} as const)[k]}
       <select value={scores[k]} onChange={e=>setScores(s=>({...s,[k]:Number(e.target.value)}))}>
        {[1,2,3,4,5].map(n=><option key={n} value={n}>{n}/5</option>)}
       </select>
      </label>)}
    </div>
    <label>评阅意见
      <textarea rows={3} value={comment} onChange={e=>setComment(e.target.value)}
        placeholder="为什么值得推进或需要修改？这些意见将用于改进下一轮搜索与智能体组合"/>
    </label>
    <button className="btn btn-primary" disabled={busy} onClick={()=>void rate()}><Star size={15}/> 保存人工评价并回流策略</button>
   </div>}
  </div>}
  {policies&&<p className="small muted">策略学习（UCB1，非模型微调）：{policies.policies.map(x=>
   x.strategy+" "+x.trials+"次"+(x.mean_reward===null?"":" / 平均奖励 "+x.mean_reward)).join(" · ")}</p>}
 </section>;
}
