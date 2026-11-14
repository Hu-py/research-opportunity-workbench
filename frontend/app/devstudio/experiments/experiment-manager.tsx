"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import styles from "./experiments.module.css";

type Experiment = {
  id: string; module_id: string; title: string; hypothesis: string;
  baseline: string; input_snapshot_ref: string; change_id: string;
  metrics: string[]; objective: string; scenario: string; change_object: string;
  method: string; expected_result: string; conclusion: string; next_action: string;
  status: string; revision: number; created_by: string; created_at: string;
  updated_by: string; updated_at: string;
};
type Run = {id:string; kind:string; external_url:string; status:string; code_sha:string; note:string; created_at:string};
type Review = {id:string; run_id:string; rubric_version:string; scores:Record<string,number>; limitations:string; created_at:string};
type ChangeEvent = {id:string; revision:number; action:string; actor_id:string; created_at:string; details:Record<string,unknown>};
type Draft = Omit<Experiment,"id"|"revision"|"created_by"|"created_at"|"updated_by"|"updated_at">;
type Filter = {search:string; module_id:string; objective:string; scenario:string; status:string; include_archived:boolean};
const modules = [
  ["DISCOVERY","文献发现与来源核验"],["PAPER_KNOWLEDGE","论文知识与证据抽取"],
  ["SIGNAL_L1","跨论文科研信号"],["DEEP_READ_L2","代表论文深读"],
  ["IDEA_L3","方法迁移与选题"],["TEAM_FIT","团队匹配"],
  ["DELIVERY","场景交付与反馈"],["PLATFORM","平台、模型与任务"],
] as const;
const objectives = [
  ["other","其他／待分类"],["quality","结果质量"],["performance","性能效率"],
  ["generalization","泛化与迁移"],["coverage","覆盖度"],["reliability","稳定可靠"],
  ["methods","方法验证"],["usability","可用性"],
] as const;
const scenarios = [
  ["other","其他"],["radar_a","Radar A · 规划实践"],["radar_b","Radar B · 技术方法"],
  ["sc01","SC01"],["sc02","SC02"],["sc03","SC03"],["platform","平台与开发"],
] as const;
const targets = [
  ["other","其他"],["source","来源配置"],["workflow","工作流"],["prompt","提示词"],
  ["model","模型"],["skill","Skill"],["backend","后端"],["frontend","前端"],
  ["data","数据"],["evaluation","评价系统"],
] as const;
const states = [
  ["planned","待执行"],["running","进行中"],["blocked","受阻"],
  ["review","待复核"],["completed","已完成"],["archived","已归档"],
] as const;
const transitions:Record<string,string[]> = {
  planned:["running","blocked","archived"],
  running:["blocked","review","archived"],
  blocked:["planned","running","archived"],
  review:["running","completed","blocked","archived"],
  completed:["running","archived"],
  archived:["planned"],
};
const baseDraft:Draft={
  module_id:"PLATFORM",title:"",hypothesis:"",baseline:"",
  input_snapshot_ref:"",metrics:[],change_id:"",
  objective:"other",scenario:"platform",change_object:"other",
  method:"",expected_result:"",conclusion:"",next_action:"",status:"planned",
};
const initialFilters:Filter={search:"",module_id:"",objective:"",scenario:"",status:"",include_archived:false};
const label=(arr:readonly (readonly [string,string])[], key:string)=>
  arr.find(v=>v[0]===key)?.[1]||key;
const shortDate=(v:string)=>v?new Date(v).toLocaleString("zh-CN"):"—";

async function api<T>(path:string,method="GET",payload?:unknown):Promise<T> {
  const res=await fetch("/api/proxy/devstudio/"+path,{
    method,credentials:"same-origin",cache:"no-store",
    headers:{"Content-Type":"application/json"},
    ...(payload===undefined?{}:{body:JSON.stringify(payload)}),
  });
  const body=await res.json().catch(()=>({})) as {detail?:string};
  if(!res.ok)throw new Error(typeof body.detail==="string"?body.detail:"请求失败（HTTP "+res.status+"）");
  return body as T;
}

