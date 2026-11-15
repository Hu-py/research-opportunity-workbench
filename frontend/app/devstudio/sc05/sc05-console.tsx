"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import styles from "./sc05.module.css";

type CaseRow={id:string;title:string;sha256:string;source_type:string;pages:number;shared_evidence_ready:boolean;created_at:string};
type RunRow={id:string;case_id:string;pair_id:string;variant:string;status:string;stage:string;pipeline_sha:string;
  model_calls:number;input_tokens:number;output_tokens:number;error:string;created_at:string;report_md?:string;quality?:Record<string,unknown>};
type Budget={utc_day:string;limits:{model_calls_per_day:number;token_reservation_per_day:number};used:{
  model_calls:number;token_reservation:number;input_tokens:number;output_tokens:number}};
type Overview={version:string;cases:CaseRow[];runs:RunRow[];budget:Budget;key_available:boolean};
type BlindReport={label:string;run_id:string;report_md:string};
type BlindPayload={ready:boolean;pair_id:string;blind_reports?:BlindReport[];statuses?:string[]};
type Repair={ready:boolean;requires_migration?:boolean;reason?:string;replay_prompt_matches?:boolean;
  saved_facts?:number;normalized_types?:{raw_type:string;normalized_type:string}[];saved_checkpoints?:number};
type RatingKey="accuracy"|"science_value"|"narrative"|"literature"|"feasibility";
type RatingForm={accuracy:number;science_value:number;narrative:number;literature:number;
  feasibility:number;hard_failure:boolean;feedback:string;failure_tags:string[]};

const ENDPOINT="/api/proxy/personal-research/me/sc05";
const defaults:RatingForm={accuracy:3,science_value:3,narrative:3,literature:3,
  feasibility:3,hard_failure:false,feedback:"",failure_tags:[]};
const categories:{key:RatingKey;label:string;weight:number}[]=[
  {key:"accuracy",label:"原论文理解与证据忠实度",weight:15},
  {key:"science_value",label:"独立科学问题价值",weight:30},
  {key:"narrative",label:"机制解释与完整研究故事",weight:25},
  {key:"literature",label:"跨领域文献深度",weight:20},
  {key:"feasibility",label:"实验的可区分性与实施可行性",weight:10},
];
const failures=[
  ["paper_understanding","论文理解不足"],["science_value","只补实验、缺少新问题"],
  ["mechanism_narrative","没有机制或完整故事"],["literature_depth","检索肤浅/已有相同研究"],
  ["feasibility","不可实施或不可证伪"],["citation_error","引用或证据不真实"],
] as const;
const stateName=(s:string)=>({
  prepared:"待运行",queued:"排队中",running:"运行中",failed:"运行失败",completed:"已完成",
} as Record<string,string>)[s]||s;
const date=(v?:string)=>v?new Date(v).toLocaleString("zh-CN"):"—";

async function api<T>(path:string,method="GET",payload?:unknown):Promise<T> {
  const res=await fetch(ENDPOINT+path,{
    method,credentials:"same-origin",cache:"no-store",
    headers:{"Content-Type":"application/json"},
    ...(payload===undefined?{}:{body:JSON.stringify(payload)}),
  });
  const data=await res.json().catch(()=>({})) as {detail?:string};
  if(!res.ok)throw new Error(typeof data.detail==="string"?data.detail:
    "请求失败（HTTP "+res.status+"）");
  return data as T;
}
function download(name:string,content:string,kind="text/markdown;charset=utf-8") {
  const url=URL.createObjectURL(new Blob([content],{type:kind}));
  const link=document.createElement("a");
  link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();
  URL.revokeObjectURL(url);
}

