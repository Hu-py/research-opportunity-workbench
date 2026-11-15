"use client";
import Link from "next/link";
import {useCallback,useEffect,useState} from "react";
import styles from "./workbench.module.css";

type Baseline={
 research_question:string;study_design:string;existing_methods:string[];
 observations:string[];constraints:string[];validation_goal:string;provenance?:string
};
type Paper={id:string;title:string;group:string;venue:string;url:string;abstract?:string;published?:string};
type Run={id:string;status:string;stage:string;paper_count:number;
 model_calls:number;input_tokens:number;output_tokens:number;error:string;
 snapshot_sha:string;created_at:string;novelty_verified:boolean;
 snapshot?:{baseline:Baseline;baseline_revision:number;source_scan:string;source_ids:Record<string,string[]>;papers:Paper[]};
 readings?:{paper_id:string;problem:string;method:string;validation:string;limitations:string;
 evidence_excerpt:string;source_level:string}[];
 matches?:{method:string;paper_ids:string[];compatibility:string;mechanism:string;assumptions:string[];
 baseline_to_compare:string;failure_risk:string}[];
 variants?:{id:string;title:string;paper_ids:string[];hypothesis:string;baseline_to_beat:string;
 minimal_test:string;data_needed:string[];stop_condition:string;risks:string[];novelty_status:string}[];
 critic?:{variant_id:string;verdict:string;nearest_paper_ids:string[];fatal_issues:string[];
 stop_condition:string;revised_test:string;novelty_status:string}[];
};
type Overview={
 version:string;task:string;
 baseline:{confirmed:boolean;revision:number|null;payload:Baseline;notice:string};
 evidence:{ready:boolean;scan_id:string|null;stats:{total:number;with_abstract:number;groups:string[];selected?:number};
 papers:Paper[];warning:string};
 model:{configured:boolean;vault_ready:boolean;provider:string;fast_model:string;reason_model:string;daily_enabled:boolean};
 budget:{limits:{model_calls_per_day:number;token_reservation_per_day:number};used:{model_calls:number}};
 runs:Run[];
};
type Detail={run:Run;feedback:{id:string;ratings:Record<string,number>;target:string;decision:string;comment:string;created_at:string}[]};
const ROOT="/api/proxy/personal-research/me/evolution";
async function request<T>(path="",method:"GET"|"PUT"|"POST"="GET",body?:unknown):Promise<T>{
 const response=await fetch(ROOT+path,{method,cache:"no-store",credentials:"same-origin",
   headers:{"Content-Type":"application/json"},
   ...(body!==undefined?{body:JSON.stringify(body)}:{})});
 if(!response.ok){
   const data=await response.json().catch(()=>({}));
   throw Error(typeof data.detail==="string"?data.detail:"后端暂时不可用（"+response.status+"）");
 }
 return response.json() as Promise<T>;
}
function lines(v:string[]|undefined){return (v||[]).join("\n");}
const statusLabel:Record<string,string>={prepared:"证据已准备",queued:"模型任务排队",running:"模型正在处理",
 completed:"机器分析已完成 · 待你审核",failed:"执行失败"};
const stageLabel:Record<string,string>={reader:"论文理解",transfer:"方法匹配与变体生成",critic:"独立反证审查",done:"全部机器阶段完成"};
const verdict:Record<string,string>={test:"可作小规模测试",hold:"应暂缓、先补证据",reject:"建议淘汰"};
const qualityTargets=[["paper_accuracy","论文理解准确性"],["method_fit","方法迁移适配性"],
 ["novelty_caution","创新性审慎程度"],["experiment_feasibility","实验可行性"],["usefulness","对研究推进的价值"]] as const;
