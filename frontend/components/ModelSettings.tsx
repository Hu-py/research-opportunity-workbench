"use client";

import {useCallback,useEffect,useState} from "react";
import {CheckCircle2,KeyRound,LockKeyhole,RefreshCw,ShieldCheck,Trash2} from "lucide-react";
import {api} from "@/lib/api";

type Budget={utc_day:string;limits:{themes_per_run:number;papers_per_day:number;model_calls_per_day:number;token_reservation_per_day:number;papers_per_theme:number};used:{model_calls:number;papers:number;token_reservation:number;input_tokens:number;output_tokens:number};notice:string};
type Config={
 provider:string;configured:boolean;vault_ready:boolean;
 fast_model:string;reason_model:string;daily_enabled:boolean;key_storage:string
};

export default function ModelSettings({canAdmin}:{canAdmin:boolean}){
 const [config,setConfig]=useState<Config|null>(null);
 const [budget,setBudget]=useState<Budget|null>(null);
 const [secret,setSecret]=useState("");
 const [reasonModel,setReasonModel]=useState("deepseek-v4-pro");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");

 const load=useCallback(async()=>{
   const result=await api<{config:Config;research_budget:Budget}>("ai-lab");
   setConfig(result.config);
   setBudget(result.research_budget);
   setReasonModel(result.config.reason_model);
 },[]);
 useEffect(()=>{void load().catch(e=>setError(e instanceof Error?e.message:String(e)));},[load]);

 async function save(fields:Record<string,unknown>){
   setBusy(true);setError("");setNotice("");
   try{
     await api("ai-lab/config",{method:"PUT",body:JSON.stringify(fields)});
     setSecret("");await load();
     setNotice("模型配置已安全保存。原始密钥不会回显。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function remove(){
   if(!window.confirm("确认移除已保存的 DeepSeek Key，并关闭每日自动分析？"))return;
   setBusy(true);setError("");setNotice("");
   try{
     await api("ai-lab/key",{method:"DELETE"});
     setSecret("");await load();setNotice("已移除密钥，每日自动分析已关闭。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }

 return <section className="panel">
   <div className="panel-header">
     <div><span className="panel-kicker">MODEL PROVIDER & API CREDENTIALS</span>
       <h2>DeepSeek 模型与 API Key</h2></div>
     <LockKeyhole size={20}/>
   </div>
   <p className="small muted">在这里统一配置文献语义分析与 AI 选题推理使用的 DeepSeek 服务。API Key 通过后端加密后存入 PostgreSQL，不会写入 GitHub、浏览器存储或前端环境变量。</p>
   {error&&<div className="alert alert-error">{error}</div>}
   {notice&&<div className="alert alert-success">{notice}</div>}
   <div className="ai-lab-status">
     <span className={config?.configured?"ai-lab-key-ready":"ai-lab-key-missing"}>
       {config?.configured?<CheckCircle2 size={15}/>:<KeyRound size={15}/>}
       {config?.configured?"DeepSeek Key 已加密保存":"尚未配置 DeepSeek Key"}
     </span>
     <span>服务器加密服务：{config?.vault_ready?"已启用":"未启用"}</span>
   </div>
   <div className="feedback-grid" style={{marginTop:18}}>
     <label>API 服务商
       <input value="DeepSeek" readOnly/>
     </label>
     <label>论文解析模型
       <input value={config?.fast_model||"deepseek-flash"} readOnly/>
     </label>
     <label>选题推理模型
       <select value={reasonModel} onChange={e=>setReasonModel(e.target.value)}>
         <option value="deepseek-v4-pro">DeepSeek V4 Pro（深入分析）</option>
         <option value="deepseek-flash">DeepSeek Flash（低成本试验）</option>
       </select>
     </label>
     <label>DeepSeek API Key
       <input type="password" value={secret} autoComplete="new-password"
         placeholder={config?.configured?"已配置；输入新 Key 可替换":"粘贴从 DeepSeek 开放平台获取的 API Key"}
         onChange={e=>setSecret(e.target.value)} maxLength={320}/>
     </label>
   </div>
   {canAdmin?<>
     <div className="inline-actions" style={{marginTop:16}}>
       <button className="btn btn-primary" disabled={busy||!config?.vault_ready||!secret.trim()}
         onClick={()=>void save({key:secret.trim(),reason_model:reasonModel})}>
         <KeyRound size={15}/> 保存 DeepSeek 配置
       </button>
       <button className="btn btn-secondary" disabled={busy||!config?.configured}
         onClick={()=>void remove()}><Trash2 size={14}/> 移除 Key</button>
       <button className="btn btn-secondary" disabled={busy}
         onClick={()=>void load()}><RefreshCw size={14}/> 刷新状态</button>
     </div>
     <label className="ai-lab-daily" style={{marginTop:18}}>
       <input type="checkbox" checked={Boolean(config?.daily_enabled)}
         disabled={busy||!config?.configured}
         onChange={e=>void save({daily_enabled:e.target.checked})}/>
       自动科研雷达：每日 5 个画像主题、最多 80 篇 LLM 语义分析，每周生成 AI 综合报告
     </label>
   </>:<p className="small muted">只有团队管理员可以新增、替换或移除 API Key，以及开启每日自动分析。</p>}
   {budget&&<div className="small-note" style={{marginTop:12}}>
     <strong>今日自动科研预算（UTC {budget.utc_day}）</strong>
     <p>已分析/预留论文 {budget.used.papers}/{budget.limits.papers_per_day} 篇 · 模型请求 {budget.used.model_calls}/{budget.limits.model_calls_per_day} 次 · Token 预留 {budget.used.token_reservation.toLocaleString()}/{budget.limits.token_reservation_per_day.toLocaleString()}</p>
     <p className="small muted">{budget.notice} 深度选题实验台的手动分析需另外注意调用成本。</p>
   </div>}
   {!config?.vault_ready&&<p className="small muted">需要先在 Render 后端服务配置 MODEL_VAULT_KEY 并重新部署，才能安全保存密钥。</p>}
   <div className="small-note"><ShieldCheck size={15}/> 安全说明：系统只返回密钥是否已配置，不返回密钥明文或密文。建议从 DeepSeek 官方开放平台创建专用 API Key。</div>
 </section>;
}
