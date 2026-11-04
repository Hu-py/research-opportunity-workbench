/* Research Atlas standalone engineering tracker.
   GitHub is the authoritative state store. No API tokens or private credentials. */
(() => {
"use strict";
const repo="Hu-py/research-opportunity-workbench";
const gh="https://api.github.com/repos/"+repo;
const src="https://github.com/"+repo;
const REFRESH_MS=10*60*1000;
const el=id=>document.getElementById(id);
const state={cfg:null,issues:null,prs:null,commits:null,runs:null,syncedAt:null,filters:{status:"all",track:"all",search:""},failures:[],loading:false};
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const trim=(s,n=250)=>String(s||"").length>n?String(s).slice(0,n-1)+"…":String(s||"");
const clock=s=>s?new Date(s).toLocaleString("zh-CN",{timeZone:"Asia/Shanghai",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}):"未知";
const textBlock=s=>trim(String(s||"").replace(/\[([^\]]+)\]\([^)]*\)/g,"$1").replace(/\*\*/g,"").replace(/\r/g,"").trim(),310);
const cleanIssueTitle=s=>String(s||"").replace(/^\[P[0-3]\]\s*/i,"");
function field(body,heading){
 const x=String(body||"");const re=new RegExp("(?:^|\\n)#{2,4}\\s*"+heading+"\\s*\\n([\\s\\S]*?)(?=\\n#{2,4}\\s|$)","i");
 return (x.match(re)||[])[1]?.trim()||"";
}
function acceptance(body){
 const content=field(body,"验收条件");
 const all=content.split("\n").filter(s=>/^-\s*\[[ xX]\]/.test(s.trim()));
 return {all:all.length,done:all.filter(x=>/\[[xX]\]/.test(x)).length,
   items:all.slice(0,3).map(x=>x.replace(/^\s*-\s*\[[ xX]\]\s*/,"").trim())};
}
function priority(issue,entry){
 return (String(issue?.title||"").match(/^\[(P[0-3])\]/i)||[])[1]?.toUpperCase()||entry?.priority||"P?";
}
function trackFor(issue,entry){
 if(entry?.track)return entry.track;
 const labels=(issue.labels||[]).map(x=>String(x.name).toLowerCase());
 const key=labels.find(x=>x.startsWith("track:"));
 return key?key.split(":")[1]:"backlog";
}
function statusFor(issue){
 if(issue.state==="closed")return {text:"已关闭 · 需核验",cls:"closed"};
 const names=(issue.labels||[]).map(x=>x.name.toLowerCase());
 if(names.includes("in progress")||names.includes("status:in-progress"))return {text:"开发中",cls:"open"};
 if(names.includes("blocked")||names.includes("status:blocked"))return {text:"阻塞中",cls:"open"};
 return {text:"开放任务",cls:"open"};
}
async function getJson(url){
 const ctl=new AbortController();
 const timer=setTimeout(()=>ctl.abort(),12500);
 try{
  const res=await fetch(url,{headers:{"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},signal:ctl.signal,cache:"no-store"});
  if(!res.ok){
   if(res.status===403||res.status===429)throw new Error("GitHub 查询受限（"+res.status+"），请稍后再刷新");
   throw new Error("HTTP "+res.status);
  }
  return await res.json();
 }finally{clearTimeout(timer);}
}
function setNumber(id,val){el(id).textContent=typeof val==="number"?val.toLocaleString("zh-CN"):"—";}
function syncNote(){
 const note=el("sync-notice"),hasIssue=Array.isArray(state.issues);
 note.className="warning "+(state.failures.length?"bad":hasIssue?"good":"");
 note.textContent=state.failures.length?
  "部分 GitHub 数据无法读取："+state.failures.join("；")+"。未读取到的状态保持未知，请勿按旧记录判定已完成。":
  hasIssue?"已连接 GitHub：研发状态以 Issues、PR、提交和 CI 实时记录为依据。任务关闭不等于科研效果验收。":
  "尚未获得 GitHub 实时任务数据。";
 el("last-sync").textContent=state.syncedAt?"更新于 "+clock(state.syncedAt):"同步未完成";
 el("sync-age").textContent=state.syncedAt?"最近成功请求 "+clock(state.syncedAt):"未取得完整源数据";
}
function renderMetrics(){
 const items=state.issues;
 setNumber("metric-total",items?.length);
 setNumber("metric-open",items?.filter(i=>i.state==="open").length);
 setNumber("metric-closed",items?.filter(i=>i.state==="closed").length);
 setNumber("metric-pr",state.prs?.filter(x=>x.state==="open").length);
}
function renderTracks(){
 const cfg=state.cfg;
 if(!cfg)return;
 el("track-grid").innerHTML=cfg.tracks.map((t,index)=>{
  const nums=cfg.milestones.filter(x=>x.track===t.id).map(x=>x.issue);
  const related=(state.issues||[]).filter(x=>nums.includes(x.number));
  const all=nums.length;
  const done=related.filter(x=>x.state==="closed").length;
  const percent=all?Math.round(done/all*100):0;
  return '<article class="track-card '+esc(t.color)+'"><div class="track-top"><span class="track-icon">'+["◇","▣","✧","⌁"][index%4]+'</span><span class="track-count">'+all+' 个规划节点</span></div>'
   +'<h3>'+esc(t.name)+'</h3><p>'+esc(t.desc)+'</p>'
   +'<div class="progress"><div style="width:'+(state.issues?percent:0)+'%"></div></div>'
   +'<div class="track-foot"><span>'+(state.issues?"GitHub 已关闭 "+done+" / "+all:"等待 GitHub 任务状态")+'</span><b>'+(state.issues?percent+"%":"—")+'</b></div></article>';
 }).join("");
}
function linkedPRs(no){
 if(!state.prs)return [];
 return state.prs.filter(p=>{
  const body=String(p.body||"");
  return new RegExp("(?:^|[^0-9])#"+no+"(?![0-9])").test(body);
 });
}
function card(issue){
 const entry=state.cfg?.milestones.find(x=>x.issue===issue.number);
 const trackId=trackFor(issue,entry);
 const track=state.cfg?.tracks.find(x=>x.id===trackId);
 const acc=acceptance(issue.body);
 const how=field(issue.body,"技术路径"),goal=field(issue.body,"目标"),example=field(issue.body,"结果示例");
 const name=cleanIssueTitle(issue.title);
 const files=(entry?.files||[]).map(p=>'<a target="_blank" rel="noopener noreferrer" href="'+src+'/blob/main/'+encodeURI(p)+'">'+esc(p)+'</a>').join("");
 const pull=linkedPRs(issue.number);
 return '<article class="task-card" data-issue="'+issue.number+'">'
  +'<div class="card-labels"><span class="badge badge-'+statusFor(issue).cls+'">'+esc(statusFor(issue).text)+'</span><span class="badge badge-prio">'+esc(priority(issue,entry))+'</span><span class="badge badge-domain">'+esc(track?.name||"其他任务")+'</span></div>'
  +'<h3 class="card-title">'+esc(name)+'</h3><p>'+esc(textBlock(goal||issue.body||"等待补充功能目标"))+'</p>'
  +'<div class="task-detail"><span>实现路径</span><div>'+esc(textBlock(how||"请在 Issue 填写技术路径"))+'</div></div>'
  +'<div class="task-detail"><span>验收条件</span><div>'+
     (acc.items.length?'<ul>'+acc.items.map(v=>'<li>'+esc(v)+'</li>').join("")+'</ul>':"等待定义可复查的验收标准")+
   (acc.all?' <small>勾选：'+acc.done+'/'+acc.all+'</small>':"")+'</div></div>'
  +'<div class="task-detail"><span>结果示例</span><div>'+esc(textBlock(example||entry?.suggestedResult||"等待补充验证结果链接"))+'</div></div>'
  +(pull.length?'<div class="task-detail"><span>关联 PR</span><div>'+pull.slice(0,3).map(p=>'<a href="'+esc(p.html_url)+'" target="_blank" rel="noopener noreferrer">#'+p.number+' '+esc(p.merged_at?"已合并":p.state)+'</a>').join(" · ")+'</div></div>':"")
  +(files?'<div class="card-files">'+files+'</div>':"")
  +'<div class="card-footer"><small>Issue #'+issue.number+' · 更新 '+clock(issue.updated_at)+'</small><a href="'+esc(issue.html_url)+'" target="_blank" rel="noopener noreferrer">查看任务 / 编辑证据 ↗</a></div></article>';
}
function renderTasks(){
 if(!state.issues){el("tasks-grid").innerHTML='<div class="placeholder">GitHub Issues 未读取成功。请重试或打开 GitHub 仓库查看任务。</div>';return;}
 let list=state.issues.slice();
 if(state.filters.status!=="all")list=list.filter(x=>x.state===state.filters.status);
 if(state.filters.track!=="all")list=list.filter(x=>trackFor(x,state.cfg?.milestones.find(e=>e.issue===x.number))===state.filters.track);
 const search=state.filters.search.trim().toLowerCase();
 if(search)list=list.filter(x=>{
  const entry=state.cfg?.milestones.find(e=>e.issue===x.number);
  return [x.number,x.title,x.body||"",...(entry?.files||[])].join(" ").toLowerCase().includes(search);
 });
 list.sort((a,b)=>{
  const p1=priority(a,state.cfg?.milestones.find(x=>x.issue===a.number));
  const p2=priority(b,state.cfg?.milestones.find(x=>x.issue===b.number));
  if(a.state!==b.state)return a.state==="open"?-1:1;
  if(p1!==p2)return p1.localeCompare(p2);
  return new Date(b.updated_at)-new Date(a.updated_at);
 });
 el("task-tally").textContent=list.length+" 条任务";
 el("tasks-grid").innerHTML=list.length?list.map(card).join(""):'<div class="placeholder">当前筛选下没有任务。</div>';
}
function renderActivity(){
 const all=state.runs||[];
 const main=all.filter(x=>x.head_branch==="main");
 const latest=main[0];
 if(!state.runs){el("ci-view").innerHTML='<p class="muted">尚未读取到 GitHub CI 结果。</p>';}
 else if(!latest){el("ci-view").innerHTML='<p class="muted">当前没有 main 分支的 CI 记录；不能断言测试通过。</p>';}
 else{
  const result=latest.conclusion||latest.status;
  const style=result==="success"?"success":result==="failure"?"failure":"pending";
  const dict={success:"通过",failure:"失败",queued:"排队中",in_progress:"进行中",cancelled:"已取消",timed_out:"超时",skipped:"跳过"};
  el("ci-view").innerHTML='<div class="ci-head"><span class="ci-pill '+style+'">'+(style==="success"?"● ":"◉ ")+esc(dict[result]||result)+'</span><small>'+clock(latest.created_at)+'</small></div>'
    +'<div class="ci-title">'+esc(latest.name||"CI")+' · '+esc(trim(latest.display_title||"main branch",90))+'</div>'
    +'<div class="ci-meta">分支 '+esc(latest.head_branch||"未知")+' · '+esc(String(latest.head_sha||"").slice(0,8))+' · Run #'+latest.run_number+'</div>'
    +'<div class="ci-steps"><span class="'+(style==="success"?"ok":style==="failure"?"bad":"running")+'">查看 CI 作业与测试细节 ↗</span></div>'
    +'<a class="subtle-link" href="'+esc(latest.html_url)+'" target="_blank" rel="noopener noreferrer">打开本次 Actions 运行记录 ↗</a>'
    +'<div class="ci-history">'+main.slice(1,4).map(x=>'<a target="_blank" rel="noopener noreferrer" href="'+esc(x.html_url)+'"><span>'+esc(x.conclusion||x.status)+' · '+esc(x.name)+'</span><time>'+clock(x.created_at)+'</time></a>').join("")+'</div>';
 }
 if(!state.commits){el("commit-view").innerHTML='<p class="muted">GitHub 提交记录暂不可读取。</p>';return;}
 el("commit-view").innerHTML=state.commits.slice(0,6).map(c=>{
  const message=(c.commit?.message||"").split("\n")[0];
  return '<div class="commit-item"><span class="commit-mark"></span><div><a href="'+esc(c.html_url)+'" target="_blank" rel="noopener noreferrer">'+esc(trim(message,85))+'</a>'
   +'<small>'+esc(c.sha.slice(0,8))+' · '+clock(c.commit?.committer?.date||c.commit?.author?.date)+'</small></div></div>';
 }).join("");
}
function renderShipped(){
 const cfg=state.cfg;if(!cfg)return;
 el("shipped-list").innerHTML=cfg.shipped.map(item=>{
  const pull=state.prs?.find(p=>p.number===item.pr);
  const merged=pull?.merged_at;
  const note=state.prs?(merged?"代码已合并":"需核对 PR 合并状态"):"GitHub PR 状态尚未同步";
  return '<div class="shipped-item"><span class="shipped-dot">✓</span><div><b>'+esc(item.title)+'</b><p>'+esc(item.note)+'</p>'
   +'<a href="'+(pull?esc(pull.html_url):src+"/pull/"+item.pr)+'" target="_blank" rel="noopener noreferrer">PR #'+item.pr+'</a>'
   +' <span class="'+(merged?"":"unverified")+'"> · '+esc(note)+'</span></div></div>';
 }).join("");
}
function renderAll(){syncNote();renderMetrics();renderTracks();renderTasks();renderActivity();renderShipped();}
async function loadConfig(){
 try{
  const r=await fetch("./roadmap.json",{cache:"no-store"});
  if(!r.ok)throw Error("HTTP "+r.status);
  state.cfg=await r.json();
  el("mission").textContent=state.cfg.mission;
  const opts=state.cfg.tracks.map(t=>'<option value="'+esc(t.id)+'">'+esc(t.name)+'</option>').join("");
  el("track-filter").insertAdjacentHTML("beforeend",opts);
  renderTracks();renderShipped();
 }catch(e){
  el("mission").textContent="开发目标配置暂不可读取，请检查 roadmap.json 文件。";
  el("sync-notice").textContent="开发目标文件读取失败："+e.message;
 }
}
async function reload(){
 if(state.loading)return;
 state.loading=true;el("refresh").disabled=true;
 state.failures=[];
 const parts=[
  ["issues",gh+"/issues?state=all&per_page=100&sort=updated"],
  ["prs",gh+"/pulls?state=all&per_page=60"],
  ["commits",gh+"/commits?sha=main&per_page=12"],
  ["runs",gh+"/actions/runs?branch=main&per_page=10"]
 ];
 const fetched=await Promise.allSettled(parts.map(x=>getJson(x[1])));
 fetched.forEach((res,i)=>{
  const key=parts[i][0];
  if(res.status==="fulfilled"){
   const arr=key==="runs"?res.value?.workflow_runs:res.value;
   state[key]=Array.isArray(arr)?(key==="issues"?arr.filter(x=>!x.pull_request):arr):null;
   if(!state[key])state.failures.push(key+"：返回格式无效");
  }else{
   state[key]=null;
   state.failures.push(key+"："+(res.reason?.message||"请求失败"));
  }
 });
 state.syncedAt=parts.some((_,i)=>fetched[i].status==="fulfilled")?new Date().toISOString():null;
 state.loading=false;el("refresh").disabled=false;renderAll();
}
function bind(){
 el("refresh").addEventListener("click",()=>reload());
 el("status-filters").addEventListener("click",e=>{
  const button=e.target.closest("button[data-state]");
  if(!button)return;
  state.filters.status=button.dataset.state;
  el("status-filters").querySelectorAll("button").forEach(x=>x.classList.toggle("active",x===button));
  renderTasks();
 });
 el("track-filter").addEventListener("change",e=>{state.filters.track=e.target.value;renderTasks();});
 el("task-search").addEventListener("input",e=>{state.filters.search=e.target.value;renderTasks();});
 document.querySelectorAll(".side-link").forEach(x=>x.addEventListener("click",()=>{
  document.querySelectorAll(".side-link").forEach(y=>y.classList.toggle("active",y===x));
 }));
 document.addEventListener("visibilitychange",()=>{
  if(document.visibilityState==="visible"&&(!state.syncedAt||Date.now()-new Date(state.syncedAt).getTime()>REFRESH_MS))reload();
 });
 window.setInterval(()=>{if(document.visibilityState==="visible")reload();},REFRESH_MS);
}
bind();
loadConfig().then(reload);
})();
