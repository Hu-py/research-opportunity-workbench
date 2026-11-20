"use client";
import Link from "next/link";
import {useCallback,useEffect,useMemo,useState} from "react";
import styles from "./venue-radar.module.css";

type Paper={title:string;url:string;year:number;work_id:string;query:string};
type Evidence={found_in_queries:string[];observed_paper_count:number;distinct_query_count:number;sample_papers:Paper[];search_plan:string;source_provider:string;basis:string};
type Candidate={id:string;name:string;probe_group:string;openalex_source_id:string;source_url:string;issn_l:string;status:string;evidence:Evidence;review_reason:string;quality_label:string;discovered_at:string};
type Entry={id:string;name:string;openalex_source_id:string;probe_group:string;active:boolean;status_note:string;approved_at:string;url:string};
type Run={id:string;status:string;requests_made:number;works_seen:number;proposals_created:number;error_summary:string;created_at:string};
type PaperResult={id:string;title:string;doi:string;url:string;published:string;venue:string;probe_group:string;query:string};
type PaperRun={id:string;status:string;source_ids:Record<string,string[]>;papers:PaperResult[];error_summary:string;created_at:string};
type Radar={title:string;task_key:string;baseline:{name:string;probe_group:string;openalex_source_id:string|null;resolution_status:string;origin:string}[];
 candidates:Candidate[];directory:Entry[];active_source_ids:Record<string,string[]>;runs:Run[];paper_runs:PaperRun[];
 search_plan:Record<string,string[]>;limits:{queries_per_discovery:number;results_per_query:number;llm_calls:number;automated_approval:boolean};note:string};
