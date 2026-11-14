"use client";
import {useCallback,useEffect,useState} from "react";
import Link from "next/link";
import styles from "./personal-research.module.css";

type RefPaper={id:string;group:string;title:string;venue:string;year:number;url:string;why_selected:string;evidence_level:string};
type Probe={id:"A"|"B"|"C";label:string;theme:string;statement:string;papers:RefPaper[]};
type RunTopic={key:string;title:string;question:string;probes:Probe[];supplementary:RefPaper[];candidate_question:string;checks:string[]};
type Result={id:string;topic_key:string;run:{
 topic:RunTopic;created_on:string;retrieval_provenance:string;
 review_status:string;candidate_status:string;disclosure:string;
 llm_api_executed:boolean;openalex_api_executed:boolean;
};review_status:string;source_digest:string;created_at:string;visibility:string};
type Profile={scope:string;status:string;profile:{
 explicitly_declared_interests:string[];research_questions?:Record<string,string>;
 analysis_preferences?:string[];claim?:string;note?:string;
}|null;team_portrait?:{
 counts?:Record<string,number>;official_line_names?:string[];
 note?:string;
};note:string};
const labels:Record<string,string>={A:"规划应用",B:"城市科学",C:"计算方法"};
const names:Record<string,string>={child_health_extrapolation:"儿童健康空间外推",vertical_urbanization_3d:"三维竖向城市化"};
function stamp(value:string|null|undefined){
 return value?value.slice(0,10):"尚无记录";
}
async function api<T>(path:string,method:"GET"|"POST"|"PUT"="GET",payload?:unknown):Promise<T>{
 const res=await fetch("/api/proxy/personal-research/"+path,{
  method,cache:"no-store",credentials:"same-origin",
  headers:{"Content-Type":"application/json"},
  ...(payload===undefined?{}:{body:JSON.stringify(payload)}),
 });
 if(!res.ok){
  let msg="读取失败（"+res.status+"）";
  try{const data=await res.json();if(typeof data?.detail==="string")msg=data.detail;}catch{}
  throw Error(msg);
 }
 return await res.json() as T;
}

