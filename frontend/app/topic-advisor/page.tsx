"use client";
import {useEffect, useState} from "react";
import {api} from "@/lib/api";

type Idea={title:string;question:string;method:string;why_now:string;paper_ids:string[];risks:string[];minimal_experiment:string};
type Result={id:string;created_at:string;content:{case:string;strategy:string;revision:number;result:{ideas:Idea[];reason?:string;trace:unknown}}};
type Portfolio={results:Result[];contexts:unknown[];decisions:unknown[];assessments:unknown[]};
export default function TopicAdvisor(){
 const [data,setData]=useState<Portfolio|null>(null),[error,setError]=useState("");
 const [selected,setSelected]=useState<{id:string;title:string}|null>(null);
 const [action,setAction]=useState("defer"),[reason,setReason]=useState(""),[principle,setPrinciple]=useState("");
 const [busy,setBusy]=useState(false);
 const reload=()=>api<Portfolio>("topic-advisor").then(setData).catch(e=>setError(String(e)));
 useEffect(()=>{void reload()},[]);
 async function submit(){if(!selected)return;setBusy(true);setError("");try{
  await api("topic-advisor/feedback",{method:"POST",body:JSON.stringify({result_id:selected.id,title:selected.title,action,reason,principle})});
  setSelected(null);setReason("");setPrinciple("");await reload();
 }catch(e){setError(String(e))}finally{setBusy(false)}}
 return <main style={{maxWidth:1100,margin:"40px auto",padding:24}}>
  <a href="/">← 返回工作台</a><h1>科研选题顾问</h1>
  <p>比较研究机会、证据和独立审查，积累可追溯的科研判断。所有候选的创新性和数据权限仍需人工核验。</p>
  {error&&<p role="alert">{error}</p>}{!data&&!error&&<p>正在读取选题档案…</p>}
  {data?.results.length===0&&<p>还没有选题记录。完成受预算控制的评测并导入后会显示在这里。</p>}
  {data?.results.map(row=><section key={row.id} style={{borderTop:"1px solid #aaa",padding:"24px 0"}}>
   <h2>{row.content.case} · {row.content.strategy} · 版本 {row.content.revision}</h2><p>{row.created_at}</p>
   {!row.content.result.ideas.length&&<p>本轮没有值得推荐的高质量选题：{row.content.result.reason}</p>}
   {row.content.result.ideas.map(idea=><article key={idea.title} style={{padding:16,background:"#f4f6f9",color:"#172033",marginBottom:16}}>
    <h3>{idea.title}</h3><p>{idea.question}</p><p>方法：{idea.method}</p><p>推荐理由：{idea.why_now}</p>
    <p>下一步核验：{idea.minimal_experiment}</p><ul>{idea.risks.map(x=><li key={x}>{x}</li>)}</ul>
    <p>论文证据：{idea.paper_ids.join("、")}</p>
    <button onClick={()=>setSelected({id:row.id,title:idea.title})}>记录科研判断</button>
   </article>)}
   <details><summary>生成路径与科学审查</summary><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(row.content.result.trace,null,2)}</pre></details>
  </section>)}
  {selected&&<form onSubmit={e=>{e.preventDefault();void submit()}}><h2>{selected.title}</h2>
   <label>决定<select value={action} onChange={e=>setAction(e.target.value)}><option value="accept">接受</option><option value="modify">修改</option><option value="reject">否定</option><option value="defer">暂缓</option></select></label>
   <label>具体科学理由<textarea required minLength={10} maxLength={3000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
   <label>可复用判断原则<textarea required minLength={10} maxLength={2000} value={principle} onChange={e=>setPrinciple(e.target.value)}/></label>
   <button disabled={busy}>确认记录</button><button type="button" onClick={()=>setSelected(null)}>取消</button>
  </form>}
  <details><summary>输入证据、独立评价与历史决策</summary><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify({contexts:data?.contexts,assessments:data?.assessments,decisions:data?.decisions},null,2)}</pre></details>
 </main>
}