export default function Workbench(){
 const [data,setData]=useState<Overview|null>(null);
 const [form,setForm]=useState<Baseline|null>(null);
 const [selected,setSelected]=useState("");
 const [detail,setDetail]=useState<Detail|null>(null);
 const [editing,setEditing]=useState(false);
 const [consent,setConsent]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [ok,setOk]=useState("");
 const [scores,setScores]=useState<Record<string,number>>({
   paper_accuracy:3,method_fit:3,novelty_caution:3,experiment_feasibility:3,usefulness:3,
 });
 const [focus,setFocus]=useState("reader");
 const [decision,setDecision]=useState("revise");
 const [comment,setComment]=useState("");
 const refresh=useCallback(async()=>{
  try{
   const overview=await request<Overview>();
   setData(overview);
   setForm(current=>current||overview.baseline.payload);
   setSelected(current=>current||overview.runs[0]?.id||"");
  }catch(e){setError(e instanceof Error?e.message:"请求失败");}
 },[]);
 useEffect(()=>{void refresh();const timer=setInterval(()=>void refresh(),15000);return()=>clearInterval(timer)},[refresh]);
 useEffect(()=>{
  if(!selected){setDetail(null);return;}
  const load=async()=>{try{setDetail(await request<Detail>("/runs/"+encodeURIComponent(selected)));}
  catch(e){setError(e instanceof Error?e.message:"详情读取失败")}};
  void load();const timer=setInterval(()=>void load(),15000);return()=>clearInterval(timer);
 },[selected,data?.runs.map(x=>x.status+":"+x.stage).join("|")]);
 async function act(fn:()=>Promise<unknown>,message:string){
  if(busy)return;
  setError("");setOk("");setBusy(true);
  try{await fn();setOk(message);await refresh();
   if(selected){setDetail(await request<Detail>("/runs/"+encodeURIComponent(selected)));}
  }catch(e){setError(e instanceof Error?e.message:"操作失败");}
  finally{setBusy(false)}
 }
 const active=data?.runs.find(x=>x.id===selected);
 const loaded=detail?.run&&detail.run.id===selected?detail.run:undefined;
 const ready=data?.evidence.ready||false;
 const aiReady=Boolean(data?.model.configured&&data?.model.vault_ready);
 const isRunning=active?.status==="queued"||active?.status==="running";
 const baseForm=form||data?.baseline.payload;
 const setField=(k:keyof Baseline,v:string)=>setForm(p=>p?{...p,[k]:v}:p);
 const setArray=(k:"existing_methods"|"observations"|"constraints",v:string)=>
   setForm(p=>p?{...p,[k]:v.split("\n").map(x=>x.trim()).filter(Boolean)}:p);
 const saveBaseline=()=>act(async()=>{
   if(!form)return;
   await request("/baseline","PUT",{...form,confirmed:true});
   setEditing(false);
 },"研究基准已由当前账号确认并保存，可用于独立版本实验。");
 const prep=()=>act(async()=>{
   const result=await request<Run>("/prepare","POST",{});
   setSelected(result.id);
   setDetail(await request<Detail>("/runs/"+encodeURIComponent(result.id)));
 },"已冻结真实论文与研究基准，尚未调用付费模型。");
 const runModel=(resume:boolean)=>act(async()=>{
   if(!selected)throw Error("没有选择具体实验");
   await request("/runs/"+encodeURIComponent(selected)+(resume?"/resume":"/start"),
      "POST",{acknowledge_external_model:consent});
 },"已提交模型分析请求；系统将分阶段保存原始论文理解、变体与反证。");
 const submitFeedback=()=>act(async()=>{
   if(!selected)throw Error("没有选择实验");
   if(comment.trim().length<8)throw Error("请至少填写8个字的具体修改反馈");
   await request("/runs/"+encodeURIComponent(selected)+"/review","POST",{
     ...scores,target:focus,decision,comment:comment.trim(),
   });
   setComment("");
 },"已把这轮学术评价保存到你的个人实验记录，不会自动修改团队标准。");
 return <main className={styles.root}><div className={styles.shell}>
  <nav className={styles.nav}><Link href="/research/personal">← 我的科研画像</Link>
   <Link href="/research/personal/journals">儿童健康期刊目录</Link>
   <Link href="/devstudio/experiments">Development Studio</Link></nav>
  <header className={styles.header}>
    <small>RESEARCH ATLAS / SC04 · EVOLUTION PILOT</small>
    <h1>儿童健康外推 · 研究演化实验</h1>
    <p>从已有研究出发，理解真实论文摘要，比较方法适用条件，提出最多3个可证伪变体并进行反证审查。所有机器结论都需要研究者审核。</p>
  </header>
  {error&&<div className={styles.error} role="alert">{error}</div>}
  {ok&&<div className={styles.success} role="status">{ok}</div>}
  <div className={styles.metrics}>
    <div><small>研究基准</small><strong>{data?.baseline.confirmed?"已确认":"待确认"}</strong><span>由本人维护</span></div>
    <div><small>真实摘要准备</small><strong>{data?.evidence.stats.selected||0} 篇</strong><span>至少3篇 / 两类探针</span></div>
    <div><small>模型凭据</small><strong>{aiReady?"已配置":"未配置"}</strong><span>不会自动发起收费调用</span></div>
    <div><small>个人实验记录</small><strong>{data?.runs.length??"—"} 次</strong><span>每轮冻结输入与版本</span></div>
  </div>
  <section className={styles.panel}>
   <div className={styles.sectionHeading}><div><h2>01 · 已有研究基准档案</h2>
     <p>请先核对研究内容、强基线及验证限制。初始内容来自此前对话，并非实验原始结果。</p></div>
     {!editing&&<button type="button" onClick={()=>setEditing(true)}>{data?.baseline.confirmed?"编辑新修订":"核对并确认"}</button>}
   </div>
   {baseForm&&(editing||!data?.baseline.confirmed?
   <div className={styles.formGrid}>
     <label>研究问题<textarea rows={2} value={baseForm.research_question} onChange={e=>setField("research_question",e.target.value)}/></label>
     <label>数据与现有研究设计<textarea rows={3} value={baseForm.study_design} onChange={e=>setField("study_design",e.target.value)}/></label>
     <label>已测试的方法 / 基线（每行一项）<textarea rows={4} value={lines(baseForm.existing_methods)} onChange={e=>setArray("existing_methods",e.target.value)}/></label>
     <label>已有观察（每行一项）<textarea rows={4} value={lines(baseForm.observations)} onChange={e=>setArray("observations",e.target.value)}/></label>
     <label>不可忽视的条件（每行一项）<textarea rows={4} value={lines(baseForm.constraints)} onChange={e=>setArray("constraints",e.target.value)}/></label>
     <label>真正需要验证的目标<textarea rows={2} value={baseForm.validation_goal} onChange={e=>setField("validation_goal",e.target.value)}/></label>
     <div className={styles.actions}><button className={styles.primary} disabled={busy} onClick={saveBaseline}>确认并保存为个人研究基准</button>
      {data?.baseline.confirmed&&<button onClick={()=>{setEditing(false);setForm(data.baseline.payload)}}>取消</button>}</div>
   </div>:<div className={styles.baseline}>
     <h3>{baseForm.research_question}</h3><p>{baseForm.study_design}</p>
     <div className={styles.twoCols}><div><strong>已有基线</strong>{baseForm.existing_methods.map(x=><p key={x}>{x}</p>)}</div>
      <div><strong>关键研究限制</strong>{baseForm.constraints.map(x=><p key={x}>{x}</p>)}</div></div>
     <p><strong>验证目标：</strong>{baseForm.validation_goal}</p>
     <small>当前确认版本：v{data?.baseline.revision}</small>
   </div>)}
  </section>
  <section className={styles.panel}>
   <div className={styles.sectionHeading}><div><h2>02 · 准备论文理解证据</h2>
    <p>只从你已批准的任务期刊目录内检索记录取论文；本页不会偷偷扩大检索范围。</p></div>
    <button disabled={busy||!data?.baseline.confirmed||!ready||isRunning} className={styles.primary}
      onClick={prep}>冻结论文并创建实验（无模型费用）</button>
   </div>
   <div className={styles.note}>最近一次严格来源扫描：{data?.evidence.scan_id||"暂无"} ·
     共 {data?.evidence.stats.total||0} 篇 · 有足够摘要 {data?.evidence.stats.with_abstract||0} 篇 ·
     覆盖探针 {(data?.evidence.stats.groups||[]).join("/")||"无"}</div>
   {!ready&&<div className={styles.warning}>
      <strong>真实论文证据尚未达到实验门槛。</strong>
      <p>请先进入「儿童健康期刊目录」，批准需要的期刊，并点击最下方的「运行目录内论文检索」。返回此页后才可以运行真实模型理解。</p>
      <Link href="/research/personal/journals">进入期刊目录与严格论文检索 →</Link>
    </div>}
   <div className={styles.paperRows}>{(data?.evidence.papers||[]).map(p=><div key={p.id}>
     <span className={styles.pill}>探针 {p.group}</span>
     <div><a href={p.url} target="_blank" rel="noopener noreferrer">{p.title} ↗</a><small>{p.venue} · {p.id}</small></div>
   </div>)}</div>
   <p className={styles.fineprint}>{data?.evidence.warning}</p>
  </section>
  <section className={styles.panel}>
    <div className={styles.sectionHeading}><div><h2>03 · 运行三阶段科研智能体</h2>
      <p>论文理解 → 方法匹配和研究变体 → 独立反证审查。每轮快照、Token 与错误都记录到数据库。</p></div>
      <button type="button" onClick={()=>void refresh()} disabled={busy}>刷新</button>
    </div>
    <div className={styles.runList}>
     {(data?.runs||[]).map(r=><button type="button" key={r.id}
       className={selected===r.id?styles.selected:""} onClick={()=>setSelected(r.id)}>
       <span>{r.id.slice(0,19)}…</span><strong>{statusLabel[r.status]||r.status}</strong>
       <small>{r.paper_count} 篇 · {r.model_calls} 次模型调用</small></button>)}
     {!(data?.runs||[]).length&&<div className={styles.empty}>暂无实验。先确认基准并准备真实论文证据。</div>}
    </div>
    {active&&<div className={styles.runState}>
      <div><strong>{statusLabel[active.status]||active.status}</strong>
       <span>当前阶段：{stageLabel[active.stage]||active.stage}</span>
       <small>调用 {active.model_calls} 次 · 输入 {active.input_tokens} / 输出 {active.output_tokens} tokens</small></div>
      {active.error&&<p className={styles.error}>{active.error}</p>}
      {(active.status==="prepared"||active.status==="failed")&&<div className={styles.control}>
       <label><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>
         我同意本轮将确认过的研究基准和公开论文摘要发送到平台已配置的模型服务进行分析。</label>
       {!aiReady&&<p className={styles.warning}>当前测试后端没有可用的 DeepSeek 模型密钥或加密服务。
         请先由 Owner 在模型配置后台启用。未配置时无法执行真实的 LLM 推理。</p>}
       <button disabled={!consent||!aiReady||busy} className={styles.primary} type="button"
        onClick={()=>runModel(active.status==="failed")}>{active.status==="failed"?"从失败阶段继续":"启动 LLM 论文理解与研究变体"}</button>
      </div>}
    </div>}
    {loaded&&(loaded.readings||[]).length>0&&<div className={styles.output}>
      <h3>论文理解 · 摘要级证据 <span className={styles.pill}>模型抽取 · 待审核</span></h3>
      {(loaded.readings||[]).map(r=><article key={r.paper_id}>
       <a href={loaded.snapshot?.papers.find(p=>p.id===r.paper_id)?.url} target="_blank" rel="noopener noreferrer">
         {loaded.snapshot?.papers.find(p=>p.id===r.paper_id)?.title||r.paper_id} ↗</a>
       <p><strong>研究问题：</strong>{r.problem}</p><p><strong>方法：</strong>{r.method}</p>
       <p><strong>验证设计：</strong>{r.validation}</p><p><strong>局限：</strong>{r.limitations}</p>
       <blockquote>摘要定位片段：{r.evidence_excerpt}</blockquote>
      </article>)}
    </div>}
    {loaded&&(loaded.matches||[]).length>0&&<div className={styles.output}>
      <h3>方法迁移适配性</h3>
      <div className={styles.twoCols}>{(loaded.matches||[]).map(m=><article key={m.method}>
        <span className={styles.pill}>{m.compatibility}</span><h4>{m.method}</h4>
        <p>{m.mechanism}</p><p><strong>比较基线：</strong>{m.baseline_to_compare}</p>
        <p><strong>主要风险：</strong>{m.failure_risk}</p>
        <small>论文依据：{m.paper_ids.join(" · ")}</small>
      </article>)}</div>
    </div>}
    {loaded&&(loaded.variants||[]).length>0&&<div className={styles.output}>
      <h3>研究变体 · 待实验验证</h3>
      {(loaded.variants||[]).map(v=><article key={v.id}>
        <h4>{v.id} · {v.title}</h4><p><strong>可证伪假设：</strong>{v.hypothesis}</p>
        <p><strong>需要击败：</strong>{v.baseline_to_beat}</p>
        <p><strong>最小实验：</strong>{v.minimal_test}</p>
        <p><strong>停止条件：</strong>{v.stop_condition}</p>
        <p><strong>新数据要求：</strong>{v.data_needed.join("；")}</p>
        <small>支持论文：{v.paper_ids.join(" · ")} · 创新性未验证</small>
        {(loaded.critic||[]).filter(c=>c.variant_id===v.id).map(c=><div className={styles.critique} key={c.variant_id}>
          <strong>独立反证：{verdict[c.verdict]||c.verdict}</strong>
          <p>{c.fatal_issues.join("；")}</p><p>调整实验：{c.revised_test}</p>
          <small>最近先例仅来自本批论文，未系统查新</small>
        </div>)}
      </article>)}
    </div>}
  </section>
  {loaded?.status==="completed"&&<section className={styles.panel}>
    <div className={styles.sectionHeading}><div><h2>04 · 你的学术质量评价</h2><p>评价用于定位 Skill / Prompt / 检索 / 审查问题，记录到个人实验，不自动改变全局规则。</p></div></div>
    <div className={styles.twoCols}>{qualityTargets.map(([key,name])=><label key={key} className={styles.score}>
     <span>{name}</span><select value={scores[key]} onChange={e=>setScores(s=>({...s,[key]:Number(e.target.value)}))}>
       {[1,2,3,4,5].map(n=><option key={n} value={n}>{n} / 5</option>)}</select></label>)}</div>
    <div className={styles.twoCols}>
     <label className={styles.score}><span>主要改进环节</span><select value={focus} onChange={e=>setFocus(e.target.value)}>
       <option value="retrieval">论文检索</option><option value="reader">论文理解</option>
       <option value="transfer">方法迁移</option><option value="critic">创新性审查</option>
       <option value="experiment">实验方案</option></select></label>
     <label className={styles.score}><span>评价决策</span><select value={decision} onChange={e=>setDecision(e.target.value)}>
       <option value="keep">保留方向</option><option value="revise">修改后再试</option>
       <option value="reject">否决方向</option></select></label>
    </div>
    <label className={styles.feedback}>具体反馈<textarea rows={4} value={comment} onChange={e=>setComment(e.target.value)}
       placeholder="请具体说明：哪篇论文理解错误、哪些方法不适配、哪种变体值得保留，为什么？"/></label>
    <button disabled={busy||comment.trim().length<8} className={styles.primary} onClick={submitFeedback}>保存本轮质量评价</button>
    {(detail?.feedback||[]).map(f=><div className={styles.feedbackItem} key={f.id}>
       <strong>{f.decision} · {f.target}</strong><p>{f.comment}</p>
       <small>{f.created_at.slice(0,19)} · {Object.values(f.ratings).join("/")} 分</small></div>)}
  </section>}
  <p className={styles.footer}>这是 SC04 第一轮研究演化测试：所有科研结论均为待验证假设；自动执行完成不等于论文正确、方法有效或创新性成立。</p>
 </div></main>;
}