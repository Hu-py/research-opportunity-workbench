"""An authenticated HTML quickstart for the SC04 real DeepSeek pilot.

Hosted through the EXISTING Next.js /api/proxy route. It does not require a
new Vercel build and never receives or exposes bearer/session/LLM secrets.
GET is read-only; every paid action requires an explicit user-initiated POST.
"""
from fastapi.responses import HTMLResponse

PAGE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SC04-R1 · 真实 DeepSeek 探索实验</title>
<style>
:root{font-family:Arial,-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:#222;background:#fafafa}
*{box-sizing:border-box}body{margin:0;padding:30px 20px}main{max-width:1000px;margin:auto}
a{color:#333}small,.muted{color:#888}header{padding:15px 0 25px}h1{font-size:27px;margin:12px 0}h2{font-size:17px;margin:0 0 12px}h3{font-size:14px;margin:12px 0}
p{line-height:1.85;font-size:13px;color:#565656}
.box{background:white;border:1px solid #e6e6e6;border-radius:7px;padding:22px;margin-bottom:15px}
.stat{display:flex;flex-wrap:wrap;gap:16px;color:#555;font-size:13px;margin:13px 0}
.stat span{padding:10px;background:#f5f5f5;border-radius:4px}
button{font:inherit;font-size:13px;border:1px solid #d5d5d5;padding:11px 15px;cursor:pointer;color:#222;background:#fff;border-radius:4px}
button.primary{background:#171717;color:#fff;border-color:#171717}
button:disabled{opacity:.46;cursor:not-allowed}
label{display:flex;gap:8px;align-items:flex-start;font-size:13px;line-height:1.8;margin:13px 0}
input[type=checkbox]{margin-top:4px}.notice{background:#f7f7f7;border-left:3px solid #777;padding:12px 15px;font-size:12px;line-height:1.9}
#error{color:#a22;white-space:pre-wrap}#success{color:#315b3a}
.paper{padding:10px 0;border-bottom:1px solid #eee}a.link{font-size:12px;line-height:1.7}
article{padding:14px 0;border-bottom:1px solid #eee}article p{margin:7px 0}
q{font-size:12px;color:#666}strong{color:#111}code{background:#f4f4f4;padding:2px 4px}
.muted{font-size:11px}pre{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}
@media(max-width:600px){body{padding:12px}h1{font-size:23px}.box{padding:16px}}
</style></head>
<body><main>
<header>
<a href="/research/personal">← 返回个人科研画像</a>
<p class="muted">RESEARCH ATLAS / SC04-R1 / AUTHENTICATED OWNER ONLY</p>
<h1>儿童健康外推 · 真实 DeepSeek 探索实验</h1>
<p>使用你已批准目录内的实际 OpenAlex 论文摘要，执行论文理解、方法迁移和独立反证审查。本页面来自 Render 后端，经 Vercel 已登录代理访问，无需新建 Vercel 部署。</p>
</header>
<div class="notice"><strong>科学边界：</strong>第一轮允许仅 A 组来源；若研究基准尚未确认，会以“待本人核对的研究草稿”进入分析，不会被改写成正式成果。原论文尚未阅读全文、创新性未系统核验，输出仅供你评价模型的科研理解能力。</div>
<p id="error" role="alert"></p><p id="success" role="status"></p>
<section class="box">
<h2>01 · 检查真实证据与模型</h2>
<div id="stats" class="stat">正在读取你的私人实验数据……</div>
<div id="papers"></div>
<button type="button" id="refresh">刷新数据库状态</button>
</section>
<section class="box">
<h2>02 · 生成本轮真实论文快照</h2>
<p>只从已通过来源 ID 限定的期刊扫描中冻结 3–5 篇真实摘要，此操作不产生模型费用。</p>
<label><input type="checkbox" id="ack1">我已了解：这是一组真实摘要的探索预实验，研究基准和跨领域覆盖尚未完成正式核验。</label>
<button type="button" class="primary" id="prepare" disabled>创建 SC04-R1 探索实验（不调用模型）</button>
</section>
<section class="box">
<h2>03 · 明确授权 DeepSeek 三阶段分析</h2>
<p>三阶段：论文理解 → 方法比较与最多 3 个研究变体 → 独立反证审查。最多发起 3 次实际模型请求，受每日预算约束；模型调用可能计费，失败请求也可能产生费用。</p>
<div id="runinfo">尚未选择或创建实验。</div>
<label><input type="checkbox" id="ack2">我授权本次将公开论文摘要及暂定或已确认的研究基准发送给 Render 上配置的 DeepSeek API，并了解潜在费用。</label>
<button type="button" class="primary" id="start" disabled>正式调用 DeepSeek（最多 3 次）</button>
<button type="button" id="status">查看本轮执行状态</button>
</section>
<section class="box">
<h2>04 · 真实模型输出与可追溯结果</h2>
<div id="result"><p class="muted">运行后显示真实数据库保存的论文解读、研究变体和审查意见。绝不使用集成测试中的模拟模型回答。</p></div>
</section>
</main>
<script>
"use strict";
const BASE="/api/proxy/personal-research/me/evolution";
const $=id=>document.getElementById(id);
let current=null, overview=null, working=false;
const safe=(v)=>String(v??"");
function el(parent,tag,content,cls){
  const node=document.createElement(tag);
  if(content!==undefined)node.textContent=safe(content);
  if(cls)node.className=cls;
  parent.appendChild(node);return node;
}
function list(parent,title,items){
  const arr=Array.isArray(items)?items:[];
  if(!arr.length)return;
  const box=el(parent,"div");el(box,"strong",title);
  arr.forEach(x=>el(box,"p",x));
}
async function json(path="",method="GET",data){
  const response=await fetch(BASE+path,{method,credentials:"same-origin",cache:"no-store",
    headers:{"Content-Type":"application/json"},body:data===undefined?undefined:JSON.stringify(data)});
  let value={};try{value=await response.json()}catch{}
  if(!response.ok)throw Error(typeof value.detail==="string"?value.detail:"HTTP "+response.status);
  return value;
}
function message(error="",success=""){
  $("error").textContent=error;$("success").textContent=success;
}
async function reload(){
  try{
    overview=await json();
    const m=overview.model||{},e=overview.exploratory||{},scan=overview.evidence?.stats||{};
    const stats=$("stats");stats.replaceChildren();
    ["DeepSeek 密钥："+(m.configured&&m.vault_ready?"已配置":"未配置"),
     "严格来源检索论文："+safe(scan.total??0)+" 篇",
     "有摘要："+safe(scan.with_abstract??0)+" 篇",
     "本轮可选："+safe(e.preview_count??0)+" 篇",
     "目前探针："+safe((e.probes||[]).join("/")||"无"),
     "Owner 权限："+(e.owner_allowed?"已验证":"未授权")
    ].forEach(x=>el(stats,"span",x));
    const papers=$("papers");papers.replaceChildren();
    (overview.evidence?.papers||[]).forEach(p=>{
      const div=el(papers,"div",undefined,"paper");
      el(div,"span","探针 "+p.group+" · "+p.venue+" · ");
      const a=el(div,"a",p.title,"link");
      if(/^https:\/\//.test(p.url)){a.href=p.url;a.rel="noopener noreferrer";a.target="_blank"}
    });
    $("prepare").disabled=working||!e.owner_allowed||!e.ready||!$("ack1").checked;
    if(!current&&overview.runs?.length)current=overview.runs[0].id;
    await detail(false);
  }catch(e){message("读取失败："+safe(e.message))}
}
async function detail(showError=true){
  if(!current){$("runinfo").textContent="尚未创建实验";$("start").disabled=true;return;}
  try{
    const data=await json("/runs/"+encodeURIComponent(current));
    const r=data.run,info=$("runinfo");
    info.replaceChildren();
    el(info,"p","实验："+r.id+" · "+r.status+" / "+r.stage+" · 实际成功保存的模型调用："+r.model_calls);
    el(info,"p","摘要："+r.paper_count+" 篇 · 实际 token 输入："+r.input_tokens+" / 输出："+r.output_tokens);
    el(info,"p","模式："+r.experiment_mode+" · 研究基准正式确认："+(r.baseline_confirmed?"是":"否"));
    if(r.error)el(info,"p","执行错误："+r.error);
    $("start").disabled=working||!overview?.model?.configured||!overview?.model?.vault_ready||
       !$("ack2").checked||!["prepared","failed"].includes(r.status);
    $("start").textContent=r.status==="failed"?"授权并恢复失败阶段":"正式调用 DeepSeek（最多 3 次）";
    showResults(r);
  }catch(e){if(showError)message(safe(e.message))}
}
function showResults(r){
  const target=$("result");target.replaceChildren();
  if(!r.readings?.length&&!r.matches?.length&&!r.variants?.length){
    el(target,"p","暂无完成的论文理解；状态："+r.status+" · "+r.stage,"muted");return;
  }
  const papers=new Map((r.snapshot?.papers||[]).map(x=>[x.id,x]));
  if(r.readings?.length){
    el(target,"h3","一、论文理解（摘要级；模型抽取未经人工审阅）");
    r.readings.forEach(item=>{
      const article=el(target,"article"),p=papers.get(item.paper_id);
      if(p){const a=el(article,"a",p.title);a.href=p.url;a.target="_blank";a.rel="noopener noreferrer";}
      else el(article,"strong",item.paper_id);
      for(const [k,label] of [["problem","研究问题"],["method","方法"],["validation","验证"],["limitations","局限"],["evidence_excerpt","摘要原文摘录"]]){
        el(article,"p",label+"："+safe(item[k]));
      }
    });
  }
  if(r.matches?.length){
    el(target,"h3","二、方法适配评估");
    r.matches.forEach(m=>{
      const a=el(target,"article");
      el(a,"strong",m.method+" · "+m.compatibility);
      el(a,"p","适配机制："+m.mechanism);
      el(a,"p","需要比较的已有基线："+m.baseline_to_compare);
      el(a,"p","风险："+m.failure_risk);
      el(a,"p","证据论文 ID："+(m.paper_ids||[]).join("、"),"muted");
    });
  }
  if(r.variants?.length){
    el(target,"h3","三、研究变体（创新性尚未验证）");
    r.variants.forEach(v=>{
      const a=el(target,"article");el(a,"h3",v.id+" · "+v.title);
      el(a,"p","可证伪假设："+v.hypothesis);
      el(a,"p","要击败的基线："+v.baseline_to_beat);
      el(a,"p","最小实验："+v.minimal_test);
      el(a,"p","失败条件："+v.stop_condition);
      list(a,"需增加的数据",v.data_needed);
      list(a,"已知风险",v.risks);
      el(a,"p","依据论文："+(v.paper_ids||[]).join("、"),"muted");
      (r.critic||[]).filter(c=>c.variant_id===v.id).forEach(c=>{
        el(a,"strong","独立反证："+c.verdict);
        list(a,"主要反证",c.fatal_issues);
        el(a,"p","建议调整："+c.revised_test);
        el(a,"p","审查局限：仅比较本轮摘要，不是系统查新","muted");
      });
    });
  }
}
async function action(fn){
  if(working)return;working=true;message();
  try{await fn()}catch(e){message(safe(e.message))}
  finally{working=false;await reload()}
}
$("refresh").onclick=()=>action(async()=>{await reload()});
$("status").onclick=()=>action(async()=>{await detail()});
$("ack1").onchange=()=>{$("prepare").disabled=working||!overview?.exploratory?.ready||!$("ack1").checked};
$("ack2").onchange=()=>{void detail(false)};
$("prepare").onclick=()=>action(async()=>{
  if(!$("ack1").checked)throw Error("请先明确确认探索性局限");
  const r=await json("/exploratory/prepare","POST",{acknowledge_provisional_baseline:true});
  current=r.id;
  $("ack2").checked=false;
  message("","已创建真实论文快照，但未产生模型费用。");
});
$("start").onclick=()=>action(async()=>{
  if(!$("ack2").checked||!current)throw Error("请先明确授权 DeepSeek 调用");
  const r=await json("/runs/"+encodeURIComponent(current)+($("start").textContent.includes("恢复")?"/resume":"/start"),
     "POST",{acknowledge_external_model:true});
  message("","已提交模型分析请求；可以使用“查看本轮执行状态”核查真实执行记录。");
});
void reload();
setInterval(()=>{if(!working)void reload()},9000);
</script></body></html>"""


def quickstart_html():
    return HTMLResponse(
        PAGE,
        headers={
            "Cache-Control":"no-store, private",
            "X-Content-Type-Options":"nosniff",
            "Referrer-Policy":"no-referrer",
            "Content-Security-Policy":"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'self'",
        },
    )
