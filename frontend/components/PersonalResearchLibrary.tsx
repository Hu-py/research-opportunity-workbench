"use client";

import {useMemo,useState} from "react";
import {AlertCircle,ArrowUpRight,BookOpen,Check,FileText,Loader2,Plus,X} from "lucide-react";
import {api} from "@/lib/api";
import type {PersonalResearchAsset,PersonalResearchAssetKind,ResearchLine} from "@/lib/types";
import styles from "./PersonalResearchLibrary.module.css";

type Draft={
 kind:PersonalResearchAssetKind;
 title:string;
 summary:string;
 url:string;
 source_type:string;
 source_id:string;
 metadata:Record<string,unknown>;
 line_ids:string[];
};

const emptyDraft:Draft={
 kind:"publication",title:"",summary:"",url:"",
 source_type:"manual",source_id:"",metadata:{},line_ids:[],
};

const kindNames:Record<PersonalResearchAssetKind,string>={
 publication:"论文",
 agent_report:"智能体报告",
 experiment_result:"实验结果",
 project:"项目",
 dataset:"数据集",
 note:"研究笔记",
};

export default function PersonalResearchLibrary({
 assets,loaded,profileSaved,lines,onChange,
}:{
 assets:PersonalResearchAsset[];
 loaded:boolean;
 profileSaved:boolean;
 lines:ResearchLine[];
 onChange:(items:PersonalResearchAsset[])=>void;
}){
 const [open,setOpen]=useState(false);
 const [editingId,setEditingId]=useState<string|null>(null);
 const [metadataText,setMetadataText]=useState("{}");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [filter,setFilter]=useState<"all"|"publication"|"agent_report"|"experiment_result">("all");
 const [draft,setDraft]=useState<Draft>(emptyDraft);
 const [doi,setDoi]=useState("");
 const [taskId,setTaskId]=useState("");
 const filtered=useMemo(()=>assets.filter(item=>filter==="all"||item.kind===filter),[assets,filter]);
 const lineName=(id:string)=>lines.find(line=>line.id===id)?.name||id;

 async function refresh(){
  const result=await api<{items:PersonalResearchAsset[]}>("personal-assets");
  onChange(result.items||[]);
 }

 async function save(){
  if(!profileSaved){setError("请先保存个人研究画像，再录入关联资料。");return;}
  if(!draft.title.trim()){setError("请先填写资料标题。");return;}
  let metadata:Record<string,unknown>={};
  try{
   const parsed=JSON.parse(metadataText||"{}");
   if(!parsed||Array.isArray(parsed)||typeof parsed!=="object")throw new Error("元数据必须是 JSON 对象");
   metadata=parsed as Record<string,unknown>;
  }catch(cause){setError(cause instanceof Error?cause.message:"元数据 JSON 格式无效");return;}
  setBusy(true);setError("");setNotice("");
  try{
   const payload={...draft,metadata};
   const item=await api<PersonalResearchAsset>(
    editingId?"personal-assets/"+editingId:"personal-assets",
    {method:editingId?"PUT":"POST",body:JSON.stringify(payload)},
   );
   onChange([item,...assets.filter(row=>row.id!==item.id)]);
   setDraft(emptyDraft);setMetadataText("{}");setEditingId(null);setOpen(false);
   setNotice(editingId?"科研资料已更新。":"科研资料已保存到当前账号。");
  }catch(cause){setError(cause instanceof Error?cause.message:"资料保存失败");}
  finally{setBusy(false);}
 }

 function edit(item:PersonalResearchAsset){
  setEditingId(item.id);
  setDraft({
   kind:item.kind,title:item.title,summary:item.summary,url:item.url,
   source_type:item.source_type,source_id:item.source_id,
   metadata:item.metadata,line_ids:item.line_ids,
  });
  setMetadataText(JSON.stringify(item.metadata||{},null,2));
  setOpen(true);setError("");setNotice("");
 }
 async function importPaper(){
  if(!doi.trim())return;
  setBusy(true);setError("");setNotice("");
  try{
   const item=await api<PersonalResearchAsset>("personal-assets/import-paper",{
    method:"POST",body:JSON.stringify({doi:doi.trim(),line_ids:draft.line_ids}),
   });
   onChange([item,...assets.filter(row=>row.id!==item.id)]);
   setDoi("");setNotice("已从共用文献库导入论文。");
  }catch(cause){setError(cause instanceof Error?cause.message:"论文导入失败");}
  finally{setBusy(false);}
 }

 async function importTask(){
  if(!taskId.trim())return;
  setBusy(true);setError("");setNotice("");
  try{
   const item=await api<PersonalResearchAsset>("personal-assets/import-task",{
    method:"POST",body:JSON.stringify({task_id:taskId.trim(),line_ids:draft.line_ids}),
   });
   onChange([item,...assets.filter(row=>row.id!==item.id)]);
   setTaskId("");setNotice("已将研究任务结果快照加入个人资料库。");
  }catch(cause){setError(cause instanceof Error?cause.message:"任务报告导入失败");}
  finally{setBusy(false);}
 }

 async function archive(id:string){
  setBusy(true);setError("");setNotice("");
  try{
   await api("personal-assets/"+id,{method:"DELETE"});
   onChange(assets.filter(item=>item.id!==id));
   setNotice("资料已归档；原始论文或报告没有被删除。");
  }catch(cause){setError(cause instanceof Error?cause.message:"资料归档失败");}
  finally{setBusy(false);}
 }

 function toggleLine(id:string){
  setDraft(current=>({...current,line_ids:current.line_ids.includes(id)
   ?current.line_ids.filter(x=>x!==id):[...current.line_ids,id]}));
 }

 return <section className={styles.panel}>
  <div className={styles.heading}>
   <div><div className={styles.eyebrow}>PERSONAL RESEARCH LIBRARY</div><h2>个人科研资料库</h2></div>
   <span className={styles.count}>{loaded?assets.length+" 条资料":"连接中"}</span>
  </div>
  <p className={styles.description}>
   论文、智能体报告、实验结果和数据集独立存入当前账号，并关联个人研究主线。数据库保存元数据与来源引用；原始 PDF 和大文件仍保留在 Library / 对象存储。
  </p>
  {!loaded?<div className={styles.message}><AlertCircle size={15}/>个人资料库 API 尚不可用，请确认新版后端已部署。</div>:<>
   <div className={styles.toolbar}>
    <div className={styles.filters}>
     {(["all","publication","agent_report","experiment_result"] as const).map(value=><button key={value}
      className={filter===value?styles.filterActive:""} onClick={()=>setFilter(value)} type="button">
      {value==="all"?"全部":kindNames[value]}
     </button>)}
    </div>
    <button className={styles.addButton} type="button" onClick={()=>setOpen(value=>!value)}>
     <Plus size={14}/>{open?"收起录入":"新增资料"}
    </button>
   </div>
   <div className={styles.assetList}>
    {filtered.length?filtered.map(item=><article className={styles.asset} key={item.id}>
     <div className={styles.assetTop}>
      <div className={styles.assetTitle}><strong>{item.title}</strong><span>{kindNames[item.kind]}</span></div>
      <div className={styles.rowActions}>
       <button type="button" className={styles.archive} disabled={busy} onClick={()=>edit(item)}>编辑</button>
       <button type="button" className={styles.archive} disabled={busy} onClick={()=>void archive(item.id)}>归档</button>
      </div>
     </div>
     {item.summary&&<p>{item.summary}</p>}
     <div className={styles.assetMeta}>
      <span>来源：{item.source_type}{item.source_id?" · "+item.source_id:""}</span>
      {item.line_ids.length>0&&<span>主线：{item.line_ids.map(lineName).join("、")}</span>}
     </div>
     {item.url&&<a href={item.url} target="_blank" rel="noreferrer">打开原始资料 <ArrowUpRight size={12}/></a>}
    </article>):<div className={styles.empty}>
     <BookOpen size={19}/><strong>这个分类暂时没有资料</strong>
     <span>可以新增资料，或从共用文献库和 Research Atlas 任务导入</span>
    </div>}
   </div>
   {open&&<div className={styles.editor}>
    <div className={styles.subhead}><h3>{editingId?"编辑个人科研资料":"新增个人科研资料"}</h3><span>仅当前账号可见</span></div>
    <div className={styles.grid}>
     <label>资料类型<select value={draft.kind} onChange={e=>setDraft(x=>({...x,kind:e.target.value as PersonalResearchAssetKind}))}>
      <option value="publication">论文</option><option value="agent_report">智能体报告</option>
      <option value="experiment_result">实验结果</option><option value="project">项目</option>
      <option value="dataset">数据集</option><option value="note">研究笔记</option>
     </select></label>
     <label>标题<input value={draft.title} onChange={e=>setDraft(x=>({...x,title:e.target.value}))} placeholder="论文、报告或实验名称"/></label>
     <label>来源类型<select value={draft.source_type} onChange={e=>setDraft(x=>({...x,source_type:e.target.value}))}>
      <option value="manual">手动录入</option><option value="doi">DOI</option>
      <option value="openalex_work">OpenAlex 论文</option><option value="chatgpt_space_page">ChatGPT 报告页</option>
      <option value="sc05_run">SC05 实验运行</option><option value="research_task">Research Atlas 任务</option>
      <option value="library_file">Library 文件</option><option value="external_url">外部链接</option>
     </select></label>
     <label>来源记录 ID<input value={draft.source_id} onChange={e=>setDraft(x=>({...x,source_id:e.target.value}))} placeholder="DOI、Run ID、Page ID 等"/></label>
    </div>
    <label className={styles.full}>原始链接<input value={draft.url} onChange={e=>setDraft(x=>({...x,url:e.target.value}))} placeholder="https://..."/></label>
    <label className={styles.full}>摘要 / 主要结果<textarea rows={3} value={draft.summary} onChange={e=>setDraft(x=>({...x,summary:e.target.value}))} placeholder="记录研究贡献、实验设置、核心结果或证据状态"/></label>
    <label className={styles.full}>结构化元数据（JSON，可选）
     <textarea rows={3} value={metadataText} onChange={e=>setMetadataText(e.target.value)} placeholder='{"blind_score":70,"status":"hold"}'/>
    </label>
    <div className={styles.subhead}><h3>关联个人研究主线</h3><span>可多选</span></div>
    <div className={styles.lineChoices}>
     {lines.map(line=><label key={line.id}><input type="checkbox" checked={draft.line_ids.includes(line.id)} onChange={()=>toggleLine(line.id)}/><span>{line.name}</span></label>)}
    </div>
    <div className={styles.actions}>
     <button type="button" className={styles.cancel} onClick={()=>setOpen(false)}>取消</button>
     <button type="button" className={styles.save} disabled={busy||!draft.title.trim()||!profileSaved} onClick={()=>void save()}>
      {busy?<Loader2 size={14} className={styles.spin}/>:<Check size={14}/>}{editingId?"保存修改":"保存资料"}
     </button>
    </div>
   </div>}
   <div className={styles.imports}>
    <div className={styles.subhead}><h3>从已有记录导入</h3><span>建立个人私有引用</span></div>
    <div className={styles.lineChoices}>
     {lines.map(line=><label key={line.id}><input type="checkbox" checked={draft.line_ids.includes(line.id)} onChange={()=>toggleLine(line.id)}/><span>{line.name}</span></label>)}
    </div>
    <div className={styles.grid}>
     <label>共用文献库 DOI<input value={doi} onChange={e=>setDoi(e.target.value)} placeholder="10.xxxx/xxxxx"/>
      <button type="button" className={styles.importButton} disabled={busy||!doi.trim()||!profileSaved} onClick={()=>void importPaper()}><BookOpen size={13}/>导入论文</button>
     </label>
     <label>Research Atlas 任务 ID<input value={taskId} onChange={e=>setTaskId(e.target.value)} placeholder="任务 ID"/>
      <button type="button" className={styles.importButton} disabled={busy||!taskId.trim()||!profileSaved} onClick={()=>void importTask()}><FileText size={13}/>导入报告</button>
     </label>
    </div>
    <p>导入只会在个人资料库建立私有引用或结果快照，不会删除、移动或修改共用文献、团队任务和原始实验记录。SC05 外部实验可通过“新增资料”登记 Run ID 与结果摘要。</p>
   </div>
   {error&&<div className={styles.error}><AlertCircle size={14}/>{error}</div>}
   {notice&&<div className={styles.notice}><Check size={14}/>{notice}</div>}
  </>}
 </section>;
}
