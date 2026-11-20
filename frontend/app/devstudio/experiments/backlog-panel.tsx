"use client";

import { useEffect, useMemo, useState } from "react";
import styles from "./experiments.module.css";

type Issue = {
  id: string; title: string; module_id: string; description: string;
  severity: string; status: string; created_at: string;
};
type IssueList = {items:Issue[]};
type IssueResponse = {detail?:string};
const statuses=[
  ["open","待处理"],["in_progress","进行中"],["blocked","受阻"],["resolved","已完成"],
] as const;
const labels:Record<string,string>=Object.fromEntries(statuses);
const priority=(row:Issue)=>row.title.match(/^\[(P[012])\]/)?.[1]||
  (row.severity==="high"?"P0":row.severity==="low"?"P2":"P1");
const sortOrder:Record<string,number>={P0:0,P1:1,P2:2};

async function request<T>(path:string,options?:RequestInit):Promise<T> {
  const result=await fetch("/api/proxy/devstudio/"+path,{
    cache:"no-store",credentials:"same-origin",...(options||{}),
    headers:{"Content-Type":"application/json",...(options?.headers||{})},
  });
  const body=await result.json().catch(()=>({})) as IssueResponse;
  if(!result.ok)throw new Error(body.detail||"请求失败 HTTP "+result.status);
  return body as T;
}

export default function BacklogPanel(){
  const [items,setItems]=useState<Issue[]>([]);
  const [priorityFilter,setPriorityFilter]=useState("");
  const [statusFilter,setStatusFilter]=useState("active");
  const [moduleFilter,setModuleFilter]=useState("");
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState("");
  useEffect(()=>{
    let cancelled=false;
    request<IssueList>("issues").then(r=>{
      if(!cancelled)setItems((r.items||[]).sort((a,b)=>
        (sortOrder[priority(a)]??3)-(sortOrder[priority(b)]??3)));
    }).catch(e=>{if(!cancelled)setError(e instanceof Error?e.message:"无法读取待办");})
      .finally(()=>{if(!cancelled)setLoading(false);});
    return ()=>{cancelled=true;};
  },[]);
  const filtered=useMemo(()=>items.filter(x=>
    (!priorityFilter||priority(x)===priorityFilter)&&
    (!moduleFilter||x.module_id===moduleFilter)&&
    (statusFilter==="all"||statusFilter==="active"
      ?statusFilter==="all"||x.status!=="resolved"
      :x.status===statusFilter)
  ),[items,priorityFilter,statusFilter,moduleFilter]);
  const modules=useMemo(()=>Array.from(new Set(items.map(x=>x.module_id))).sort(),[items]);
  async function update(item:Issue,status:string){
    if(item.status===status)return;
    if(status==="resolved"&&!confirm("将任务标记为已完成？请确认相关验收标准已经实际通过。"))return;
    setBusy(item.id);setError("");
    try{
      const saved=await request<Issue>("issues/"+encodeURIComponent(item.id),{
        method:"PATCH",body:JSON.stringify({status}),
      });
      setItems(old=>old.map(x=>x.id===item.id?saved:x));
    }catch(e){setError(e instanceof Error?e.message:"无法更新状态");}
    finally{setBusy("");}
  }
  return <details className={styles.backlog} open>
    <summary className={styles.backlogTitle}>
      <span>研发待办与问题 <small>（{items.filter(x=>x.status!=="resolved").length} 条未完成）</small></span>
      <span className={styles.backlogNote}>P0 优先 · 点击展开/折叠</span>
    </summary>
    <div className={styles.backlogFilters}>
      <label>优先级
        <select value={priorityFilter} onChange={e=>setPriorityFilter(e.target.value)}>
          <option value="">全部</option><option value="P0">P0 · 优先</option>
          <option value="P1">P1 · 近期</option><option value="P2">P2 · 后续</option>
        </select>
      </label>
      <label>状态
        <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)}>
          <option value="active">未完成</option><option value="all">全部</option>
          {statuses.map(([key,name])=><option key={key} value={key}>{name}</option>)}
        </select>
      </label>
      <label>模块
        <select value={moduleFilter} onChange={e=>setModuleFilter(e.target.value)}>
          <option value="">全部模块</option>
          {modules.map(m=><option key={m} value={m}>{m}</option>)}
        </select>
      </label>
      <button className={styles.subtle} type="button" onClick={()=>{setPriorityFilter("");setStatusFilter("active");setModuleFilter("");}}>清除筛选</button>
    </div>
    {error&&<p role="alert" className={styles.error}>{error}</p>}
    {loading?<p className={styles.muted}>正在载入待办…</p>:filtered.length===0?
      <p className={styles.muted}>当前筛选下没有待办。</p>:
      <div className={styles.backlogItems}>
        {filtered.map(item=><article key={item.id} className={styles.backlogItem}>
          <div className={styles.backlogItemHead}>
            <div>
              <strong>{item.title}</strong>
              <span>{item.module_id} · {labels[item.status]||item.status}</span>
            </div>
            <select aria-label={"修改任务状态："+item.title} value={item.status}
              disabled={busy===item.id}
              onChange={e=>void update(item,e.target.value)}>
              {statuses.map(([key,name])=><option key={key} value={key}>{name}</option>)}
            </select>
          </div>
          <details>
            <summary>任务说明、关联实验与验收标准</summary>
            <p className={styles.backlogDescription}>{item.description}</p>
          </details>
        </article>)}
      </div>}
  </details>;
}