const GROUPS=[{id:"A",name:"规划应用与健康场景"},{id:"B",name:"城市科学与空间机制"},{id:"C",name:"计算方法与可迁移技术"}];
const STATUS:Record<string,string>={queued:"等待执行",running:"正在检索",completed:"完成",partial:"部分完成",failed:"失败",pending:"等待你审核",approved:"已批准",rejected:"已拒绝"};
const BASE="/api/proxy/personal-research/me/journal-radar";
async function request<T>(path="",method:"GET"|"POST"="GET",body?:unknown):Promise<T>{
 const res=await fetch(BASE+path,{method,cache:"no-store",credentials:"same-origin",
  headers:{"Content-Type":"application/json"},...(body?{body:JSON.stringify(body)}:{})});
 if(!res.ok){const payload=await res.json().catch(()=>({}));
  throw Error(typeof payload.detail==="string"?payload.detail:"请求失败："+res.status);}
 return res.json() as Promise<T>;
}
export default function VenueRadar(){
 const [state,setState]=useState<Radar|null>(null);
 const [filter,setFilter]=useState("all");
 const [notes,setNotes]=useState<Record<string,string>>({});
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 const [success,setSuccess]=useState("");
 const refresh=useCallback(async()=>{
  try{const next=await request<Radar>();setState(next);setError("");}
  catch(e){setError(e instanceof Error?e.message:"无法读取个人任务期刊目录");}
 },[]);
 useEffect(()=>{
  void refresh();
  const timer=setInterval(()=>{void refresh();},10000);
  return()=>clearInterval(timer);
 },[refresh]);
 const candidates=useMemo(()=>state?.candidates.filter(v=>filter==="all"||v.probe_group===filter)||[],[state,filter]);
 const current=state?.runs[0];
 const paperRun=state?.paper_runs[0];
 const unresolved=state?.baseline.filter(x=>!x.openalex_source_id).length||0;
 const active=state?Object.values(state.active_source_ids).reduce((n,list)=>n+list.length,0):0;
 const pending=state?.candidates.filter(x=>x.status==="pending").length||0;
 async function act(fn:()=>Promise<unknown>,message:string){
  if(busy)return;
  setBusy(true);setError("");setSuccess("");
  try{await fn();setSuccess(message);await refresh();}
  catch(e){setError(e instanceof Error?e.message:"操作失败");}
  finally{setBusy(false);}
 }
 function review(c:Candidate,decision:"approve"|"reject"){
  const reason=(notes[c.id]||"").trim();
  if(reason.length<5){setError("请为审核决定填写至少 5 个字的理由");return;}
  void act(()=>request("/candidates/"+encodeURIComponent(c.id)+"/review","POST",{decision,reason}),
   decision==="approve"?"已加入此任务期刊目录，不影响全局来源库。":"已拒绝并保留审核记录。");
 }
 return <main className={styles.root}>
  <div className={styles.shell}>
   <nav className={styles.nav}><Link href="/research/personal">← 我的科研画像</Link><Link href="/devstudio/experiments">Development Studio</Link></nav>
   <header className={styles.header}>
    <div><small>RESEARCH ATLAS / SC03 CHILD HEALTH PILOT</small>
     <h1>儿童健康外推 · 任务期刊目录</h1>
     <p>让系统从研究问题出发发现新期刊。只有你逐项审批后，才会进入本任务可用来源；其他研究主题和全局来源库不受影响。</p></div>
    <button onClick={()=>void refresh()} disabled={busy} type="button">刷新状态</button>
   </header>
   {error&&<div className={styles.error} role="alert">{error}</div>}
   {success&&<div className={styles.success} role="status">{success}</div>}
   <div className={styles.metrics}>
    <div><small>既有任务起点</small><strong>{state?.baseline.length??"—"}</strong><span>来自全局已整理目录</span></div>
    <div><small>待审核新期刊</small><strong>{pending}</strong><span>不自动纳入</span></div>
    <div><small>新增获批来源</small><strong>{state?.directory.filter(x=>x.active).length??0}</strong><span>仅此个人任务</span></div>
    <div><small>可用于严格检索的 ID</small><strong>{active}</strong><span>含已解析起点</span></div>
   </div>
   <section className={styles.panel}>
    <div className={styles.sectionhead}><div><h2>01 · 发现新的候选期刊</h2>
      <p>OpenAlex 按六条检索查询寻找论文，再追踪论文所属期刊；不是根据期刊名字猜测，也不是自动质量排名。</p></div>
      <button className={styles.primary} onClick={()=>void act(()=>request("/discover","POST"),"已记录一次期刊探索请求，结果完成后自动刷新。")}
       disabled={busy||current?.status==="running"||current?.status==="queued"} type="button">
       {current?.status==="running"||current?.status==="queued"?"正在发现期刊…":"运行儿童健康期刊探索"}
      </button>
    </div>
    <div className={styles.queries}>{GROUPS.map(g=><div key={g.id}>
     <strong>{g.id} · {g.name}</strong>
     {(state?.search_plan[g.id]||[]).map(q=><small key={q}>{q}</small>)}
    </div>)}</div>
    <p className={styles.meta}>每次最多 {state?.limits.queries_per_discovery??6} 次 OpenAlex 查询、每次 {state?.limits.results_per_query??40} 条论文；LLM 调用 0 次。OpenAlex API 可能产生少量检索计费，且有额度和访问限制，只有你点击才执行。</p>
    {current&&<div className={styles.status}>
      <strong>最近一次执行：{STATUS[current.status]||current.status}</strong>
      <span>{current.requests_made} 次请求 · 观察到 {current.works_seen} 条论文返回 · 新建候选 {current.proposals_created} 本</span>
      {current.error_summary&&<span className={styles.warn}>{current.error_summary}</span>}
    </div>}
   </section>
   <section className={styles.panel}>
    <div className={styles.sectionhead}><div><h2>02 · 审核 AI 发现的候选期刊</h2>
      <p>每项显示 OpenAlex Source ID、发现依据、代表论文。出现频次只表示检索信号，不代表影响因子、期刊质量或推荐投稿。</p></div>
      <select aria-label="筛选探针" value={filter} onChange={e=>setFilter(e.target.value)}>
       <option value="all">所有探针</option>{GROUPS.map(g=><option key={g.id} value={g.id}>{g.id} · {g.name}</option>)}
      </select>
    </div>
    {!candidates.length&&<div className={styles.empty}>还没有期刊候选。点击上方「运行儿童健康期刊探索」开始真实来源搜索，完成后会在这里出现可审批清单。</div>}
    <div className={styles.candidates}>
    {candidates.map(c=><article key={c.id} className={styles.candidate}>
      <div className={styles.candhead}><div>
        <small>探针 {c.probe_group} · {STATUS[c.status]||c.status}</small>
        <h3>{c.name}</h3>
        <a href={c.source_url} target="_blank" rel="noopener noreferrer">{c.openalex_source_id} · 查看 OpenAlex 来源记录 ↗</a>
      </div><span className={styles.pill}>{c.evidence.observed_paper_count} 篇检索命中</span></div>
      <p className={styles.evidence}>推荐理由：{c.evidence.distinct_query_count} 条不同查询发现相关论文；来源类型为期刊。
       {c.issn_l?" ISSN-L："+c.issn_l+"。":""} 需要进一步核对研究适配度、文献类型和期刊可信度。</p>
      <div className={styles.samples}><strong>来源论文（可核查）</strong>
       {(c.evidence.sample_papers||[]).map(p=><div key={p.work_id}><a target="_blank" rel="noopener noreferrer" href={p.url}>{p.title} ↗</a><small>{p.year||"年份未核实"} · {p.query}</small></div>)}
      </div>
      {c.status==="pending"?<div className={styles.review}>
        <label>审批依据（至少 5 字）<input value={notes[c.id]||""} onChange={e=>setNotes(o=>({...o,[c.id]:e.target.value}))}
          placeholder="例如：多篇研究直接涉及儿童环境暴露与健康，纳入 A 组持续关注"/></label>
        <div className={styles.buttons}>
          <button disabled={busy||(notes[c.id]||"").trim().length<5} className={styles.primary} onClick={()=>review(c,"approve")} type="button">批准加入本任务目录</button>
          <button disabled={busy||(notes[c.id]||"").trim().length<5} onClick={()=>review(c,"reject")} type="button">拒绝</button>
        </div>
      </div>:<p className={styles.reviewed}>审批记录：{c.review_reason||"已审核"}</p>}
    </article>)}
    </div>
   </section>
   <section className={styles.panel}>
    <div className={styles.sectionhead}><div><h2>03 · 本任务生效的期刊目录</h2>
      <p>原始起点与人工批准的新来源分别管理。新来源只有在本任务中生效，可暂停，不同步修改团队全局来源库。</p></div></div>
    <div className={styles.queries}>{GROUPS.map(g=><div key={g.id}><strong>{g.id} · {g.name}</strong>
       {(state?.baseline||[]).filter(x=>x.probe_group===g.id).map(x=><small key={x.name}>{x.name}{!x.openalex_source_id?" · 待解析 OpenAlex ID":""}</small>)}
    </div>)}</div>
    {unresolved>0&&<p className={styles.meta}>既有起点中 {unresolved} 本尚未完成 OpenAlex 精确解析；严格目录内检索只使用已解析或人工批准的 Source ID，不会因解析失败而扩大成全网搜索。</p>}
    <h3 className={styles.smallheading}>新增获批期刊</h3>
    {!state?.directory.length?<p className={styles.empty}>暂无新增获批期刊。审批上面的候选后会自动出现在这里。</p>:<div className={styles.directory}>
      {state.directory.map(e=><div key={e.id} className={styles.entry}>
        <div><strong>{e.name}</strong><small>{e.probe_group} · {e.openalex_source_id} · {e.active?"已启用":"已暂停"}</small></div>
        <button disabled={busy} type="button" onClick={()=>{
          const reason=e.active?"暂时不适用于本任务，暂停期刊检索":"恢复作为本任务已批准的来源";
          void act(()=>request("/directory/"+encodeURIComponent(e.id)+"/status","POST",{action:e.active?"pause":"resume",reason}),
            e.active?"该来源已暂停。":"该来源已恢复。");
        }}>{e.active?"暂停":"恢复"}</button>
      </div>)}
    </div>}
   </section>
   <section className={styles.panel}>
    <div className={styles.sectionhead}><div><h2>04 · 验证新目录能否找到论文</h2>
      <p>冻结当前生效的 Source ID，在批准范围内做一次严格 OpenAlex 检索。这个步骤不调用 LLM，不产生周报结论。</p></div>
      <button type="button" disabled={busy||active===0||paperRun?.status==="running"||paperRun?.status==="queued"}
        onClick={()=>void act(()=>request("/scan-approved","POST"),"已提交严格来源目录验证检索请求。")}>运行目录内论文检索</button>
    </div>
    {active===0&&<p className={styles.meta}>当前没有可用的已解析 Source ID；可以先批准新期刊，或另行完成既有来源 ID 解析。</p>}
    {paperRun&&<div className={styles.status}><strong>最近一次目录验证：{STATUS[paperRun.status]||paperRun.status}</strong><span>返回 {paperRun.papers.length} 篇去重论文</span>{paperRun.error_summary&&<span className={styles.warn}>{paperRun.error_summary}</span>}</div>}
    {paperRun&&paperRun.papers.length>0&&<div className={styles.papers}>{paperRun.papers.slice(0,30).map(p=>
      <p key={p.id}><a href={p.url} target="_blank" rel="noopener noreferrer">{p.title} ↗</a><small>{p.venue} · 探针 {p.probe_group} · {p.published}</small></p>)}</div>}
   </section>
   <p className={styles.disclaimer}>本页为儿童健康外推单任务试验：发现 → 证据 → 人工批准 → 生效目录 → 严格来源检索。下一阶段才接入跨论文 LLM 综合与周报质量评分。</p>
  </div>
 </main>;
}