export default function PersonalResearch(){
 const [profile,setProfile]=useState<Profile|null>(null);
 const [results,setResults]=useState<Result[]>([]);
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 const [selected,setSelected]=useState("child_health_extrapolation");
 const [editing,setEditing]=useState(false);
 const [interestText,setInterestText]=useState("儿童健康空间外推\n三维竖向城市化");
 const [note,setNote]=useState("");

 const reload=useCallback(async()=>{
   setBusy(true);
   try{
    const [p,r]=await Promise.all([
      api<Profile>("me"),api<{items:Result[]}>("me/results"),
    ]);
    setProfile(p);setResults(r.items||[]);
    setInterestText((p.profile?.explicitly_declared_interests||["儿童健康空间外推","三维竖向城市化"]).join("\n"));
    setNote(p.profile?.note||"");
    setError("");
   }catch(e){setError(e instanceof Error?e.message:"后端不可用");}
   finally{setBusy(false);}
 },[]);
 useEffect(()=>{void reload();},[reload]);
 async function initialize(){
   setBusy(true);
   try{
    await api("me/initialize","POST",{});
    await reload();
   }catch(e){setError(e instanceof Error?e.message:"初始化失败");}
   finally{setBusy(false);}
 }
 async function save(){
  const interests=interestText.split("\n").map(x=>x.trim()).filter(Boolean);
  setBusy(true);
  try{
   await api("me","PUT",{interests,note});
   setEditing(false);
   await reload();
  }catch(e){setError(e instanceof Error?e.message:"保存失败");}
  finally{setBusy(false);}
 }
 const displayed=results.find(x=>x.topic_key===selected)||results[0];
 return <main className={styles.root}>
  <div className={styles.shell}>
   <nav className={styles.nav}>
    <Link href="/research-atlas-v0.5.html?space=research">← 返回研究台</Link>
    <Link href="/devstudio">Development Studio</Link>
   </nav>
   <header className={styles.header}>
    <div>
     <div className={styles.eyebrow}>RESEARCH ATLAS / PERSONAL RESEARCH</div>
     <h1>我的科研画像</h1>
     <p>个人科研方向与检索结果独立保存。团队科研画像可作为背景信息，但不会覆盖你的研究兴趣。</p>
    </div>
    <button type="button" disabled={busy} onClick={()=>void reload()}>{busy?"读取中":"刷新"}</button>
   </header>
   {error&&<div className={styles.error} role="alert">{error}</div>}
   <section className={styles.panel}>
    <div className={styles.sectionhead}><h2>个人研究档案</h2>
      <span className={styles.pill}>{profile?.status==="not_created"?"尚未建立":"仅自己可见"}</span>
    </div>
    {!profile?.profile?<div className={styles.blank}>
     <p>目前这个登录账号尚未建立个人画像。点击后将你明确选择的两个研究方向绑定到当前账号，同时从测试数据库领取两份文献研究结果。</p>
     <button type="button" onClick={()=>void initialize()} disabled={busy}>建立我的画像并载入两个研究结果</button>
    </div>:<>
      {!editing?<div>
       <div className={styles.chips}>{(profile.profile.explicitly_declared_interests||[]).map(x=><span key={x}>{x}</span>)}</div>
       <div className={styles.sectionhead}><small>关注方向可以单独编辑，不影响团队研究主线</small>
        <button className={styles.secondary} type="button" onClick={()=>setEditing(true)}>编辑画像</button></div>
       <div className={styles.soft}>{(profile.profile.analysis_preferences||[]).map((v,i)=><p key={i}>{v}</p>)}</div>
      </div>:<div className={styles.editor}>
       <label>研究领域（每行一个）<textarea rows={4} value={interestText} onChange={e=>setInterestText(e.target.value)} /></label>
       <label>附加研究偏好<textarea rows={3} value={note} onChange={e=>setNote(e.target.value)}/></label>
       <div className={styles.actions}><button disabled={busy} type="button" onClick={()=>void save()}>保存个人画像</button>
        <button className={styles.secondary} type="button" onClick={()=>setEditing(false)}>取消</button></div>
      </div>}
    </>}
   </section>
   <section className={styles.panel}>
    <div className={styles.sectionhead}><h2>两次三探针研究试运行</h2><span className={styles.pill}>待科研审核</span></div>
    <p className={styles.hint}>本次使用实际出版页面检索资料，并整理成两个有来源记录的试运行结果。不是平台自动完成的 LLM 综合，也没有运行儿童健康或楼层预测模型。</p>
    <div className={styles.tabs}>
     {Object.keys(names).map(k=><button key={k} type="button" onClick={()=>setSelected(k)}
       className={selected===k?styles.active:""}>{names[k]}</button>)}
    </div>
    {displayed?<div>
      <div className={styles.runhead}>
       <div><h3>{displayed.run.topic.title}</h3><p>{displayed.run.topic.question}</p></div>
       <span className={styles.pill}>需审核</span>
      </div>
      <div className={styles.probes}>
        {displayed.run.topic.probes.map(probe=><article key={probe.id} className={styles.probe}>
          <div className={styles.probehead}><span className={styles.letter}>{probe.id}</span>
            <div><h4>{labels[probe.id]}｜{probe.theme}</h4><p>{probe.statement}</p></div>
          </div>
          <ul>{probe.papers.map(p=><li key={p.id}>
           <a href={p.url} target="_blank" rel="noopener noreferrer">{p.title} ↗</a>
           <span>{p.venue} · {p.year}</span>
           <small>{p.why_selected}</small>
          </li>)}</ul>
        </article>)}
      </div>
      <div className={styles.footergrid}>
        <section><h4>待验证的研究问题</h4><p>{displayed.run.topic.candidate_question}</p>
         <h4>下一步核验</h4><ul>{displayed.run.topic.checks.map(x=><li key={x}>{x}</li>)}</ul></section>
        <section><h4>跨刊补充证据</h4>{displayed.run.topic.supplementary.map(p=><p key={p.id}>
         <a href={p.url} target="_blank" rel="noopener noreferrer">{p.title} ↗</a><small>{p.venue}</small></p>)}
         <p className={styles.disclosure}>{displayed.run.disclosure}</p>
         <small>原始快照指纹：{displayed.source_digest.slice(0,16)}… · {stamp(displayed.run.created_on)}</small>
        </section>
      </div>
    </div>:<p className={styles.blank}>当前账号尚未关联研究结果，请先建立个人画像。</p>}
   </section>
   <section className={styles.team}>
    <div className={styles.sectionhead}><h2>团队画像 · 只读摘要</h2><span className={styles.pill}>团队共享来源</span></div>
    <p>{profile?.note||"团队画像单独维护，不自动用个人研究方向覆盖。"}</p>
    <div className={styles.chips}>{(profile?.team_portrait?.official_line_names||[]).slice(0,8).map((line,i)=><span key={i}>{line}</span>)}</div>
    <small>团队成果与个人学术能力不是同一个概念；团队画像仍需独立研究审核。</small>
   </section>
  </div>
 </main>;
}
