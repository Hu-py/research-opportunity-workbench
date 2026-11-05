"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {BrainCircuit,CheckCircle2,Database,ExternalLink,KeyRound,LockKeyhole,Play,RefreshCw,RotateCcw,ShieldCheck,Trash2,XCircle} from "lucide-react";
import {api} from "@/lib/api";
import ScientificExplorationPanel from "@/components/ScientificExplorationPanel";
import ScientificTournamentPanel from "@/components/ScientificTournamentPanel";
import ResearchEvolutionPanel from "@/components/ResearchEvolutionPanel";

type ModelConfig={
 provider:string;configured:boolean;vault_ready:boolean;
 fast_model:string;reason_model:string;daily_enabled:boolean;key_storage:string
};
type AnalysisRun={
 id:string;line_id:string;line_name:string;source:string;
 status:string;stage:string;error:string;model_calls:number;
 input_tokens:number;output_tokens:number;papers_in_context:number;
 created_at:string;updated_at:string
};
type Opportunity={
 id:string;run_id:string;line_id:string;title:string;question:string;method:string;why_now:string;
 papers:{id:string;title:string;url:string;doi:string}[];
 dataset_ids:string[];baselines:string[];minimal_experiment:string;
 risks:string[];critic:{verdict:string;novelty_status:string;
 fatal_gaps:string[];revised_experiment:string};status:string
};
type Dashboard={config:ModelConfig;runs:AnalysisRun[];cards:Opportunity[];note:string};
type Strategy={line_id:string;line_name:string};
type CatalogItem={id:string;name:string};
const stages=[
 {id:"planner",title:"Research Planner",sub:"读取研究瓶颈、数据属性和成果"},
 {id:"reader",title:"Paper Reader",sub:"解析人工审核过的论文标题与摘要"},
 {id:"generator",title:"Method Transfer + Generator",sub:"迁移方法，提出有对照实验的研究问题"},
 {id:"critic",title:"Idea Critic",sub:"检验先前研究风险与数据可行性"}
];

