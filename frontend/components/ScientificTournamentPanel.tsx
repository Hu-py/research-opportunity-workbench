"use client";

import {useCallback,useEffect,useState} from "react";
import {BrainCircuit,GitBranch,Play,RefreshCw,RotateCcw,ShieldCheck,Users} from "lucide-react";
import {api} from "@/lib/api";

type Line={line_id:string;line_name:string};
type Summary={id:string;question:string;status:string;stage:string;
 model_calls:number;input_tokens:number;output_tokens:number;error:string};
type Idea={id?:string;title:string;question:string;mechanism?:string;
 falsifiable_prediction?:string;method:string;minimal_experiment:string;
 baselines:string[];limitations?:string[]};
type Decision={outcome:string;selected_ids:string[];reason:string;
 unresolved_disagreements:string[];stopping_reason:string};
type Run=Summary&{review_unblinded:boolean;baseline:Idea[];round0:Idea[];revisions:Idea[];
 critiques:{target_id:string;stance:string;objections:string[];tests:string[]}[];
 decision:Decision|null;trace:{stage:string;status:string;recorded_at:string}[]};
type Blind={cards:{blind_id:string;ideas:Idea[];outcome?:string}[]};
type Preflight={
 ready:boolean;model_configured:boolean;vault_ready:boolean;
 persistent_database:boolean;approved_papers:number;registered_datasets:number;
 remaining_model_calls:number;remaining_token_allowance:number;
 maximum_trial_calls:number;reserved_trial_tokens:number;
 notes:string[];does_not_invoke_model:boolean
};
type Scores={scientific_value:number;novelty:number;feasibility:number;testability:number};
const scoreNames:{key:keyof Scores;label:string}[]=[
 {key:"scientific_value",label:"科学价值"},
 {key:"novelty",label:"研究增量"},
 {key:"feasibility",label:"数据可行性"},
 {key:"testability",label:"可证伪性"}
];
const DEFAULT:Scores={scientific_value:3,novelty:3,feasibility:3,testability:3};
const decisions:Record<string,string>={
 single:"保留一项优选研究方向",plural:"保留多个相互竞争的研究方向",
 none:"本轮全部淘汰",needs_evidence:"证据不足，需重新检索"
};
const runStatus:Record<string,string>={
 queued:"已排队",running:"正在竞争",completed:"竞赛结束 · 待人工评价",
 failed:"运行失败"
};

