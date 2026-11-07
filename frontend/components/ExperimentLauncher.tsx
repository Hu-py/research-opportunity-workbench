"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {Activity,AlertTriangle,ArrowUpRight,CheckCircle2,
        GitBranch,Play,RefreshCw,Settings2,ShieldCheck,SlidersHorizontal} from "lucide-react";

type Source="workbench_sync"|"public_demo"|"team_evidence"|"approved_secret";
type Generation="0"|"1"|"2";
type Papers="4"|"6"|"8";
type Pairs="1"|"2"|"3";
type LaunchInput={
 evidence_source:Source;max_generations:Generation;max_papers:Papers;
 max_pairs:Pairs;stream_live_events:boolean;synthetic_pilot:boolean;
 reuse_llm_cache:boolean;replay_namespace:string;
 save_knowledge_graph:boolean;bilingual_report:boolean
};
type RemoteRun={
 id:number;status:string;conclusion:string|null;created_at:string;
 html_url:string;display_title:string;run_number:number
};
type LauncherStatus={
 configured:boolean;workflow_url:string;runs:RemoteRun[];detail?:string
};
const initial:LaunchInput={
 evidence_source:"workbench_sync",max_generations:"0",max_papers:"4",max_pairs:"1",
 stream_live_events:true,synthetic_pilot:false,reuse_llm_cache:false,
 replay_namespace:"studio_default",save_knowledge_graph:true,bilingual_report:true
};
function date(value:string){
 const time=new Date(value);
 return Number.isFinite(time.getTime())?
   time.toLocaleString("zh-CN",{month:"2-digit",day:"2-digit",
     hour:"2-digit",minute:"2-digit",hour12:false}):"未知时间";
}
function remoteStatus(run:RemoteRun){
 if(run.status==="completed"){
   return run.conclusion==="success"?"已完成 / Succeeded":
     run.conclusion==="failure"?"失败 / Failed":"结束 / "+(run.conclusion||"Unknown");
 }
 if(run.status==="queued"||run.status==="waiting"||run.status==="pending")return "排队中 / Queued";
 if(run.status==="in_progress")return "运行中 / Running";
 return run.status;
}
const fieldNames:{field:keyof LaunchInput;label:string;help:string}[]=[
 {field:"stream_live_events",label:"实时事件同步 / Live monitoring",
  help:"在 SQL 007 已创建后，按节点写入实时进度。"},
 {field:"save_knowledge_graph",label:"保存研究知识图谱 / Knowledge graph",
  help:"仅团队证据来源可用，需要 SQL 004。"},
 {field:"bilingual_report",label:"中英对照报告 / Bilingual report",
  help:"对最终科研结果生成中文与英文双栏总结，最多增加一次模型调用。"},
 {field:"synthetic_pilot",label:"合成预实验 / Synthetic pilot",
  help:"仅适用于网络韧性主线；固定代码模拟不构成科学验证。"},
 {field:"reuse_llm_cache",label:"精确调用缓存 / Exact-request replay",
  help:"需先执行 SQL 006；仅完全相同请求可以复用缓存。"}
];