export default function AIResearchLab({canAdmin,canEdit}:{canAdmin:boolean;canEdit:boolean}){
 const [data,setData]=useState<Dashboard|null>(null);
 const [strategies,setStrategies]=useState<Strategy[]>([]);
 const [datasets,setDatasets]=useState<CatalogItem[]>([]);
 const [selected,setSelected]=useState("");
 const [secret,setSecret]=useState("");
 const [reasonModel,setReasonModel]=useState("deepseek-v4-pro");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");

 const load=useCallback(async()=>{
   const [dashboard,strategiesResponse,catalog]=await Promise.all([
     api<Dashboard>("ai-lab"),
     api<{strategies:Strategy[]}>("opportunity-engine"),
     api<{items:CatalogItem[]}>("cusp/datasets")
   ]);
   setData(dashboard);setStrategies(strategiesResponse.strategies);
   setDatasets(catalog.items);setReasonModel(dashboard.config.reason_model);
   setSelected(old=>old||strategiesResponse.strategies[0]?.line_id||"");
 },[]);
 useEffect(()=>{void load().catch(e=>setError(String(e)));},[load]);
 const running=data?.runs.some(x=>x.status==="queued"||x.status==="running")||false;
 useEffect(()=>{
   if(!running)return;
   const timer=setInterval(()=>{void load().catch(()=>{});},6000);
   return()=>clearInterval(timer);
 },[running,load]);
 const datasetById=useMemo(()=>Object.fromEntries(datasets.map(x=>[x.id,x.name])),[datasets]);
 const activeRun=data?.runs[0];
 async function saveConfig(fields:Record<string,unknown>){
   setBusy(true);setError("");setNotice("");
   try{
     await api("ai-lab/config",{method:"PUT",body:JSON.stringify(fields)});
     // Immediately release the secret from the input after a successful save.
     setSecret("");await load();
     setNotice("模型配置已安全保存。密钥只在服务器解密使用，页面不回显。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function removeKey(){
   if(!window.confirm("确认移除已保存的 DeepSeek Key，并关闭每日自动分析？"))return;
   setBusy(true);setError("");
   try{await api("ai-lab/key",{method:"DELETE"});setSecret("");await load();setNotice("已移除密钥，自动分析已关闭。");}
   catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function start(){
   if(!selected)return;
   setBusy(true);setError("");setNotice("");
   try{
     const result=await api<{id:string}>("ai-lab/run",{
       method:"POST",body:JSON.stringify({line_id:selected})});
     setNotice("已启动四阶段 AI 深度分析："+result.id.slice(0,8)+
       "。每完成一个阶段都会保存中间结果；运行会产生 DeepSeek API 用量。");
     await load();
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function resume(id:string){
   setBusy(true);setError("");
   try{await api("ai-lab/runs/"+id+"/resume",{method:"POST",body:"{}"});await load();setNotice("已从上一阶段检查点恢复运行。");}
   catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function review(id:string,status:"shortlist"|"rejected"|"draft"){
   setBusy(true);setError("");
   try{await api("ai-lab/cards/"+id,{method:"PATCH",body:JSON.stringify({status})});await load();setNotice("已保存选题评价与审查状态。");}
   catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 return <div className="ai-lab-page repository-root">
   <div className="page-heading">
     <span className="panel-kicker">RESEARCH OPPORTUNITY ENGINE · P2</span>
     <h1>AI 科研选题实验台</h1>
     <p>自主检索、论文Agent互审、多轮科研假设演化和反证检索，最终只推送通过证据门控的选题；人工评价只发生在成果推荐之后。</p>
   </div>
   {error&&<div className="alert alert-error">{error}</div>}
   {notice&&<div className="alert alert-success">{notice}</div>}
   <section className="panel ai-lab-config">
     <div className="panel-header"><div>
       <span className="panel-kicker">SECURE MODEL CONFIGURATION</span>
       <h2>DeepSeek 模型连接</h2></div><LockKeyhole size={20}/></div>
     <div className="ai-lab-status">
       <span className={data?.config.configured?"ai-lab-key-ready":"ai-lab-key-missing"}>
         {data?.config.configured?<CheckCircle2 size={15}/>:<KeyRound size={15}/>}
         {data?.config.configured?"DeepSeek Key 已加密保存":"尚未配置 DeepSeek Key"}
       </span>
       <span>服务器加密服务：{data?.config.vault_ready?"已启用":"尚未启用"}</span>
     </div>
     <p className="small muted">只允许管理员配置，密钥通过 HTTPS 发送至 FastAPI 后端，用独立的服务器密钥加密存入 PostgreSQL。不会显示原始 Key，也不会写入公开 GitHub。</p>
     {canAdmin&&<div className="ai-lab-secret-form">
       <label>DeepSeek API Key
         <input type="password" value={secret} autoComplete="new-password"
           placeholder={data?.config.configured?"填写新 Key 可替换现有密钥":"在这里粘贴 DeepSeek API Key"}
           onChange={e=>setSecret(e.target.value)} maxLength={320}/>
       </label>
       <label>选题推理与批评模型
         <select value={reasonModel} onChange={e=>setReasonModel(e.target.value)}>
           <option value="deepseek-v4-pro">DeepSeek V4 Pro（深入分析）</option>
           <option value="deepseek-flash">DeepSeek Flash（低成本试验）</option>
         </select>
       </label>
       <div className="inline-actions">
         <button className="btn btn-primary" disabled={busy||!data?.config.vault_ready}
           onClick={()=>void saveConfig({...(secret.trim()?{key:secret.trim()}:{}),
             reason_model:reasonModel})}><KeyRound size={15}/> 保存模型配置</button>
         {data?.config.configured&&<button className="btn btn-secondary" disabled={busy}
           onClick={()=>void removeKey()}><Trash2 size={14}/> 移除 Key</button>}
       </div>
       <label className="ai-lab-daily">
         <input type="checkbox" checked={Boolean(data?.config.daily_enabled)}
           disabled={busy||!data?.config.configured}
           onChange={e=>void saveConfig({daily_enabled:e.target.checked})}/>
         启用每日画像检索与预分析、每周 LLM 综合报告（付费 API）
       </label>
       <p className="small muted">自动文献预分析可处理尚待人工审核的候选论文，但不会自动批准；每周报告只形成待审核科研假设。手动启动四阶段深度选题仍需人工确认，独立产生 API 成本。</p>
     </div>}
     {!canAdmin&&<p className="small muted">请由团队管理员在这里配置模型密钥。研究成员可以查看分析结果与按权限手动运行。</p>}
   </section>

   <ResearchEvolutionPanel selectedLine={selected} lines={strategies}
     canEdit={canEdit} modelConfigured={Boolean(data?.config.configured)}/>
   <details className="panel">
     <summary className="small"><strong>展开历史科研流程与 A/B 对照实验</strong>（旧流程需先人工筛文献；新流程不需要）</summary>
   <section className="panel">
     <div className="panel-header"><div><span className="panel-kicker">STEPWISE WORKFLOW</span><h2>启动与监控深度选题分析</h2></div><BrainCircuit size={20}/></div>
     <p className="small muted">仅分析通过「科研关联与文献发现 → 候选论文」人工标注为相关或方法借鉴的文献，最多 5 篇／次。不读取原始数据文件；受限数据资产不会发送给模型。</p>
     <div className="ai-lab-controls">
       <label>研究主线
         <select value={selected} onChange={e=>setSelected(e.target.value)}>
           {strategies.map(x=><option key={x.line_id} value={x.line_id}>{x.line_name}</option>)}
         </select>
       </label>
       <button className="btn btn-primary" disabled={busy||!canEdit||!data?.config.configured||running||!selected}
         onClick={()=>void start()}><Play size={15}/> 深度发现选题</button>
       <button className="btn btn-secondary" disabled={busy}
         onClick={()=>void load()}><RefreshCw size={15}/> 刷新状态</button>
     </div>
     {activeRun&&<div className="ai-lab-run-box">
       <div className="ai-lab-run-head"><strong>{activeRun.line_name}</strong>
         <span>{activeRun.status==="completed"?"分析完成":activeRun.status==="failed"?"运行失败":
           activeRun.status==="running"?"正在运行":"等待执行"} · {activeRun.source==="scheduled"?"定时":"手动"}</span></div>
       <div className="ai-lab-stage-grid">{stages.map((s,i)=>{
         const index=stages.findIndex(x=>x.id===activeRun.stage);
         const reached=activeRun.status==="completed"||activeRun.stage==="done"||i<index;
         const current=s.id===activeRun.stage;
         return <div className={"ai-lab-stage "+(reached?"ai-lab-stage-done":current?"ai-lab-stage-current":"")} key={s.id}>
           <span>{reached?<CheckCircle2 size={17}/>:current&&activeRun.status==="running"?<RotateCcw size={17}/>:<span>{i+1}</span>}</span>
           <div><strong>{s.title}</strong><small>{s.sub}</small></div>
         </div>;
       })}</div>
       <p className="small muted">模型调用 {activeRun.model_calls} 次 · 输入 {activeRun.input_tokens} Tokens · 输出 {activeRun.output_tokens} Tokens · 参考 {activeRun.papers_in_context} 篇已审核论文</p>
       {activeRun.error&&<p className="alert alert-error">{activeRun.error}</p>}
       {activeRun.status==="failed"&&canEdit&&<button className="btn btn-secondary" disabled={busy}
         onClick={()=>void resume(activeRun.id)}><RotateCcw size={14}/> 从检查点重试</button>}
     </div>}
     {data&&!data.runs.length&&<div className="small-note">还没有 AI 分析任务。配置密钥、审核至少一篇论文后即可试运行。</div>}
   </section>

   <ScientificExplorationPanel selectedLine={selected} lines={strategies}
     canEdit={canEdit} modelConfigured={Boolean(data?.config.configured)}/>
   <ScientificTournamentPanel selectedLine={selected} lines={strategies}
     canEdit={canEdit} canAdmin={canAdmin}
     modelConfigured={Boolean(data?.config.configured)}/>

   <section className="panel">
     <div className="panel-header"><div><span className="panel-kicker">AI OPPORTUNITY DRAFTS</span><h2>候选选题与审查</h2></div><Database size={18}/></div>
     {!data?.cards.length?<div className="small-note">尚未生成深度选题卡片。旧的规则模板选题仍保留在原研究选题池，二者不会混淆。</div>:
       <div className="ai-lab-card-list">{data.cards.map(card=><article className="ai-lab-card" key={card.id}>
         <div className="ai-lab-card-top"><span>{card.status==="shortlist"?"已加入候选清单":card.status==="rejected"?"暂不采用":"待人工审核"}</span>
           <span>{card.critic?.verdict||"尚未审查"}</span></div>
         <h3>{card.title}</h3>
         <p><b>研究问题：</b>{card.question}</p>
         <p><b>方法与突破口：</b>{card.method}</p>
         <p><b>为何值得研究：</b>{card.why_now}</p>
         <p><b>最小可行实验：</b>{card.minimal_experiment}</p>
         <p><b>基线：</b>{card.baselines.join("、")||"尚未确认"}</p>
         <p><b>可关联数据属性：</b>{card.dataset_ids.length?
             card.dataset_ids.map(id=>datasetById[id]||"未公开的数据登记").join("、"):"没有已核验的数据匹配"}</p>
         <div className="ai-lab-paper-list"><strong>文献证据（仅元数据及摘要）</strong>
           {card.papers.map(p=><a key={p.id} href={p.url} target="_blank" rel="noopener noreferrer">
             {p.title} <ExternalLink size={12}/></a>)}</div>
         <div className="ai-lab-critic">
           <strong>Critic 反向审查</strong>
           <p>{card.critic?.novelty_status||"创新性尚未核验"}</p>
           {(card.critic?.fatal_gaps||[]).map((g,i)=><p key={i}>· {g}</p>)}
           <p><b>实验修订：</b>{card.critic?.revised_experiment||"待核查"}</p>
         </div>
         {card.risks.length>0&&<p className="small muted">初步风险：{card.risks.join("；")}</p>}
         {canEdit&&<div className="inline-actions">
           <button className="btn btn-secondary" disabled={busy} onClick={()=>void review(card.id,"shortlist")}><CheckCircle2 size={14}/> 值得跟进</button>
           <button className="btn btn-secondary" disabled={busy} onClick={()=>void review(card.id,"rejected")}><XCircle size={14}/> 暂缓</button>
           {card.status!=="draft"&&<button className="btn btn-secondary" disabled={busy} onClick={()=>void review(card.id,"draft")}>恢复待审</button>}
         </div>}
       </article>)}</div>}
     <div className="small-note"><ShieldCheck size={15}/> AI 分析的成果仅是候选科研假设；因尚未实现系统性的先前研究检索，不得宣称创新性已验证或已发表论文的实验结论。</div>
   </section>
   </details>
 </div>;
}