export default function ScientificTournamentPanel({lines,selectedLine,canEdit,canAdmin,
 modelConfigured}:{lines:Line[];selectedLine:string;canEdit:boolean;canAdmin:boolean;
 modelConfigured:boolean}){
 const [lineId,setLineId]=useState("");
 const [question,setQuestion]=useState("");
 const [preflight,setPreflight]=useState<Preflight|null>(null);
 const [preflightError,setPreflightError]=useState("");
 const [checkingPreflight,setCheckingPreflight]=useState(false);
 const [runs,setRuns]=useState<Summary[]>([]);
 const [current,setCurrent]=useState<Run|null>(null);
 const [blind,setBlind]=useState<Blind|null>(null);
 const [scores,setScores]=useState<Record<string,Scores>>({});
 const [recommendations,setRecommendations]=useState<Record<string,"test"|"investigate"|"reject">>({});
 const [showTrace,setShowTrace]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [message,setMessage]=useState("");
 const [feedbackKind,setFeedbackKind]=useState("human_review");
 const [finding,setFinding]=useState("");
 const [reference,setReference]=useState("");
 const [limitation,setLimitation]=useState("");
 useEffect(()=>{if(!lineId&&selectedLine)setLineId(selectedLine);},[selectedLine,lineId]);
 const checkReadiness=useCallback(async(id:string)=>{
   if(!id){setPreflight(null);return null;}
   setCheckingPreflight(true);
   setPreflightError("");
   try{
     const ready=await api<Preflight>("scientific-tournaments/preflight?line_id="+encodeURIComponent(id));
     setPreflight(ready);
     return ready;
   }catch(e){
     setPreflight(null);
     setPreflightError(e instanceof Error?e.message:String(e));
     return null;
   }finally{setCheckingPreflight(false);}
 },[]);
 useEffect(()=>{
   if(!lineId){setPreflight(null);return;}
   let active=true;
   setPreflight(null);
   void api<Preflight>("scientific-tournaments/preflight?line_id="+encodeURIComponent(lineId))
     .then(value=>{if(active){setPreflight(value);setPreflightError("");}})
     .catch(e=>{if(active){setPreflight(null);setPreflightError(String(e));}});
   return()=>{active=false;};
 },[lineId]);
 const refresh=useCallback(async(id?:string)=>{
   const data=await api<{items:Summary[]}>("scientific-tournaments");
   setRuns(data.items);
   const target=id||data.items[0]?.id;
   if(!target){setCurrent(null);setBlind(null);return;}
   const item=await api<Run>("scientific-tournaments/"+target);
   setCurrent(item);
   if(item.status==="completed"){
     setBlind(await api<Blind>("scientific-tournaments/"+target+"/blind"));
   }else setBlind(null);
 },[]);
 useEffect(()=>{void refresh().catch(e=>setError(String(e)));},[refresh]);
 const active=runs.some(r=>r.status==="queued"||r.status==="running");
 useEffect(()=>{
   if(!active)return;
   const handle=setInterval(()=>{void refresh().catch(()=>{});},6000);
   return()=>clearInterval(handle);
 },[active,refresh]);

 async function start(){
   if(!lineId||question.trim().length<10)return;
   setBusy(true);setError("");setMessage("");
   try{
     const verified=await checkReadiness(lineId);
     if(!verified?.ready){
       setError(verified?.notes.join("；")||"无法确认科研竞赛就绪状态，请先检查密钥、研究数据及当日预算");
       return;
     }
     const out=await api<{id:string}>("scientific-tournaments",{
       method:"POST",body:JSON.stringify({line_id:lineId,question:question.trim()})
     });
     setMessage("已提交同输入 A/B 科研竞赛："+out.id.slice(0,8)+
       "，本次最多使用 14 次付费模型调用；运行结果需人工审核。");
     await refresh(out.id);
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);void checkReadiness(lineId);}
 }
 async function resume(){
   if(!current)return;
   setBusy(true);setError("");
   try{
     await api("scientific-tournaments/"+current.id+"/resume",{method:"POST",body:"{}"});
     await refresh(current.id);setMessage("已从上一已完成阶段继续。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function rate(label:string){
   if(!current)return;
   setBusy(true);setError("");setMessage("");
   try{
     await api("scientific-tournaments/"+current.id+"/ratings",{
       method:"POST",body:JSON.stringify({
         blind_id:label,...(scores[label]||DEFAULT),
         recommendation:recommendations[label]||"investigate",comment:""
       })
     });
     setMessage("已保存 "+label+" 的匿名人工评分；不会自动修改团队画像或选题。");
     await refresh(current.id);
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function curate(){
   if(!current)return;
   setBusy(true);setError("");setMessage("");
   try{
     await api("scientific-tournaments/"+current.id+"/learning",{
       method:"POST",body:JSON.stringify({
         feedback_kind:feedbackKind,finding:finding.trim(),
         supporting_reference:reference.trim(),limitation:limitation.trim()
       })
     });
     setFinding("");setReference("");setLimitation("");
     setMessage("已作为团队审核的经验保存；将进入未来竞赛的冻结输入，不等于外部实证核验。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 const selected=current?.decision?.selected_ids||[];
 return <section className="panel" aria-label="多智能体科研竞赛与回流">
   <div className="panel-header"><div>
     <span className="panel-kicker">MULTI-AGENT TOURNAMENT · PAIRED A/B</span>
     <h2>科研多智能体竞争与对照实验</h2>
   </div><GitBranch size={20}/></div>
   <p className="small muted">A：原四阶段选题链；B：问题、方法、数据三路独立生成 → 交叉反驳 → 修订 → 仲裁。两组使用同一冻结论文与数据目录，最多三轮竞争，不强制达成共识。</p>
   <div className="ai-lab-controls">
     <label>研究主线
       <select value={lineId} onChange={e=>setLineId(e.target.value)}>
         <option value="">选择研究主线</option>
         {lines.map(x=><option key={x.line_id} value={x.line_id}>{x.line_name}</option>)}
       </select>
     </label>
     <label style={{flex:"2 1 320px"}}>本轮科研问题
       <input value={question} maxLength={600} onChange={e=>setQuestion(e.target.value)}
         placeholder="例如：城市空间关系的跨城市外推是否存在未解释的失效机制？"/>
     </label>
     <button className="btn btn-primary" disabled={busy||active||checkingPreflight||!canEdit||
        !modelConfigured||preflight?.ready!==true||!lineId||question.trim().length<10} onClick={()=>void start()}>
       <Play size={15}/> 运行 A/B 竞赛
     </button>
     <button className="btn btn-secondary" disabled={busy} onClick={()=>void refresh(current?.id)}>
       <RefreshCw size={15}/> 刷新
     </button>
   </div>
   <div className="small-note">
     <ShieldCheck size={15}/> <strong>零费用试验前检查：</strong>
     {checkingPreflight?"正在检查":
      preflight?.ready?"已就绪，可以人工启动":
      preflight?"尚未就绪":"请选择研究主线"}
     {preflight&&<span>
       {" · "}持久化存储 {preflight.persistent_database?"PostgreSQL":"未接通"}
       {" · "}已审论文 {preflight.approved_papers}
       {" · "}登记数据 {preflight.registered_datasets}
       {" · "}可用模型调用 {preflight.remaining_model_calls}
       {" · "}剩余预留 Token {preflight.remaining_token_allowance.toLocaleString()}
     </span>}
     {preflight?.notes?.length>0&&
       <p className="small muted">{preflight.notes.join("；")}</p>}
     {preflightError&&<p className="small muted">检查未完成：{preflightError}</p>}
   </div>
   <p className="small muted">只有环境就绪后才可人工启动，最多 14 次模型调用。试验不会定时自动运行，也不会执行原始研究代码。</p>
   {error&&<div className="alert alert-error">{error}</div>}
   {message&&<div className="alert alert-success">{message}</div>}
   {runs.length>0&&<div className="inline-actions" style={{flexWrap:"wrap"}}>
     {runs.slice(0,7).map(r=><button type="button" key={r.id}
       className="btn btn-secondary" onClick={()=>{setShowTrace(false);void refresh(r.id);}}>
       {runStatus[r.status]||r.status} · {r.id.slice(0,8)}
     </button>)}
   </div>}
   {current&&<div className="ai-lab-run-box">
     <div className="ai-lab-run-head"><strong>{current.question}</strong>
       <span>{runStatus[current.status]||current.status} · {current.stage}</span></div>
     <p className="small muted">模型调用 {current.model_calls} 次，
       输入 {current.input_tokens} / 输出 {current.output_tokens} tokens。
       模型给出的创新性判断一律视为未核验。</p>
     {current.error&&<div className="alert alert-error">{current.error}</div>}
     {current.status==="failed"&&canEdit&&
       <button className="btn btn-secondary" disabled={busy} onClick={()=>void resume()}>
         <RotateCcw size={15}/> 从检查点恢复
       </button>}
     {current.status==="completed"&&<>
       <div className="small-note"><ShieldCheck size={15}/>
         建议先完成下面的匿名人工评价，再查看哪组采用了多 Agent。匿名呈现可减少评价偏见，但无法替代独立盲评。
       </div>
       {blind?.cards.map(card=><article className="ai-lab-card" key={card.blind_id}>
         <h3>{card.blind_id}</h3>
         {card.ideas.length===0?<p>此方案没有产生符合条件的候选科研假设。</p>:
           card.ideas.map((idea,i)=><div key={i}>
             <p><b>研究问题：</b>{idea.question}</p>
             <p><b>可证伪预测：</b>{idea.falsifiable_prediction||"待补充"}</p>
             <p><b>研究方法：</b>{idea.method}</p>
             <p><b>最小实验：</b>{idea.minimal_experiment}</p>
             <p><b>基线：</b>{idea.baselines.join("、")}</p>
           </div>)}
         {canEdit&&<div className="ai-lab-controls">
           {scoreNames.map(field=><label key={field.key}>{field.label}
             <select value={(scores[card.blind_id]||DEFAULT)[field.key]}
               onChange={e=>setScores(old=>({
                 ...old,[card.blind_id]:{...(old[card.blind_id]||DEFAULT),
                    [field.key]:Number(e.target.value)}
               }))}>
               {[1,2,3,4,5].map(v=><option key={v} value={v}>{v} / 5</option>)}
             </select>
           </label>)}
           <label>研究建议
             <select value={recommendations[card.blind_id]||"investigate"}
               onChange={e=>setRecommendations(old=>({
                 ...old,[card.blind_id]:e.target.value as "test"|"investigate"|"reject"
               }))}>
               <option value="test">建议小实验</option>
               <option value="investigate">继续检索</option>
               <option value="reject">暂缓</option>
             </select>
           </label>
           <button className="btn btn-secondary" disabled={busy}
             onClick={()=>void rate(card.blind_id)}><Users size={14}/> 保存匿名评价</button>
         </div>}
       </article>)}
       {current.review_unblinded?
       <button className="btn btn-secondary" onClick={()=>setShowTrace(!showTrace)}>
         <BrainCircuit size={15}/>{showTrace?"收起":"显示"}竞争过程与分歧
       </button>:
       <p className="small muted">请先完成方案一和方案二的评分，才能查看 A/B 角色及竞赛详细记录。</p>}
       {current.review_unblinded&&showTrace&&<div className="ai-lab-card">
         <h3>仲裁：{decisions[current.decision?.outcome||""]||"未知"}</h3>
         <p>{current.decision?.reason}</p>
         <p><b>保留假设：</b>{selected.join("、")||"没有可直接推进的假设"}</p>
         <p><b>剩余争议：</b>{current.decision?.unresolved_disagreements.join("；")||"无进一步结构化争议"}</p>
         <p><b>停止原因：</b>{current.decision?.stopping_reason}</p>
         <h3>R0 · 独立研究假设</h3>
         {current.round0.map(x=><p key={x.id}>{x.id} · {x.question}</p>)}
         <h3>R1 · 交叉反驳</h3>
         {current.critiques.map(x=><p key={x.target_id}>{x.target_id} · {x.stance}：
           {x.objections.join("；")}</p>)}
         <h3>R2 · 修订</h3>
         {current.revisions.map(x=><p key={x.id}>{x.id} · {x.question}</p>)}
         <h3>运行阶段</h3>
         <p className="small muted">{current.trace.map(x=>x.stage).join(" → ")}</p>
       </div>}
       {canAdmin&&<div className="ai-lab-card">
         <h3>人工审核后回流到科研记忆</h3>
         <p className="small muted">只有管理员提交的具体经验进入未来竞赛；普通 Agent 自评和匿名得分不会自动写入画像或知识库。</p>
         <label>反馈类型
           <select value={feedbackKind} onChange={e=>setFeedbackKind(e.target.value)}>
             <option value="human_review">人工研究评审</option>
             <option value="experiment_observation">实验观察结果</option>
             <option value="data_availability">数据可得性核查</option>
           </select>
         </label>
         <label>经过团队审核的具体发现
           <textarea value={finding} rows={3} maxLength={900}
              onChange={e=>setFinding(e.target.value)}
              placeholder="例如：外推实验中发现的可复现失败条件；不要只写‘这个选题很好’"/>
         </label>
         <label>证据或实验记录来源
           <input value={reference} maxLength={500}
             onChange={e=>setReference(e.target.value)}
             placeholder="DOI、实验日志编号或团队内部报告 ID"/>
         </label>
         <label>局限性与适用边界
           <textarea value={limitation} rows={2} maxLength={650}
             onChange={e=>setLimitation(e.target.value)}
             placeholder="说明研究尺度、数据质量或尚未验证的条件"/>
         </label>
         <button className="btn btn-secondary" disabled={busy||
           finding.trim().length<12||limitation.trim().length<8}
           onClick={()=>void curate()}><ShieldCheck size={15}/> 审核并回流到下一轮</button>
       </div>}
     </>}
   </div>}
 </section>;
}