export default function SC05Console(){
  const [data,setData]=useState<Overview|null>(null);
  const [caseId,setCaseId]=useState("");
  const [pairId,setPairId]=useState("");
  const [file,setFile]=useState<File|null>(null);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState("");
  const [error,setError]=useState("");
  const [info,setInfo]=useState("");
  const [approvedCost,setApprovedCost]=useState(false);
  const [repair,setRepair]=useState<Record<string,Repair>>({});
  const [details,setDetails]=useState<Record<string,RunRow>>({});
  const [blind,setBlind]=useState<BlindPayload|null>(null);
  const [ratings,setRatings]=useState<Record<string,RatingForm>>({});
  const [rated,setRated]=useState<Record<string,boolean>>({});
  const [comparison,setComparison]=useState<Record<string,unknown>|null>(null);
  const [activeReport,setActiveReport]=useState("");
  const refresh=useCallback(async()=>{
    try{
      const res=await api<Overview>("");
      setData(res);
      setCaseId(old=>res.cases.some(x=>x.id===old)?old:(res.cases[0]?.id||""));
      const ids=[...new Set(res.runs.map(r=>r.pair_id))];
      setPairId(old=>ids.includes(old)?old:(ids[0]||""));
      setError("");
    }catch(e){setError(e instanceof Error?e.message:"连接测试后端失败");}
    finally{setLoading(false);}
  },[]);
  useEffect(()=>{void refresh();},[refresh]);
  useEffect(()=>{
    if(!data?.runs.some(r=>["running","queued"].includes(r.status)))return;
    const timer=setInterval(()=>void refresh(),9000);
    return ()=>clearInterval(timer);
  },[data?.runs,refresh]);

  const cases=data?.cases||[];
  const pairs=useMemo(()=>{
    const map=new Map<string,RunRow[]>();
    for(const run of data?.runs||[]){
      map.set(run.pair_id,[...(map.get(run.pair_id)||[]),run]);
    }
    return [...map.entries()].map(([id,runs])=>({id,runs,
      title:cases.find(c=>c.id===runs[0]?.case_id)?.title||"科研论文 A/B 测试",
      created:runs[0]?.created_at||""}));
  },[data,cases]);
  const pair=pairs.find(x=>x.id===pairId);
  const chosenCase=cases.find(x=>x.id===caseId);
  const pairRuns=(pair?.runs||[]).slice().sort((a,b)=>
    (a.variant==="science_gate_off"?0:1)-(b.variant==="science_gate_off"?0:1));

  const upload=async(e:FormEvent)=>{
    e.preventDefault();
    if(!file)return;
    setBusy("upload");setError("");setInfo("");
    try{
      if(file.size>4_000_000)throw new Error(
        "网页上传目前支持不超过 4 MB 的 PDF。已入库的论文无需重复上传。");
      const res=await fetch("/api/sc05/pdf",{
        method:"POST",cache:"no-store",credentials:"same-origin",
        headers:{"Content-Type":"application/pdf","X-Paper-Title":file.name.replace(/\.pdf$/i,"")},
        body:file,
      });
      const body=await res.json().catch(()=>({})) as {id?:string;detail?:string};
      if(!res.ok||!body.id)throw new Error(body.detail||"论文上传失败");
      const pair=await api<{pair_id:string}>("/cases/"+encodeURIComponent(body.id)+"/ab","POST");
      setInfo("论文已保存到私有实验库，并建立 A/B 对照（尚未调用 DeepSeek）。");
      setCaseId(body.id);setPairId(pair.pair_id);setFile(null);
      await refresh();
    }catch(e){setError(e instanceof Error?e.message:"论文上传失败");}
    finally{setBusy("");}
  };

  const newPair=async()=>{
    if(!caseId)return;
    setBusy("create");setError("");setInfo("");
    try{
      const res=await api<{pair_id:string}>("/cases/"+encodeURIComponent(caseId)+"/ab","POST");
      setInfo("A/B 实验已创建，此时没有任何 DeepSeek 费用。");
      await refresh();setPairId(res.pair_id);
      setRepair({});setBlind(null);setComparison(null);
    }catch(e){setError(e instanceof Error?e.message:"创建实验失败");}
    finally{setBusy("");}
  };

  const checkRepair=async(runId:string)=>{
    setBusy("check-"+runId);setError("");setInfo("");
    try{
      const res=await api<Repair>("/runs/"+encodeURIComponent(runId)+"/repair-check");
      setRepair(p=>({...p,[runId]:res}));
      setInfo(res.ready?
        "检查点已经通过只读恢复检查；恢复时只需对后续未执行的模型步骤付费。":
        "不能安全复用旧检查点：需要先修复该失败原因。");
    }catch(e){setError(e instanceof Error?e.message:"恢复检查失败");}
    finally{setBusy("");}
  };

  const start=async(run:RunRow)=>{
    setError("");setInfo("");
    if(!approvedCost){setError("请先勾选「同意本次真实 DeepSeek 费用」。");return;}
    if(run.status==="failed"&&repair[run.id]?.ready!==true){
      setError("先点击「检查可恢复性」，确认可以安全续跑。");return;
    }
    if(!window.confirm("确认从服务器执行 "+run.id+"？\n\n这是实际 DeepSeek 付费调用，受到当日请求/Token 预算限制。\n已有的成功检查点会尝试复用，不保证未执行的后续步骤免费。"))return;
    setBusy("start-"+run.id);
    try{
      await api("/runs/"+encodeURIComponent(run.id)+"/start","POST",
        {acknowledge_external_model:true});
      setApprovedCost(false);
      setInfo("已提交服务器执行。你可以关闭本页，之后登录查看已保存的进度和结果；若后台服务重启，需检查任务状态。");
      await refresh();
    }catch(e){setError(e instanceof Error?e.message:"提交执行失败");}
    finally{setBusy("");}
  };

  const showRun=async(runId:string)=>{
    setBusy("view-"+runId);setError("");
    try{
      const res=await api<RunRow>("/runs/"+encodeURIComponent(runId));
      setDetails(prev=>({...prev,[runId]:res}));
      setActiveReport(runId);
    }catch(e){setError(e instanceof Error?e.message:"读取报告失败");}
    finally{setBusy("");}
  };

  const exportAudit=async(runId:string)=>{
    setBusy("audit-"+runId);setError("");
    try{
      const res=await api<Record<string,unknown>>("/runs/"+encodeURIComponent(runId)+"/audit");
      download(runId+"_audit.json",JSON.stringify(res,null,2),"application/json;charset=utf-8");
      setInfo("审计 JSON 已下载；包含私有论文摘录和原始模型结果，请勿公开上传。");
    }catch(e){setError(e instanceof Error?e.message:"读取审计记录失败");}
    finally{setBusy("");}
  };

  const loadBlind=async()=>{
    if(!pairId)return;
    setBusy("blind");setError("");setInfo("");
    try{
      const res=await api<BlindPayload>("/pairs/"+encodeURIComponent(pairId)+"/blind");
      setBlind(res);setComparison(null);
      if(!res.ready)setInfo("需等两组真实推理都完成后才能进行盲评。");
    }catch(e){setError(e instanceof Error?e.message:"读取盲评报告失败");}
    finally{setBusy("");}
  };
  const rating=(id:string)=>ratings[id]||{...defaults,failure_tags:[]};
  const editRating=(id:string,patch:Partial<RatingForm>)=>{
    setRatings(old=>({...old,[id]:{...rating(id),...patch}}));
  };
  const review=async(e:FormEvent,rep:BlindReport)=>{
    e.preventDefault();
    const value=rating(rep.run_id);
    if(!window.confirm("提交匿名报告 "+rep.label+" 的科研质量评分？提交后不能覆盖已有评价。"))return;
    setBusy("review-"+rep.run_id);setError("");
    try{
      await api("/runs/"+encodeURIComponent(rep.run_id)+"/review","POST",value);
      setRated(prev=>({...prev,[rep.run_id]:true}));
      setInfo("已保存匿名评价。两份报告都评分后可以查看 A/B 效果差异。");
    }catch(e){setError(e instanceof Error?e.message:"评分保存失败；若已经评分，请直接尝试查看对照");}
    finally{setBusy("");}
  };

  const compare=async()=>{
    if(!pairId)return;
    setBusy("compare");setError("");
    try{
      const result=await api<Record<string,unknown>>("/pairs/"+encodeURIComponent(pairId)+"/comparison");
      setComparison(result);
    }catch(e){setError(e instanceof Error?e.message:"需先为两份报告完成评分");}
    finally{setBusy("");}
  };

  return <main className={styles.page}>
    <header className={styles.top}>
      <div>
        <a href="/devstudio/experiments" className={styles.back}>Development Studio / 实验管理</a>
        <h1>SC05 · 智能体科研能力测评</h1>
        <p>一篇论文，一次上传；实验、原始模型响应、论文证据、报告及评价统一保存在私有研究后台。</p>
      </div>
      <div className={styles.topActions}>
        <span className={styles.owner}>Owner only</span>
        <button type="button" onClick={()=>void refresh()} disabled={loading||Boolean(busy)} className={styles.secondary}>刷新状态</button>
      </div>
    </header>
    {error&&<p role="alert" className={styles.error}>{error}</p>}
    {info&&<p role="status" className={styles.info}>{info}</p>}
    {loading?<p className={styles.muted}>正在读取你的私有科研实验库...</p>:
      !data?<p className={styles.muted}>未连接到研究后台。请先检查 Owner 登录状态。</p>:<>
      <section className={styles.summary}>
        <article><small>已入库论文</small><strong>{cases.length}</strong></article>
        <article><small>已建立 A/B 测试</small><strong>{pairs.length}</strong></article>
        <article><small>今日模型请求</small><strong>{data.budget.used.model_calls} / {data.budget.limits.model_calls_per_day}</strong></article>
        <article><small>今日预留 Token</small><strong>{data.budget.used.token_reservation.toLocaleString()}</strong></article>
      </section>
      <div className={styles.grid}>
        <section className={styles.panel}>
          <h2>论文库</h2>
          <p className={styles.muted}>已在数据库中的论文无需再次上传。完整 PDF 不会写入 GitHub；后台保存可追溯的源文本、哈希与实验关联。</p>
          <div className={styles.caseList}>
            {cases.length===0?<p className={styles.muted}>暂无论文记录</p>:cases.map(c=><button type="button" key={c.id}
              className={styles.caseItem+(c.id===caseId?" "+styles.selected:"")}
              onClick={()=>setCaseId(c.id)}>
              <strong>{c.title}</strong><small>{c.pages} 页 · {c.sha256.slice(0,16)}…</small>
              <small>{c.shared_evidence_ready?"已冻结事实证据":"尚未生成共享证据"} · {date(c.created_at)}</small>
            </button>)}
          </div>
          <form className={styles.upload} onSubmit={upload}>
            <label htmlFor="sc05-file">新增论文 PDF</label>
            <input id="sc05-file" type="file" accept=".pdf,application/pdf"
              onChange={e=>setFile(e.target.files?.[0]||null)}/>
            <small>网页上传暂限 4 MB。现有郑州论文已入库，可以直接选中使用。</small>
            <button type="submit" className={styles.secondary} disabled={!file||Boolean(busy)}>
              {busy==="upload"?"上传中...":"上传并创建 A/B 实验（免费）"}
            </button>
          </form>
          <div className={styles.actions}>
            <button type="button" className={styles.primary} disabled={!chosenCase||Boolean(busy)}
              onClick={()=>void newPair()}>{busy==="create"?"创建中...":"为选中论文建立新的 A/B"}</button>
          </div>
        </section>
        <section className={styles.panel}>
          <h2>实验记录</h2>
          <p className={styles.muted}>从数据库选择之前创建的实验，查看失败状态、恢复检查和新结果。</p>
          {pairs.length===0?<p className={styles.muted}>暂无实验</p>:<div className={styles.pairList}>
            {pairs.map(p=><button key={p.id} type="button"
              className={styles.pairItem+(p.id===pairId?" "+styles.selected:"")}
              onClick={()=>{setPairId(p.id);setBlind(null);setComparison(null);setActiveReport("");}}>
              <strong>{p.title}</strong>
              <small>{p.id}</small>
              <span>{p.runs.map(r=>stateName(r.status)).join(" · ")}</span>
            </button>)}
          </div>}
          <p className={styles.storage}>数据位置：Render 私有 PostgreSQL。报告和检查点不用保存到你的 Mac 才能在网页中再次查看。</p>
        </section>
      </div>
      {pair&&<section className={styles.panel}>
        <div className={styles.sectionHead}>
          <div><h2>当前 A/B 测评</h2><p className={styles.muted}>{pair.id} · {pair.title}</p></div>
          <button type="button" className={styles.secondary} onClick={()=>void refresh()}>刷新进度</button>
        </div>
        <div className={styles.consent}>
          <label><input type="checkbox" checked={approvedCost}
            onChange={e=>setApprovedCost(e.target.checked)}/>
            <strong>我同意此次执行使用 DeepSeek 付费模型。</strong></label>
          <small>不勾选不会发生模型调用。已有成功阶段尽量从检查点恢复；每日预算限制仍生效。</small>
        </div>
        <div className={styles.runs}>
          {pairRuns.map((run,i)=>{
            const r=repair[run.id];
            const canStart=run.status==="prepared" ||
              (run.status==="failed"&&r?.ready===true);
            const other=pairRuns.find(x=>x.id!==run.id);
            const needsEvidence=run.variant==="science_gate_on"&&
              other?.status!=="completed";
            return <article className={styles.run} key={run.id}>
              <div className={styles.sectionHead}>
                <div><h3>{run.variant==="science_gate_off"?"配置 A · 基线推理":"配置 B · 科学价值筛选"}</h3>
                  <code>{run.id}</code></div>
                <span className={styles.status} data-status={run.status}>{stateName(run.status)}</span>
              </div>
              <div className={styles.meta}>
                <span>阶段：{run.stage}</span>
                <span>已调用：{run.model_calls} 次</span>
                <span>输入 / 输出 Token：{run.input_tokens} / {run.output_tokens}</span>
              </div>
              {run.error&&<p className={styles.error}>运行错误：{run.error}</p>}
              {r&&<div className={r.ready?styles.info:styles.error}>
                {r.ready?"检查点可复用":"尚未通过安全恢复检查"}
                {r.requires_migration?" · 涉及版本迁移":""}
                {r.saved_facts!==undefined?" · 已核验事实 "+r.saved_facts+" 条":""}
                {r.reason?" · "+r.reason:""}
              </div>}
              <div className={styles.actions}>
                {run.status==="failed"&&<button type="button" className={styles.secondary}
                  disabled={Boolean(busy)} onClick={()=>void checkRepair(run.id)}>
                  {busy==="check-"+run.id?"检查中...":"检查可恢复性（不扣费）"}
                </button>}
                {["prepared","failed"].includes(run.status)&&<button type="button" className={styles.primary}
                  disabled={Boolean(busy)||!approvedCost||!canStart||needsEvidence}
                  onClick={()=>void start(run)}>
                  {run.status==="failed"?"继续已有运行":"启动模型分析"}
                </button>}
                {run.status==="completed"&&<button type="button" className={styles.secondary}
                  disabled={Boolean(busy)} onClick={()=>void showRun(run.id)}>阅读报告</button>}
                <button type="button" className={styles.link} disabled={Boolean(busy)}
                  onClick={()=>void exportAudit(run.id)}>导出执行审计</button>
              </div>
              {needsEvidence&&<small className={styles.muted}>此运行需要先完成另一组并冻结原文证据。</small>}
            </article>;
          })}
        </div>
        {activeReport&&details[activeReport]?.report_md&&<section className={styles.report}>
          <div className={styles.sectionHead}><h3>智能体原始研究报告</h3>
            <button type="button" className={styles.secondary} onClick={()=>
              download(activeReport+"_report.md",details[activeReport].report_md||"")}>下载 Markdown</button>
          </div>
          <pre>{details[activeReport].report_md}</pre>
        </section>}
        <section className={styles.blind}>
          <h2>匿名科研质量评测</h2>
          <p className={styles.muted}>两组报告完成后再加载匿名版本，避免先知道哪个版本加入了科学价值筛选。</p>
          <div className={styles.actions}>
            <button type="button" className={styles.secondary} onClick={()=>void loadBlind()}
              disabled={Boolean(busy)}>加载匿名报告 A/B</button>
            <button type="button" className={styles.secondary} onClick={()=>void compare()}
              disabled={Boolean(busy)}>两份评分后查看对照结果</button>
          </div>
          {blind?.ready&&blind.blind_reports?.map(rep=><article className={styles.blindCard} key={rep.run_id}>
            <div className={styles.sectionHead}><h3>匿名报告 {rep.label}</h3>
              <button type="button" className={styles.secondary} onClick={()=>
                download("blind_"+rep.label+".md",rep.report_md)}>下载报告</button>
            </div>
            <details><summary>展开阅读完整科研报告</summary><pre>{rep.report_md}</pre></details>
            <form className={styles.rating} onSubmit={e=>void review(e,rep)}>
              <p>请评价这份报告的独立科研价值，而不只是它是否列举了需要补充的实验。</p>
              {categories.map(c=><label key={c.key}>
                <span>{c.label} <small>权重 {c.weight}%</small></span>
                <select value={rating(rep.run_id)[c.key]}
                  onChange={e=>editRating(rep.run_id,{[c.key]:Number(e.target.value)})}>
                  {[0,1,2,3,4,5].map(v=><option key={v} value={v}>{v}/5</option>)}
                </select>
              </label>)}
              <fieldset><legend>发现的问题（可多选）</legend>
                {failures.map(([key,name])=><label key={key}>
                  <input type="checkbox" checked={rating(rep.run_id).failure_tags.includes(key)}
                    onChange={e=>editRating(rep.run_id,{
                      failure_tags:e.target.checked
                        ?[...rating(rep.run_id).failure_tags,key]
                        :rating(rep.run_id).failure_tags.filter(x=>x!==key),
                    })}/>
                  {name}
                </label>)}
              </fieldset>
              <label className={styles.flag}><input type="checkbox"
                checked={rating(rep.run_id).hard_failure}
                onChange={e=>editRating(rep.run_id,{hard_failure:e.target.checked})}/>
                证据造假／虚构论文／伪造实验：硬性不通过</label>
              <label className={styles.notes}>失败原因与改进建议
                <textarea value={rating(rep.run_id).feedback} rows={3} maxLength={3000}
                  onChange={e=>editRating(rep.run_id,{feedback:e.target.value})}/>
              </label>
              <button type="submit" className={styles.primary}
                disabled={Boolean(busy)||rated[rep.run_id]}>
                {rated[rep.run_id]?"评价已保存":"提交匿名评分"}
              </button>
            </form>
          </article>)}
          {comparison&&<div className={styles.comparison}>
            <h3>A/B 评分对照</h3>
            <pre>{JSON.stringify(comparison,null,2)}</pre>
            <p className={styles.muted}>这只是人工评分差异，科学创新性仍需进一步查新并在未见论文上复测。</p>
          </div>}
        </section>
      </section>}
    </>}
  </main>;
}