export default function ExperimentManager({currentRole}:{currentRole:string}) {
  const [items,setItems]=useState<Experiment[]>([]);
  const [filter,setFilter]=useState<Filter>(initialFilters);
  const [selected,setSelected]=useState<string>("");
  const [draft,setDraft]=useState<Draft>(baseDraft);
  const [revision,setRevision]=useState(0);
  const [creating,setCreating]=useState(false);
  const [view,setView]=useState<"details"|"runs"|"history">("details");
  const [runs,setRuns]=useState<Run[]>([]);
  const [reviews,setReviews]=useState<Record<string,Review[]>>({});
  const [history,setHistory]=useState<ChangeEvent[]>([]);
  const [runUrl,setRunUrl]=useState("");
  const [runKind,setRunKind]=useState("github_actions");
  const [runNote,setRunNote]=useState("");
  const [reviewRun,setReviewRun]=useState("");
  const [reviewScore,setReviewScore]=useState("3");
  const [reviewNote,setReviewNote]=useState("");
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");

  const update=(key:keyof Draft,value:string|string[])=>{
    setDraft(old=>({...old,[key]:value}));
  };

  const loadList=useCallback(async(f:Filter, preferred?:string)=>{
    setLoading(true);
    try{
      const params=new URLSearchParams();
      if(f.search.trim())params.set("query",f.search.trim());
      if(f.module_id)params.set("module_id",f.module_id);
      if(f.objective)params.set("objective",f.objective);
      if(f.scenario)params.set("scenario",f.scenario);
      if(f.status)params.set("status",f.status);
      if(f.include_archived)params.set("include_archived","true");
      const result=await api<{items:Experiment[]}>("experiment-management?"+params.toString());
      setItems(result.items||[]);
      setSelected(old=>{
        const candidate=preferred||old;
        return result.items.some(x=>x.id===candidate)?candidate:(result.items[0]?.id||"");
      });
      setError("");
    }catch(err){setError(err instanceof Error?err.message:"无法加载实验");}
    finally{setLoading(false);}
  },[]);
  useEffect(()=>{void loadList(filter);},[filter,loadList]);

  const loadDetails=useCallback(async(id:string)=>{
    try{
      const [detail,runRes,historyRes]=await Promise.all([
        api<Experiment>("experiment-management/"+encodeURIComponent(id)),
        api<{items:Run[]}>("experiments/"+encodeURIComponent(id)+"/runs"),
        api<{items:ChangeEvent[]}>("experiment-management/"+encodeURIComponent(id)+"/history"),
      ]);
      setDraft({
        module_id:detail.module_id,title:detail.title,hypothesis:detail.hypothesis,
        baseline:detail.baseline,input_snapshot_ref:detail.input_snapshot_ref,
        metrics:detail.metrics||[],change_id:detail.change_id||"",
        objective:detail.objective,scenario:detail.scenario,change_object:detail.change_object,
        method:detail.method,expected_result:detail.expected_result,
        conclusion:detail.conclusion,next_action:detail.next_action,status:detail.status,
      });
      setRevision(detail.revision);
      setRuns(runRes.items||[]);
      setHistory(historyRes.items||[]);
      const list=await Promise.all((runRes.items||[]).slice(0,30).map(async run=>{
        const data=await api<{items:Review[]}>("runs/"+encodeURIComponent(run.id)+"/evaluations");
        return [run.id,data.items] as const;
      }));
      setReviews(Object.fromEntries(list));
    }catch(err){setError(err instanceof Error?err.message:"无法读取实验详情");}
  },[]);
  useEffect(()=>{if(!creating&&selected){void loadDetails(selected);}},[creating,selected,loadDetails]);

  const fresh=()=>{
    setCreating(true);setSelected("");setDraft({...baseDraft,metrics:[]});
    setRevision(0);setRuns([]);setReviews({});setHistory([]);setView("details");
    setMessage("");setError("");
  };
  const choose=(id:string)=>{
    setCreating(false);setSelected(id);setView("details");setMessage("");setError("");
  };
  const refresh=async(id?:string)=>{
    await loadList(filter,id);
    if(id)await loadDetails(id);
  };
  const save=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();setBusy(true);setError("");setMessage("");
    try{
      if(creating){
        const data=await api<Experiment>("experiment-management","POST",{
          ...draft,metrics:draft.metrics, status:undefined,
        });
        setCreating(false);setSelected(data.id);
        setMessage("实验已创建，可继续关联运行与评测");
        await refresh(data.id);
      }else{
        if(!selected)throw new Error("请先选择一个实验");
        const data=await api<Experiment>("experiment-management/"+encodeURIComponent(selected),
          "PATCH",{...draft,expected_revision:revision});
        setRevision(data.revision);
        setMessage("实验已保存，修订版本 "+data.revision);
        await refresh(selected);
      }
    }catch(err){setError(err instanceof Error?err.message:"保存失败");}
    finally{setBusy(false);}
  };
  const changeStatus=async(next:string)=>{
    if(!selected)return;
    if(next==="archived"&&!confirm("确认归档实验？归档后不会从数据库删除，可重新开启。"))return;
    setBusy(true);setError("");setMessage("");
    try{
      const data=await api<Experiment>("experiment-management/"+encodeURIComponent(selected),
        "PATCH",{expected_revision:revision,status:next});
      setRevision(data.revision);setMessage("状态已更新为："+label(states,next));
      await refresh(selected);
    }catch(err){setError(err instanceof Error?err.message:"状态更新失败");}
    finally{setBusy(false);}
  };
  const linkRun=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();if(!selected)return;
    setBusy(true);setError("");
    try{
      await api("experiments/"+encodeURIComponent(selected)+"/runs","POST",{
        kind:runKind,external_url:runUrl.trim(),note:runNote.trim(),
      });
      setRunUrl("");setRunNote("");setMessage("运行引用已登记，尚未自动核验执行结果");
      await loadDetails(selected);
    }catch(err){setError(err instanceof Error?err.message:"登记运行失败");}
    finally{setBusy(false);}
  };
  const addReview=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();if(!reviewRun)return;
    setBusy(true);setError("");
    try{
      await api("runs/"+encodeURIComponent(reviewRun)+"/evaluations","POST",{
        rubric_version:"manual-review-v1",
        scores:{research_quality:Number(reviewScore)},
        limitations:reviewNote.trim(),
      });
      setReviewRun("");setReviewNote("");
      setMessage("人工评价已追加，历史评价不会被覆盖");
      if(selected)await loadDetails(selected);
    }catch(err){setError(err instanceof Error?err.message:"评价保存失败");}
    finally{setBusy(false);}
  };
  const input=(key:keyof Draft,labelText:string,required=false,maxLength=2000)=>(
    <label className={styles.field} key={key}>
      <span>{labelText}</span>
      <input required={required} maxLength={maxLength} value={draft[key] as string}
        onChange={e=>update(key,e.target.value)}/>
    </label>
  );
  const long=(key:keyof Draft,labelText:string,required=false,rows=3)=>(
    <label className={styles.field} key={key}>
      <span>{labelText}</span>
      <textarea required={required} rows={rows} value={draft[key] as string}
        onChange={e=>update(key,e.target.value)}/>
    </label>
  );
  const select=(key:keyof Draft,labelText:string,options:readonly (readonly [string,string])[])=>
    <label className={styles.field} key={key}>
      <span>{labelText}</span>
      <select value={draft[key] as string} onChange={e=>update(key,e.target.value)}>
        {options.map(([val,text])=><option key={val} value={val}>{text}</option>)}
      </select>
    </label>;

  return <main className={styles.page}>
    <header className={styles.top}>
      <div>
        <a href="/devstudio" className={styles.back}>Development Studio / 返回研发台</a>
        <h1>实验管理 <small>V0.4</small></h1>
        <p>实验目标、场景、变更对象、运行证据与版本演化集中管理。登记不等于科学验证。</p>
      </div>
      <div className={styles.headerActions}>
        <span className={styles.role}>当前身份 · {currentRole.toUpperCase()}</span>
        <button type="button" className={styles.primary} onClick={fresh}>＋ 新建实验</button>
      </div>
    </header>
    {error&&<div role="alert" className={styles.error}>{error}</div>}
    {message&&<div role="status" className={styles.message}>{message}</div>}
    <section className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.heading}><strong>实验列表</strong><span>{items.length} 项</span></div>
        <div className={styles.filters}>
          <label className={styles.field}>搜索标题、假设或方法
            <input value={filter.search} placeholder="搜索实验..." onChange={e=>setFilter(f=>({...f,search:e.target.value}))}/>
          </label>
          <label className={styles.field}>模块
            <select value={filter.module_id} onChange={e=>setFilter(f=>({...f,module_id:e.target.value}))}>
              <option value="">所有模块</option>
              {modules.map(([id,name])=><option key={id} value={id}>{name}</option>)}
            </select>
          </label>
          <div className={styles.filterGrid}>
            <label className={styles.field}>目标<select value={filter.objective} onChange={e=>setFilter(f=>({...f,objective:e.target.value}))}>
              <option value="">全部目标</option>
              {objectives.map(([id,name])=><option key={id} value={id}>{name}</option>)}
            </select></label>
            <label className={styles.field}>场景<select value={filter.scenario} onChange={e=>setFilter(f=>({...f,scenario:e.target.value}))}>
              <option value="">全部场景</option>
              {scenarios.map(([id,name])=><option key={id} value={id}>{name}</option>)}
            </select></label>
          </div>
          <label className={styles.field}>状态
            <select value={filter.status} onChange={e=>setFilter(f=>({...f,status:e.target.value}))}>
              <option value="">所有进行中</option>
              {states.map(([id,name])=><option key={id} value={id}>{name}</option>)}
            </select>
          </label>
          <label className={styles.toggle}>
            <input type="checkbox" checked={filter.include_archived} onChange={e=>setFilter(f=>({...f,include_archived:e.target.checked}))}/>
            包含已归档实验
          </label>
          <button type="button" className={styles.subtle} onClick={()=>setFilter(initialFilters)}>重置筛选</button>
        </div>
        {loading?<p className={styles.muted}>正在读取...</p>:items.length===0?<p className={styles.muted}>没有符合条件的实验。可新建第一条。</p>:(
          <div className={styles.experimentList}>
            {items.map(x=><button key={x.id} type="button"
              className={styles.experimentCard+(x.id===selected&&!creating?" "+styles.active:"")}
              onClick={()=>choose(x.id)}>
              <strong>{x.title}</strong>
              <span>{label(modules,x.module_id)} · {label(states,x.status)}</span>
              <small>{label(objectives,x.objective)} / {label(scenarios,x.scenario)}</small>
              <small>修订 {x.revision} · {shortDate(x.updated_at)}</small>
            </button>)}
          </div>
        )}
      </aside>
      <section className={styles.detail}>
        {!selected&&!creating?<div className={styles.empty}>选择左侧实验，或点击「新建实验」开始管理。</div>:(
          <>
            <div className={styles.detailTop}>
              <div>
                <span className={styles.eyebrow}>{creating?"NEW EXPERIMENT":"EXPERIMENT / "+selected}</span>
                <h2>{creating?"建立实验档案":draft.title||"未命名实验"}</h2>
                {!creating&&<p className={styles.muted}>版本 {revision} · {label(states,draft.status)}</p>}
              </div>
              {!creating&&<button type="button" className={styles.subtle} onClick={()=>void refresh(selected)}>刷新当前实验</button>}
            </div>
            {!creating&&<div className={styles.tabs}>
              {(["details","runs","history"] as const).map((x)=><button type="button" key={x}
                className={view===x?styles.tabActive:""} onClick={()=>setView(x)}>
                {x==="details"?"实验资料":x==="runs"?"运行与评价":"变更记录"}
              </button>)}
            </div>}
            {(creating||view==="details")&&<form className={styles.form} onSubmit={save}>
              <div className={styles.formGrid}>
                {input("title","实验名称 *",true,200)}
                {select("module_id","所属模块",modules)}
                {select("objective","实验目标",objectives)}
                {select("scenario","使用场景",scenarios)}
                {select("change_object","变更对象",targets)}
                <label className={styles.field}><span>追踪指标（逗号分隔，最多 20 个）</span>
                  <input value={draft.metrics.join(", ")}
                    onChange={e=>update("metrics",e.target.value.split(/[,，]/).map(x=>x.trim()).filter(Boolean))}/>
                </label>
              </div>
              {long("hypothesis","研究假设 / 验证问题 *",true)}
              {long("method","实验设计与方法")}
              {long("baseline","基线和对照")}
              {long("expected_result","预期结果 / 判定条件")}
              <div className={styles.formGrid}>
                {input("input_snapshot_ref","数据或输入快照引用",false,1600)}
                {input("change_id","关联的变更申请 ID（可选）",false,32)}
              </div>
              {long("conclusion","阶段结论（人工登记，不代表通过科学验证）")}
              {long("next_action","下一步行动",false,2)}
              <div className={styles.footer}>
                <button className={styles.primary} disabled={busy} type="submit">{busy?"保存中...":creating?"创建实验":"保存修改并记录版本"}</button>
                <span>并发编辑发生冲突时会提示刷新，不覆盖他人修改。</span>
              </div>
              {!creating&&<div className={styles.workflow}>
                <h3>实验状态</h3>
                <p>不能跳过复核直接标记完成；需至少一条关联运行的人工评价。</p>
                <div className={styles.statusActions}>{(transitions[draft.status]||[]).map(status=>
                  <button type="button" key={status} disabled={busy} onClick={()=>void changeStatus(status)}>
                    {status==="archived"?"归档实验":status==="planned"&&draft.status==="archived"?"重新开启":"转为「"+label(states,status)+"」"}
                  </button>)}
                </div>
              </div>}
            </form>}
            {!creating&&view==="runs"&&<div className={styles.tabContent}>
              <h3>关联运行记录</h3><p className={styles.muted}>GitHub Actions / 内部任务仅为引用。外部执行结果默认为「待核验」，不会自动声称成功。</p>
              <form onSubmit={linkRun} className={styles.inlineForm}>
                <label className={styles.field}>运行类型<select value={runKind} onChange={e=>setRunKind(e.target.value)}>
                  <option value="github_actions">GitHub Actions</option><option value="internal">内部科研任务</option>
                </select></label>
                <label className={styles.field}>GitHub Run URL 或 /api/tasks/… 路径
                  <input required value={runUrl} onChange={e=>setRunUrl(e.target.value)} placeholder="https://github.com/Hu-py/research-opportunity-workbench/actions/runs/…"/>
                </label>
                <label className={styles.field}>运行备注<input value={runNote} onChange={e=>setRunNote(e.target.value)}/></label>
                <button type="submit" className={styles.primary} disabled={busy}>关联运行</button>
              </form>
              {runs.length===0?<p className={styles.muted}>尚未关联运行。</p>:runs.map(run=><article className={styles.panel} key={run.id}>
                <div><strong>{run.kind==="github_actions"?"GitHub Actions":"内部任务"}</strong> · {run.status} · {shortDate(run.created_at)}</div>
                <p><code>{run.external_url}</code></p>
                {run.kind==="github_actions"&&<a href={run.external_url} target="_blank" rel="noopener noreferrer">打开 GitHub Run</a>}
                <p className={styles.muted}>{run.note||"无备注"}</p>
                <h4>人工评价（追加，不覆盖）</h4>
                {(reviews[run.id]||[]).map(rv=><div className={styles.review} key={rv.id}>
                  {shortDate(rv.created_at)} · {rv.rubric_version} · 评分 {rv.scores.research_quality??"—"}/5
                  <div>{rv.limitations||"未填写局限"}</div>
                </div>)}
                <button type="button" className={styles.subtle} onClick={()=>setReviewRun(run.id)}>＋ 新增人工评价</button>
              </article>)}
              {reviewRun&&<form onSubmit={addReview} className={styles.panel}>
                <h4>评价 Run {reviewRun}</h4>
                <label className={styles.field}>质量评分（仅人工记录）
                  <select value={reviewScore} onChange={e=>setReviewScore(e.target.value)}>
                    {[0,1,2,3,4,5].map(v=><option key={v} value={v}>{v} / 5</option>)}
                  </select>
                </label>
                <label className={styles.field}>局限与依据
                  <textarea rows={3} value={reviewNote} onChange={e=>setReviewNote(e.target.value)}/>
                </label>
                <div className={styles.footer}>
                  <button type="submit" disabled={busy} className={styles.primary}>保存人工评价</button>
                  <button type="button" onClick={()=>setReviewRun("")} className={styles.subtle}>取消</button>
                </div>
              </form>}
            </div>}
            {!creating&&view==="history"&&<div className={styles.tabContent}>
              <h3>实验版本与变更记录</h3>
              <p className={styles.muted}>每次修改附修订号、操作者和变更差异。旧版实验的历史从第一次 V0.4 修改开始记录。</p>
              {history.length===0?<p className={styles.muted}>暂无 V0.4 变更记录。</p>:history.map(h=><article className={styles.panel} key={h.id}>
                <div><strong>Revision {h.revision}</strong> · {h.action==="created"?"创建":h.action==="status_changed"?"状态更新":"编辑"} · {shortDate(h.created_at)}</div>
                <small className={styles.muted}>操作成员：{h.actor_id}</small>
                <details><summary>查看本次变更</summary>
                  <pre className={styles.json}>{JSON.stringify(h.details,null,2)}</pre>
                </details>
              </article>)}
            </div>}
          </>
        )}
      </section>
    </section>
  </main>;
}
