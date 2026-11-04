"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {
  ArrowRight,ArrowUpRight,BookOpen,CheckCircle2,ChevronDown,Clock3,
  Database,ExternalLink,GitBranch,Lightbulb,Loader2,Plus,
  RefreshCw,Search,ShieldCheck,Sparkles,Workflow,
} from "lucide-react";
import {api} from "@/lib/api";
import type {Overview} from "@/lib/types";

type Focus = "applied"|"cs_frontier"|"cross_domain";
type Status = "built"|"partial"|"planned";
type Feature = {
  id:string;track:"opportunity"|"frontier"|"foundation";
  name:string;goal:string;implementation:string;acceptance:string;
  status:Status;files:string[];navigate?:Destination;
};
type Destination="profile"|"repository"|"assets"|"discovery"|"ai-lab"|"ideas"|"brief"|"agent";
type Interest={
  id:string;title:string;focus:Focus;problem:string;keywords:string[];
  queries:string[];venues:string[];enabled:boolean;created_at:string;
  last_checked_at:string|null;last_status:string;last_new:number;
  recent_papers:{id:string;title:string;url:string;published:string;venue:string}[];
};
type InterestResponse={items:Interest[];note:string;weekly_schedule:string};
type DiscoveryResponse={
  candidates:{id:string;title:string;url:string;status:string;line_id:string;published:string}[];
  runs:{id:string;status:string;scanned:number;new_candidates:number;errors:string[]}[];
  strategies:{line_id:string;enabled:boolean}[];relations:{status:string}[];
};
type AIResponse={
  config:{configured:boolean;daily_enabled:boolean};
  runs:{status:string;stage:string;model_calls:number}[];
  cards:{title:string;status:string;id:string}[];
};
type Snapshot={
  overview:Overview|null;discovery:DiscoveryResponse|null;
  ai:AIResponse|null;interest:InterestResponse|null;errors:string[];
};
const base="https://github.com/Hu-py/research-opportunity-workbench/blob/main/";
const features:Feature[]=[
  {id:"data",track:"foundation",name:"团队成果与数据基础",
   goal:"以已核验成果、研究项目和非受限数据属性为事实依据",
   implementation:"PostgreSQL 成果档案 + CUSP 数据台账 + 审核关联",
   acceptance:"真实数据数量、来源 ID 与限制等级可追溯；不读取原始敏感文件",
   status:"built",files:["backend/repository.py","backend/cusp.py"],navigate:"assets"},
  {id:"profile",track:"foundation",name:"数据库证据驱动研究画像",
   goal:"根据真实数据库生成可核验的研究能力与方向，而非依据聊天记录",
   implementation:"证据清单 → 规则聚类/模型草稿 → 管理员审核 → 版本化发布",
   acceptance:"每条画像有真实成果或数据 ID；未审核草稿不改写正式画像",
   status:"partial",files:["backend/profile_database.py","backend/profile_intelligence.py"],navigate:"profile"},
  {id:"link",track:"opportunity",name:"数据—问题—方法关联",
   goal:"把团队可以研究的问题与可用数据、已有研究方法建立联系",
   implementation:"P0 候选关系匹配 → 人工确认 → 可追溯关系",
   acceptance:"关联有来源和置信说明；相似度不能冒充数据可用性",
   status:"built",files:["backend/discovery_links.py"],navigate:"discovery"},
  {id:"retrieval",track:"opportunity",name:"最新论文检索与候选池",
   goal:"按问题和可迁移方法双通道收集最新论文",
   implementation:"OpenAlex → 去重/元数据归一 → 规则初筛 → 人工审核",
   acceptance:"最近一次扫描有请求数、成功/失败状态和可打开的 DOI/来源",
   status:"partial",files:["backend/discovery_runner.py","backend/discovery.py"],navigate:"discovery"},
  {id:"analysis",track:"opportunity",name:"LLM 论文分析和选题生成",
   goal:"结合团队真实研究基础提出有证据、有基线、有风险提示的选题",
   implementation:"Planner → Paper Reader → Idea Generator → Critic",
   acceptance:"至少一轮真实模型完成四阶段；引用 ID 合法、实验和风险可审阅",
   status:"partial",files:["backend/ai_lab.py","backend/model_gateway.py"],navigate:"ai-lab"},
  {id:"ideas",track:"opportunity",name:"选题审核与演化",
   goal:"持续对研究假设进行筛选、反馈与迭代，而不是一次性给出标题",
   implementation:"规则候选/AI 草稿 → 人工反馈 → 版本与证据存档",
   acceptance:"选题能回溯所引论文、人工决策和修订记录",
   status:"partial",files:["research_workbench/core.py","backend/ai_lab.py"],navigate:"ideas"},
  {id:"interest",track:"frontier",name:"手动研究兴趣与分支",
   goal:"随时添加新研究问题、跨领域想法或计算机前沿专题",
   implementation:"独立兴趣表 → 结构化查询 → 周度补充扫描 → 分支文献",
   acceptance:"新增兴趣可跨会话保存、停用、试抓取并显示实际论文",
   status:"partial",files:["backend/interests.py","frontend/components/DevelopmentStudio.tsx"]},
  {id:"cs",track:"frontier",name:"计算机顶会与前沿学习",
   goal:"系统学习 AI、系统、数据库、HCI、机器人等方向的前沿方法",
   implementation:"领域观察目录和查询模板已加入；待实现 venue 验证及论文质量评估",
   acceptance:"可按学科/会议/年份筛选真实论文，记录阅读笔记与方法迁移卡",
   status:"partial",files:["backend/interests.py","frontend/components/DevelopmentStudio.tsx"]},
  {id:"weekly",track:"opportunity",name:"每周自动选题简报",
   goal:"每周汇总新增研究论文、计算机前沿与选题变化",
   implementation:"GitHub Actions weekly.yml → OpenAlex 增量检索 → PostgreSQL → Markdown/可选邮件",
   acceptance:"确认 Actions 已启用并连续成功运行，按分支展示增量论文与失败原因",
   status:"partial",files:[".github/workflows/weekly.yml","research_workbench/cli.py"],navigate:"brief"},
  {id:"knowledge",track:"frontier",name:"知识库与精读学习",
   goal:"积累文章理解、学习进度、知识节点和方法迁移经验",
   implementation:"后续接入 Zotero/全文许可阅读、嵌入检索、阅读笔记和知识图谱",
   acceptance:"至少一份可复查的论文全文解析和跨文章对比学习记录",
   status:"planned",files:["docs/ARCHITECTURE.md"]},
  {id:"evaluation",track:"opportunity",name:"选题质量评价与实验闭环",
   goal:"从研究意义、创新边界、团队适配、数据可行和计算预算评估选题",
   implementation:"证据矩阵 → 新颖性反证检索 → 最小可行实验 → 结果反馈",
   acceptance:"候选选题有同领域基线和可重复的否证/可行性试验",
   status:"planned",files:["docs/AI_RESEARCH_LAB_P2.md"]},
  {id:"delivery",track:"foundation",name:"稳定任务与每周交付",
   goal:"自动化任务有失败重试、成本监控、通知和可核查的交付历史",
   implementation:"现有任务/调度基础 → 独立 Worker/可靠队列 → 运行告警/邮件或其他推送",
   acceptance:"不依赖网页常开；成功/失败均可追踪，数据有备份",
   status:"partial",files:["backend/worker.py",".github/workflows/weekly.yml"],navigate:"brief"},
];
const focusLabel:Record<Focus,string>={
  applied:"领域研究",cs_frontier:"计算机前沿",cross_domain:"交叉方法",
};
const statusLabel:Record<Status,string>={
  built:"已有实现",partial:"部分实现",planned:"规划中",
};
const presets=[
  {title:"机器学习与表示学习",area:"CS · ML",venues:["NeurIPS","ICML","ICLR"],
   queries:["representation learning graph foundation models","self supervised learning scientific discovery"]},
  {title:"自然语言处理与智能体",area:"CS · NLP/Agents",venues:["ACL","EMNLP","NeurIPS"],
   queries:["language model agent planning evaluation","retrieval augmented generation agent benchmark"]},
  {title:"计算机视觉与多模态",area:"CS · CV",venues:["CVPR","ICCV","ECCV"],
   queries:["vision language model geospatial understanding","3D scene representation learning"]},
  {title:"数据挖掘与图学习",area:"CS · Data Mining",venues:["KDD","WWW","WSDM"],
   queries:["heterogeneous graph learning spatiotemporal","urban graph representation learning"]},
  {title:"数据库与数据系统",area:"CS · Database",venues:["SIGMOD","VLDB","ICDE"],
   queries:["vector database multimodal retrieval","data lakehouse query optimization"]},
  {title:"机器人与具身智能",area:"CS · Robotics",venues:["ICRA","IROS","RSS"],
   queries:["robot world model planning navigation","embodied agent task planning"]},
  {title:"人机交互与可视化",area:"CS · HCI/Vis",venues:["CHI","UIST","IEEE VIS"],
   queries:["human AI collaborative decision making","interactive visual analytics scientific discovery"]},
  {title:"系统与软件工程",area:"CS · Systems/SE",venues:["OSDI","SOSP","ICSE"],
   queries:["agentic software engineering evaluation","distributed systems autonomous agents"]},
  {title:"计算机安全与可信 AI",area:"CS · Security",venues:["IEEE S&P","USENIX Security","CCS"],
   queries:["privacy preserving machine learning","LLM agent security evaluation"]},
];