export default function ExperimentLauncher(){
 const [params,setParams]=useState<LaunchInput>(initial);
 const [status,setStatus]=useState<LauncherStatus|null>(null);
 const [error,setError]=useState("");
 const [message,setMessage]=useState("");
 const [busy,setBusy]=useState(false);
 const [confirmed,setConfirmed]=useState(false);
 const [advanced,setAdvanced]=useState(false);

 const refresh=useCallback(async()=>{
  try{
   const r=await fetch("/api/research-lab/launch",{cache:"no-store"});
   const j=await r.json() as LauncherStatus&{detail?:string};
   if(!r.ok)throw Error(j.detail||"读取 GitHub 运行状态失败");
   setStatus(j);
   if(!j.configured)setError(j.detail||"需要配置启动 Token");
  }catch(e){setError(e instanceof Error?e.message:"无法获取启动状态");}
 },[]);
 useEffect(()=>{
   void refresh();
   const tick=window.setInterval(()=>{void refresh();},12000);
   return()=>window.clearInterval(tick);
 },[refresh]);

 const running=status?.runs?.some(r=>
  ["queued","in_progress","requested","waiting","pending"].includes(r.status))||false;
 const maxCalls=Number(params.max_generations)==2?55:30;
 const frontierCeiling=maxCalls+(params.bilingual_report?1:0);
 const teamPortrait=["workbench_sync","team_evidence"].includes(params.evidence_source);
 const totalCeiling=frontierCeiling+(teamPortrait?9:0);
 const chosenParams=useMemo(()=>{
   return {...params,save_knowledge_graph:teamPortrait&&params.save_knowledge_graph};
 },[params,teamPortrait]);
 function update<K extends keyof LaunchInput>(key:K,value:LaunchInput[K]){
   setParams(s=>({...s,[key]:value}));setConfirmed(false);setMessage("");setError("");
 }
 async function launch(){
  if(!confirmed||busy||running||!status?.configured)return;
  setBusy(true);setError("");setMessage("");
  try{
   const r=await fetch("/api/research-lab/launch",{
     method:"POST",headers:{"Content-Type":"application/json"},
     body:JSON.stringify(chosenParams),credentials:"same-origin"
   });
   const body=await r.json() as {detail?:string;status?:string;max_model_calls?:number};
   if(!r.ok)throw Error(body.detail||"实验提交失败");
   setMessage("已提交至 GitHub Actions / Submitted. 等待调度后可在下方查看真实运行步骤。");
   setConfirmed(false);
   window.setTimeout(()=>{void refresh();},2200);
  }catch(e){setError(e instanceof Error?e.message:"无法启动实验");}
  finally{setBusy(false);}
 }
 return <section className="game-panel game-launcher" aria-label="启动科研实验 Run Research Experiment">
   <header className="game-launcher-head">
    <div><span className="game-label">EXPERIMENT CONTROL CENTER</span>
     <h2><SlidersHorizontal size={18}/> 启动新实验 / Launch experiment</h2>
     <p>选择 Agent 的实验规模、竞争强度及输出方式，结果自动进入下方实时监控和历史回放。</p>
    </div><div className="game-launcher-head-actions">
      <button type="button" onClick={()=>void refresh()} aria-label="刷新实验状态"><RefreshCw size={15}/> 刷新</button>
      <a target="_blank" rel="noopener noreferrer"
         href="https://github.com/Hu-py/research-agent-lab/actions/workflows/live-frontier.yml">
         Actions <ArrowUpRight size={14}/></a>
    </div>
   </header>
   <div className="game-launcher-fields">
    <label><b>研究证据 / Evidence source</b>
     <select value={params.evidence_source}
      onChange={e=>update("evidence_source",e.target.value as Source)}>
      <option value="workbench_sync">现有团队画像与成果 / Workbench sync</option>
      <option value="public_demo">公开演示数据 / Public demo</option>
      <option value="team_evidence">已授权团队证据 / Approved team JSON</option>
      <option value="approved_secret">已批准快照 / Approved snapshot</option>
     </select>
     <small>私有来源要求 GitHub Secrets 中已有授权；不上传原始 CUSP 数据。</small>
    </label>
    <label><b>进化轮数 / Evolution generations</b>
     <select value={params.max_generations}
       onChange={e=>update("max_generations",e.target.value as Generation)}>
      <option value="0">0 — 初代基线 / Baseline</option>
      <option value="1">1 — 自适应进化 / Adaptive evolution</option>
      <option value="2">2 — 强制两轮进化 / Two controlled rounds</option>
     </select>
     <small>轮数增加意味着更多批评、改写和重赛。</small>
    </label>
    <label><b>论文上限 / Papers to screen</b>
     <select value={params.max_papers}
       onChange={e=>update("max_papers",e.target.value as Papers)}>
      <option value="4">4 — 低预算 / Low</option>
      <option value="6">6 — 标准 / Standard</option>
      <option value="8">8 — 更深入 / Extended</option>
     </select>
     <small>OpenAlex 发现后由独立 Agent 审核。</small>
    </label>
    <label><b>每轮对决 / Pairwise matches per round</b>
     <select value={params.max_pairs}
       onChange={e=>update("max_pairs",e.target.value as Pairs)}>
      <option value="1">1 — 最小实验 / Minimal</option>
      <option value="2">2 — 平衡 / Balanced</option>
      <option value="3">3 — 更多对决 / More comparisons</option>
     </select>
     <small>每场评审都会对调候选位置。</small>
    </label>
   </div>
   <div className="game-launcher-switches">
    {fieldNames.map(item=>{
      const disabled=item.field==="save_knowledge_graph"&&!teamPortrait;
      return <label key={item.field} className={"game-launcher-toggle "+(disabled?"game-disabled":"")}>
        <input type="checkbox" checked={Boolean(chosenParams[item.field])}
          disabled={disabled}
          onChange={e=>update(item.field,e.target.checked as never)}/>
        <span><b>{item.label}</b><small>{item.help}</small></span>
      </label>;
    })}
   </div>
   <div className="game-launcher-advanced">
    <button type="button" onClick={()=>setAdvanced(v=>!v)}>
      <Settings2 size={15}/> {advanced?"收起高级设置 / Hide advanced":"高级设置 / Advanced settings"}
    </button>
    {advanced&&<label><b>缓存实验命名空间 / Replay namespace</b>
      <input type="text" spellCheck={false} maxLength={64}
        value={params.replay_namespace}
        onChange={e=>update("replay_namespace",e.target.value)}/>
      <small>同一失败实验重跑使用相同名称；A/B 对照实验请设置不同名称。</small>
    </label>}
   </div>
   <div className="game-launcher-footer">
    <div className="game-launcher-budget">
     <Activity size={18}/>
     <div><strong>最多约 {totalCeiling} 次模型调用 / Up to {totalCeiling} model requests</strong>
      <small>Frontier {frontierCeiling} 次{teamPortrait?" + 团队画像至多 9 次":""}；非精确费用估算，实际调用可能更少或不同。</small>
     </div>
    </div>
    <label className="game-launcher-confirm">
      <input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>
      我确认启动会调用付费 DeepSeek，且已核验所选数据的共享授权。
      <span> / I understand the model cost and data authorization requirements.</span>
    </label>
    <button type="button" className="game-launcher-start"
      disabled={!confirmed||busy||running||!status?.configured||
        !/^[A-Za-z0-9_-]{1,64}$/.test(params.replay_namespace)}
      onClick={()=>void launch()}>
      <Play size={17}/> {busy?"提交中 / Submitting":
        running?"已有实验运行 / Already running":"启动科研博弈 / Start research run"}
    </button>
   </div>
   {status&&!status.configured&&<div className="game-notice">
     <AlertTriangle size={16}/>
     需要在 Vercel 配置服务端 RESEARCH_LAB_GITHUB_TOKEN，授权 GitHub Actions 读写权限后才能启动。
     / A server-only Actions token is required.
   </div>}
   {error&&<div className="game-error">{error}</div>}
   {message&&<div className="game-launcher-success"><CheckCircle2 size={15}/>{message}</div>}
   {!!status?.runs?.length&&<div className="game-launcher-runs">
     <h3><GitBranch size={15}/> 最近 GitHub 实验 / Recent workflow runs</h3>
     {status.runs.slice(0,4).map(r=><a key={r.id} href={r.html_url} target="_blank" rel="noopener noreferrer">
       <span>{date(r.created_at)}</span>
       <strong>{remoteStatus(r)}</strong>
       <small>#{r.run_number}</small>
       <ArrowUpRight size={14}/>
     </a>)}
   </div>}
   <p className="game-launcher-disclaimer">
     <ShieldCheck size={13}/> 只向 GitHub 提交安全校验后的参数，密钥始终保存在服务端。启动成功不代表科学结论已验证。
     / Parameter-only dispatch; model judgments are not external scientific validation.
   </p>
 </section>;
}
