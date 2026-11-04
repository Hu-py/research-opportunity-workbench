"use client";
import {useCallback,useEffect,useState} from "react";
import {BookOpen,CheckCircle2,GitBranch,Plus,RefreshCw,Search} from "lucide-react";
import {api} from "@/lib/api";

type Interest={id:string;title:string;focus:"applied"|"cs_frontier"|"cross_domain";
  problem:string;queries:string[];venues:string[];enabled:boolean;last_status:string;
  last_checked_at:string|null;last_new:number;
  recent_papers:{id:string;title:string;url:string;published:string}[]};
type Data={items:Interest[]};
const presets=[
 {name:"机器学习与图表示",venues:"NeurIPS, ICML, ICLR",queries:"graph foundation model\nself supervised graph representation learning"},
 {name:"LLM 智能体",venues:"ACL, EMNLP",queries:"LLM agent planning evaluation\nagent workflow optimization"},
 {name:"计算机视觉与多模态",venues:"CVPR, ICCV, ECCV",queries:"vision language model remote sensing\n3D visual scene representation"},
 {name:"数据库与信息检索",venues:"SIGMOD, VLDB, ICDE",queries:"retrieval augmented generation database\nvector database efficient retrieval"},
 {name:"机器人与具身智能",venues:"ICRA, IROS, RSS",queries:"embodied agent world model\nrobot task planning navigation"},
 {name:"HCI / 计算机系统",venues:"CHI, UIST, OSDI",queries:"human AI collaboration evaluation\nmulti agent software systems"},
];
function split(s:string,n:number){return Array.from(new Set(s.split(/[\n,;，；]+/).map(x=>x.trim()).filter(Boolean))).slice(0,n);}
export default function InterestWatchlist({canEdit}:{canEdit:boolean}){
 const [data,setData]=useState<Data|null>(null),[busy,setBusy]=useState(false);
 const [error,setError]=useState(""),[notice,setNotice]=useState("");
 const [name,setName]=useState(""),[goal,setGoal]=useState(""),[queries,setQueries]=useState("");
 const [venues,setVenues]=useState(""),[focus,setFocus]=useState<Interest["focus"]>("cs_frontier");
 const [open,setOpen]=useState(false);
 const load=useCallback(async()=>{try{setData(await api<Data>("research-interests"));}catch(e){setError(e instanceof Error?e.message:"读取失败");}},[]);
 useEffect(()=>{void load();},[load]);
 async function create(){
  setError("");setNotice("");if(name.trim().length<3||!split(queries,4).length){setError("请填写主题名称及至少一个检索表达式");return;}
  setBusy(true);
  try{
   await api("research-interests",{method:"POST",body:JSON.stringify({
    title:name.trim(),focus,problem:goal,keywords:[],queries:split(queries,4),venues:split(venues,12),enabled:true,
   })});
   setOpen(false);setName("");setGoal("");setQueries("");setVenues("");
   setNotice("兴趣分支已保存；每周调度需要独立开启 GitHub Actions。");
   await load();
  }catch(e){setError(e instanceof Error?e.message:"保存失败");}
  finally{setBusy(false);}
 }
 async function action(item:Interest,kind:"toggle"|"scan"){
  setBusy(true);setError("");setNotice("");
  try{
   if(kind==="toggle"){
    await api("research-interests/"+encodeURIComponent(item.id),{method:"PATCH",body:JSON.stringify({enabled:!item.enabled})});
    setNotice("分支监测状态已更改。");
   }else{
    await api("research-interests/"+encodeURIComponent(item.id)+"/scan",{method:"POST",body:"{}"});
    setNotice("已提交真实文献试抓取，请刷新查看结果。");
   }
   await load();
  }catch(e){setError(e instanceof Error?e.message:"操作失败");}
  finally{setBusy(false);}
 }
 return <div className="dev-studio">
   <div className="page-heading"><span className="panel-kicker">RESEARCH INTEREST WATCHLIST</span>
    <h1>研究兴趣与计算机前沿</h1>
    <p>独立兴趣分支可以手动添加、暂停、试抓取；它们不会被自动当作团队已核验科研成果。</p></div>
   <div className="dev-sectionbar">
    <div><h2>关注主题</h2><p>数据保存在 PostgreSQL；每周抓取使用独立的 GitHub Actions 调度。</p></div>
    <div className="inline-actions"><button className="btn" disabled={busy} onClick={()=>void load()}><RefreshCw size={14}/> 刷新</button>
     {canEdit&&<button className="btn btn-primary" onClick={()=>setOpen(x=>!x)}><Plus size={14}/> 添加兴趣</button>}</div>
   </div>
   {error&&<div className="alert alert-error">{error}</div>}
   {notice&&<div className="alert alert-success"><CheckCircle2 size={14}/>{notice}</div>}
   {open&&canEdit&&<section className="panel dev-interest-form">
    <h3>新建监测分支</h3>
    <div className="dev-form-grid"><label>方向名称<input value={name} onChange={e=>setName(e.target.value)} placeholder="例如：图基础模型"/></label>
     <label>类型<select value={focus} onChange={e=>setFocus(e.target.value as Interest["focus"])}><option value="cs_frontier">计算机前沿</option><option value="cross_domain">跨领域方法</option><option value="applied">领域研究</option></select></label></div>
    <label>研究目标<textarea rows={2} value={goal} onChange={e=>setGoal(e.target.value)}/></label>
    <label>英文检索词（每行一条）<textarea rows={3} value={queries} onChange={e=>setQueries(e.target.value)}/></label>
    <label>关注会议（仅观察标签，目前不自动验证 venue）<input value={venues} onChange={e=>setVenues(e.target.value)}/></label>
    <div className="inline-actions"><button className="btn btn-primary" disabled={busy} onClick={()=>void create()}>保存分支</button>
      <button className="btn" onClick={()=>setOpen(false)}>取消</button></div>
   </section>}
   <div className="dev-watch-grid">
    {data===null?<div className="dev-empty">正在读取兴趣列表，或后端尚未部署新版本。</div>:
      data.items.length===0?<div className="dev-empty"><GitBranch size={20}/><strong>尚未添加兴趣</strong><p>从下方专题开始，或自行填写感兴趣的问题。</p></div>:
      data.items.map(item=><article className="dev-watch-card" key={item.id}>
        <div className="dev-watch-top"><span>{item.focus==="cs_frontier"?"计算机前沿":item.focus==="cross_domain"?"交叉方法":"领域研究"}</span>
          <span className={item.enabled?"dev-watch-on":"dev-watch-off"}>{item.enabled?"已开启":"已暂停"}</span></div>
        <h3>{item.title}</h3><p>{item.problem||"暂无目标描述"}</p><div className="dev-tags">{item.venues.map(v=><span key={v}>{v}</span>)}</div>
        <small>最后状态：{item.last_status} · 本轮新增 {item.last_new} 篇</small>
        <details className="dev-watch-detail"><summary>检索策略与真实论文</summary>
          {item.queries.map(q=><p key={q} className="dev-query">{q}</p>)}
          {item.recent_papers.length?item.recent_papers.map(p=><a key={p.id} href={p.url} target="_blank" rel="noopener noreferrer">{p.title} ↗</a>):<p className="small muted">尚未存入论文</p>}</details>
        {canEdit&&<div className="dev-watch-actions"><button className="btn btn-secondary" disabled={busy} onClick={()=>void action(item,"toggle")}>{item.enabled?"暂停":"恢复"}</button>
          <button className="btn btn-primary" disabled={busy||!item.enabled} onClick={()=>void action(item,"scan")}><Search size={13}/>试抓取</button></div>}
      </article>)}
   </div>
   <section className="dev-cs-section"><div className="dev-sectionbar"><div><h2>计算机领域学习模板</h2><p>这些是待关注专题，不是平台已经检索或审核的顶会论文。</p></div></div>
    <div className="dev-cs-grid">{presets.map(p=><div className="dev-cs-card" key={p.name}><span>CS FRONTIER</span><h3>{p.name}</h3>
     <div className="dev-tags">{split(p.venues,6).map(v=><small key={v}>{v}</small>)}</div>
     <p>{p.queries.split("\n")[0]}</p>
     {canEdit&&<button onClick={()=>{setName(p.name);setFocus("cs_frontier");setVenues(p.venues);setQueries(p.queries);setGoal("跟踪此计算机领域的研究进展，筛选可迁移方法。");setOpen(true);window.scrollTo({top:0,behavior:"smooth"});}}>创建兴趣分支 →</button>}</div>)}</div>
   </section>
   <p className="dev-final-note"><BookOpen size={14}/> 检索和阅读属于科研平台业务功能。开发进度控制台已迁移到独立网站，不再出现在本工作台。</p>
 </div>;
}