function splitTerms(raw:string,max:number){
  return Array.from(new Set(raw.split(/[\n,，;；]+/).map(x=>x.trim()).filter(Boolean))).slice(0,max);
}
function when(value:string|null|undefined){
  if(!value)return "尚无";
  const dt=new Date(value);
  return Number.isNaN(dt.getTime())?"未知":dt.toLocaleString("zh-CN",{dateStyle:"medium",timeStyle:"short"});
}
function count(value:number|undefined|null){
  return typeof value==="number"?value.toLocaleString("zh-CN"):"—";
}

export default function DevelopmentStudio({canEdit,onNavigate}:{
  canEdit:boolean;onNavigate:(destination:Destination)=>void;
}){
  const [data,setData]=useState<Snapshot>({overview:null,discovery:null,ai:null,interest:null,errors:[]});
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [feedback,setFeedback]=useState("");
  const [error,setError]=useState("");
  const [filter,setFilter]=useState<"all"|Status>("all");
  const [title,setTitle]=useState("");
  const [focus,setFocus]=useState<Focus>("cs_frontier");
  const [problem,setProblem]=useState("");
  const [keywords,setKeywords]=useState("");
  const [queries,setQueries]=useState("");
  const [venues,setVenues]=useState("");
  const [showForm,setShowForm]=useState(false);

  const load=useCallback(async()=>{
    setLoading(true);
    const paths=["overview","opportunity-engine","ai-lab","research-interests"];
    const results=await Promise.allSettled([
      api<Overview>(paths[0]),api<DiscoveryResponse>(paths[1]),
      api<AIResponse>(paths[2]),api<InterestResponse>(paths[3]),
    ]);
    const val=<T,>(idx:number):T|null=>results[idx].status==="fulfilled"?
      (results[idx] as PromiseFulfilledResult<T>).value:null;
    setData({overview:val<Overview>(0),discovery:val<DiscoveryResponse>(1),
      ai:val<AIResponse>(2),interest:val<InterestResponse>(3),
      errors:results.flatMap((result,index)=>result.status==="rejected"?
        [paths[index]+"："+(result.reason instanceof Error?result.reason.message:"读取失败")]:[])});
    setLoading(false);
  },[]);
  useEffect(()=>{void load();},[load]);
  const pending=useMemo(()=>data.interest?.items.some(x=>x.last_status==="queued")||false,[data.interest]);
  useEffect(()=>{
    if(!pending)return;
    const timer=setInterval(()=>{void load();},6000);
    return()=>clearInterval(timer);
  },[pending,load]);

  function usePreset(p:typeof presets[number]){
    setFocus("cs_frontier");setTitle(p.title);
    setProblem("持续学习"+p.title+"的新进展，筛选可迁移到团队研究问题的方法（兴趣假设，非既有成果）。");
    setKeywords(p.title);setQueries(p.queries.join("\n"));setVenues(p.venues.join(", "));
    setShowForm(true);
    document.getElementById("dev-interest-form")?.scrollIntoView({behavior:"smooth",block:"center"});
  }
  async function save(){
    setError("");setFeedback("");
    const parsed=splitTerms(queries,4);
    if(title.trim().length<3||parsed.length===0){
      setError("请填写不少于 3 个字符的名称和至少 1 条检索表达式。");return;
    }
    setBusy(true);
    try{
      await api("research-interests",{method:"POST",body:JSON.stringify({
        title:title.trim(),focus,problem:problem.trim(),keywords:splitTerms(keywords,12),
        queries:parsed,venues:splitTerms(venues,12),enabled:true,
      })});
      setFeedback("研究兴趣已独立保存到数据库。启用的分支会在已配置的每周工作流中参与抓取；当前不代表已完成自动运行。");
      setTitle("");setProblem("");setKeywords("");setQueries("");setVenues("");setShowForm(false);
      await load();
    }catch(e){setError(e instanceof Error?e.message:"保存失败");}
    finally{setBusy(false);}
  }
  async function toggle(row:Interest){
    setError("");setFeedback("");setBusy(true);
    try{
      await api("research-interests/"+encodeURIComponent(row.id),{
        method:"PATCH",body:JSON.stringify({enabled:!row.enabled})});
      setFeedback("已更新分支监测状态。");await load();
    }catch(e){setError(e instanceof Error?e.message:"更新失败");}
    finally{setBusy(false);}
  }
  async function scan(row:Interest){
    setBusy(true);setFeedback("");setError("");
    try{
      await api("research-interests/"+encodeURIComponent(row.id)+"/scan",
        {method:"POST",body:"{}"});
      setFeedback("本次试抓取已提交；检查扫描状态和实际论文记录以确认成功。");await load();
    }catch(e){setError(e instanceof Error?e.message:"试抓取失败");}
    finally{setBusy(false);}
  }
  const visible=features.filter(x=>filter==="all"||x.status===filter);
  const built=features.filter(x=>x.status==="built").length;
  const partial=features.filter(x=>x.status==="partial").length;
  const sample=data.discovery?.candidates.find(x=>x.status==="relevant"||x.status==="method")
    ||data.discovery?.candidates[0];
  const runs=data.discovery?.runs||[];
  const latest=runs[0];
  const completedAI=data.ai?.runs.filter(x=>x.status==="completed").length;
  const interestPapers=data.interest?.items.flatMap(x=>x.recent_papers.map(p=>({...p,branch:x.title})))||[];

  return <div className="dev-studio">
    <div className="page-heading dev-heading">
      <div><span className="panel-kicker">RESEARCH ATLAS · PRODUCT & DELIVERY MAP</span>
        <h1>开发总览与科研雷达规划</h1>
        <p>区分需求、实现方式、代码进展与真实运行证据。所有示例从当前数据库读取，不用虚构结果替代验证。</p></div>
      <button className="btn" onClick={()=>void load()} disabled={loading}>
        {loading?<Loader2 size={15} className="spin"/>:<RefreshCw size={15}/>}刷新运行证据
      </button>
    </div>
    {data.errors.length>0&&<div className="alert alert-error">
      部分实时指标暂不可用：{data.errors.join("；")}。以下代码状态不等于线上成功。
    </div>}
    <div className="dev-summary">
      <div><small>功能节点</small><strong>{features.length}</strong><span>目标与验收条件已列出</span></div>
      <div><small>代码已有实现</small><strong>{built}</strong><span>仍需结合运行验证</span></div>
      <div><small>部分实现 / 待打通</small><strong>{partial}</strong><span>当前主要开发工作</span></div>
      <div><small>已收录论文（数据库）</small><strong>{count(data.overview?.papers)}</strong><span>实时查询，不是模拟数据</span></div>
    </div>

    <section className="panel dev-pipelines">
      <div className="panel-header"><div><span className="panel-kicker">TWO CONNECTED RESEARCH LOOPS</span>
        <h2>平台要跑通的两条主线</h2></div></div>
      <div className="dev-pipeline">
        <div className="dev-pipe-title"><Database size={17}/><b>A · 科研机会发现</b><span>以真实团队研究基础为起点</span></div>
        <div className="dev-steps">
          {["已核验成果 / 数据属性","数据库证据画像","跨学科新论文","LLM 方法迁移 / 选题","人工评估 / 实验"].map((x,i)=>
            <div key={x} className="dev-step"><span>{String(i+1).padStart(2,"0")}</span><b>{x}</b>{i<4&&<ArrowRight size={15}/>}</div>)}
        </div>
      </div>
      <div className="dev-pipeline">
        <div className="dev-pipe-title"><BookOpen size={17}/><b>B · 计算机前沿学习</b><span>独立专题，但能反哺研究方向</span></div>
        <div className="dev-steps">
          {["领域 / 顶会观察清单","人工添加兴趣分支","每周检索与筛选","精读 / 方法知识库","匹配团队问题"].map((x,i)=>
            <div key={x} className="dev-step"><span>{String(i+1).padStart(2,"0")}</span><b>{x}</b>{i<4&&<ArrowRight size={15}/>}</div>)}
        </div>
      </div>
      <p className="small muted dev-footnote">当前顶会仅是人工维护的观察范围；OpenAlex 结果尚未做会议身份校验和论文优质性评价。两个主线不能混淆“关注兴趣”与“已核验团队能力”。</p>
    </section>

    <section className="dev-roadmap">
      <div className="dev-sectionbar"><div><span className="panel-kicker">DELIVERY STATUS</span>
        <h2>功能实现矩阵</h2><p>“已有实现”表示仓库具备对应代码；只有下方有真实运行记录，才可进一步判断能否正常工作。</p></div>
        <div className="dev-filters">
          {([["all","全部"],["built","已有实现"],["partial","部分实现"],["planned","规划中"]] as const).map(x=>
            <button key={x[0]} className={filter===x[0]?"active":""} onClick={()=>setFilter(x[0])}>{x[1]}</button>)}
        </div>
      </div>
      <div className="dev-feature-grid">
        {visible.map(item=><article className="dev-feature" key={item.id}>
          <div className="dev-feature-top"><span className={"dev-status dev-"+item.status}>{statusLabel[item.status]}</span>
            <span className="dev-track">{item.track==="opportunity"?"选题引擎":item.track==="frontier"?"前沿学习":"研究基础"}</span></div>
          <h3>{item.name}</h3><p>{item.goal}</p>
          <div className="dev-feature-info"><span>实现路径</span><div>{item.implementation}</div></div>
          <div className="dev-feature-info"><span>验收标准</span><div>{item.acceptance}</div></div>
          <div className="dev-feature-footer">
            <details><summary>代码依据 <ChevronDown size={13}/></summary>
              {item.files.map(file=><a key={file} href={base+file} target="_blank" rel="noopener noreferrer">
                <ExternalLink size={12}/>{file}</a>)}
            </details>
            {item.navigate&&<button className="dev-navigate" onClick={()=>onNavigate(item.navigate!)}>
              查看功能 <ArrowUpRight size={14}/></button>}
          </div>
        </article>)}
      </div>
    </section>

    <section className="panel dev-evidence">
      <div className="panel-header"><div><span className="panel-kicker">LIVE EVIDENCE · NOT MOCK DATA</span>
        <h2>运行证据与结果示例</h2></div><span className="dev-evidence-tip">更新于本次页面读取</span></div>
      <div className="dev-evidence-grid">
        <div><span>团队研究主线</span><b>{count(data.overview?.research_lines)}</b><small>来自正式研究画像</small></div>
        <div><span>登记数据集</span><b>{count(data.overview?.cusp_datasets)}</b><small>元数据，并非原始文件</small></div>
        <div><span>待审核论文</span><b>{count(data.discovery?.candidates.filter(x=>x.status==="pending").length)}</b><small>检索候选，未验证创新性</small></div>
        <div><span>已完成 AI 分析</span><b>{count(completedAI)}</b><small>必须核验模型输出内容</small></div>
        <div><span>手动兴趣分支</span><b>{count(data.interest?.items.length)}</b><small>与已核验团队能力独立</small></div>
      </div>
      <div className="dev-results">
        <div><h3><Search size={15}/> 最近检索</h3>
          {!latest?<p>暂无检索执行记录，尚不能判断抓取流程已跑通。</p>:<>
            <p>状态：<strong>{latest.status}</strong> · 扫描 {latest.scanned} 条 · 新增 {latest.new_candidates} 条候选</p>
            {latest.errors.length>0&&<p>本轮错误：{latest.errors[0]}</p>}
          </>}
          {sample&&<div className="dev-sample"><small>实际候选论文 · {sample.status}</small>
            <a href={sample.url} target="_blank" rel="noopener noreferrer">{sample.title}<ArrowUpRight size={13}/></a>
            <span>{sample.published||"发表日期待核验"}</span></div>}
        </div>
        <div><h3><Sparkles size={15}/> 选题实例</h3>
          {!data.ai?.cards.length?<p>暂无已保存的 AI 选题卡；不能把规划示例当作真实结果。</p>:
            <div className="dev-sample"><small>数据库中已有 {data.ai.cards.length} 条 AI 选题草稿</small>
              <strong>{data.ai.cards[0].title}</strong><span>审核状态：{data.ai.cards[0].status}</span>
            </div>}
          <p className="dev-small-notice">实际模型：{data.ai?.config.configured?"已保存模型凭证":"未确认已配置"}；仅当完整运行记录显示 completed 才视为执行完成。</p>
        </div>
      </div>
    </section>

    <section className="dev-interest-section">
      <div className="dev-sectionbar"><div><span className="panel-kicker">PERSONAL WATCHLIST · SHARED TEAM DATABASE</span>
        <h2>兴趣分支与每周论文追踪</h2>
        <p>把临时研究兴趣、计算机专题、交叉想法单独存储。启用后可加入周度文献抓取和简报，不修改正式团队科研画像。</p></div>
        {canEdit&&<button className="btn btn-primary" onClick={()=>setShowForm(x=>!x)}><Plus size={15}/>添加研究兴趣</button>}
      </div>
      {feedback&&<div className="alert alert-success">{feedback}</div>}
      {error&&<div className="alert alert-error">{error}</div>}
      <div id="dev-interest-form">
        {showForm&&canEdit&&<div className="panel dev-interest-form">
          <h3>新建研究兴趣</h3><p className="small muted">只输入可以公开检索的主题和关键词；不要在检索表达式中填写保密项目、未发表论文或数据路径。</p>
          <div className="dev-form-grid">
            <label>兴趣名称<input maxLength={180} value={title} onChange={e=>setTitle(e.target.value)} placeholder="例如：时空图基础模型"/></label>
            <label>研究类别<select value={focus} onChange={e=>setFocus(e.target.value as Focus)}>
              <option value="applied">领域研究</option><option value="cs_frontier">计算机前沿</option><option value="cross_domain">交叉方法</option>
            </select></label>
          </div>
          <label>核心问题 / 学习目标<textarea rows={2} value={problem} onChange={e=>setProblem(e.target.value)} placeholder="希望解决什么问题、学习什么方法？"/></label>
          <div className="dev-form-grid">
            <label>关键词（逗号分隔）<input value={keywords} onChange={e=>setKeywords(e.target.value)} placeholder="graph learning, spatiotemporal"/></label>
            <label>关注会议（可选，观察清单）<input value={venues} onChange={e=>setVenues(e.target.value)} placeholder="NeurIPS, ICLR, KDD"/></label>
          </div>
          <label>英文文献检索表达式（每行一条，最多 4 条；每轮最多执行前 2 条）
            <textarea rows={4} value={queries} onChange={e=>setQueries(e.target.value)} placeholder={"spatiotemporal graph foundation model\nurban graph representation learning"}/></label>
          <div className="inline-actions"><button className="btn btn-primary" disabled={busy||!canEdit} onClick={()=>void save()}>
            <CheckCircle2 size={15}/> 保存并加入周度关注</button>
            <button className="btn" onClick={()=>setShowForm(false)}>取消</button></div>
        </div>}
      </div>
      <div className="dev-watch-grid">
        {!data.interest?<div className="dev-empty">兴趣列表尚未读到，请检查后端是否已部署最新版本。</div>:
          data.interest.items.length===0?<div className="dev-empty">
            <GitBranch size={23}/><strong>还没有手动兴趣分支</strong>
            <p>先从下方计算机前沿目录选择一个专题，或点击“添加研究兴趣”。</p>
          </div>:
          data.interest.items.map(x=><article className="dev-watch-card" key={x.id}>
            <div className="dev-watch-top"><span>{focusLabel[x.focus]}</span>
              <span className={x.enabled?"dev-watch-on":"dev-watch-off"}>{x.enabled?"已加入监测":"已暂停"}</span></div>
            <h3>{x.title}</h3><p>{x.problem||"尚未填写学习目标"}</p>
            <div className="dev-tags">{x.venues.map(v=><span key={v}>{v}</span>)}</div>
            <small>最近扫描：{when(x.last_checked_at)} · {x.last_status} · 新增 {x.last_new} 篇</small>
            <details className="dev-watch-detail"><summary>检索词与实际论文 <ChevronDown size={13}/></summary>
              {x.queries.map(q=><p key={q} className="dev-query">{q}</p>)}
              {!x.recent_papers.length?<p className="small muted">尚无该兴趣的实际抓取结果。</p>:
                x.recent_papers.map(p=><a key={p.id} href={p.url} target="_blank" rel="noopener noreferrer">{p.title}<ArrowUpRight size={12}/></a>)}
            </details>
            {canEdit&&<div className="dev-watch-actions">
              <button className="btn btn-secondary" disabled={busy} onClick={()=>void toggle(x)}>{x.enabled?"暂停关注":"重新启用"}</button>
              <button className="btn btn-primary" disabled={busy||!x.enabled||x.last_status==="queued"} onClick={()=>void scan(x)}><Search size={13}/>试抓取</button>
            </div>}
          </article>)}
      </div>
      <p className="dev-weekly-note"><Clock3 size={16}/> 每周自动抓取依赖 <code>.github/workflows/weekly.yml</code> 的 <code>ENABLE_WEEKLY=true</code>、持久化 <code>DATABASE_URL</code> 和有效 OpenAlex 配置。此页面无法证明 GitHub Actions 已启用。新增兴趣不会立即触发付费 LLM。</p>
    </section>

    <section className="dev-cs-section">
      <div className="dev-sectionbar"><div><span className="panel-kicker">COMPUTER SCIENCE FRONTIER CURRICULUM</span>
        <h2>计算机前沿领域观察目录</h2><p>先建立广覆盖的领域目录，再针对团队问题筛选可迁移的新方法；会议是参考来源，不是已完成抓取的结果。</p></div>
      </div>
      <div className="dev-cs-grid">
        {presets.map(p=><article className="dev-cs-card" key={p.title}>
          <span>{p.area}</span><h3>{p.title}</h3>
          <div className="dev-tags">{p.venues.map(v=><small key={v}>{v}</small>)}</div>
          <p>{p.queries[0]}</p>
          {canEdit&&<button onClick={()=>usePreset(p)}>作为新兴趣添加 <ArrowRight size={14}/></button>}
        </article>)}
      </div>
    </section>
    <p className="dev-final-note"><ShieldCheck size={15}/> 成功标准：可证实的来源、可复现的运行、可审阅的研究价值。页面“代码实现”标签不是自动化验收报告；生产环境要以真实检索、周报成功执行和科研成员审核为准。</p>
  </div>;
