import { getTeamToken, teamAuthEnabled } from "@/lib/session";
import { DEV_CENTER_HTML } from "@/lib/devstudio-approved-html";
import { DEV_CENTER_BRIDGE } from "@/lib/devstudio-live-bridge";
export const dynamic="force-dynamic";
export const runtime="nodejs";
const HEADERS:Record<string,string>={
  "Content-Type":"text/html; charset=utf-8",
  "Cache-Control":"private, no-store, max-age=0",
  "X-Content-Type-Options":"nosniff",
  "Referrer-Policy":"same-origin",
  "X-Frame-Options":"DENY",
};
function loginPage(message:string,status:number):Response{
  const escaped=message.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]||c));
  const html="<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Research Atlas · 开发者登录</title>\n<style>*{box-sizing:border-box}body{margin:0;background:#fcfcfb;color:#141414;font:13px/1.7 -apple-system,BlinkMacSystemFont,\"PingFang SC\",\"Microsoft YaHei\",sans-serif}.rail{position:fixed;left:0;top:0;bottom:0;width:64px;background:#111;color:white;padding:23px 15px;font-size:20px;font-weight:bold}main{min-height:100vh;margin-left:64px;display:grid;place-items:center;padding:24px}.box{background:white;border:1px solid #e6e6e6;border-radius:8px;width:min(100%,460px);padding:35px}.kicker{font-size:10px;letter-spacing:2px;color:#888;font-weight:700}h1{font-size:26px;margin:12px 0 6px}p{font-size:12px;color:#777;line-height:1.8}label{font-weight:600;display:block;margin-top:20px;font-size:12px}input{display:block;width:100%;margin-top:7px;padding:11px;border:1px solid #ddd;border-radius:6px;font:inherit}button{width:100%;border:0;border-radius:6px;padding:11px;background:#111;color:white;cursor:pointer;margin:22px 0 0}button:disabled{opacity:.5}.error{color:#a43836}a{color:#555}</style></head>\n<body><div class=\"rail\">RA</div><main><div class=\"box\"><div class=\"kicker\">RESEARCH ATLAS / DEVELOPMENT STUDIO</div><h1>开发者中心</h1><p>与科研前台使用同一个网站和团队身份，仅授权管理员可访问。</p><p class=\"error\" id=\"message\">__ERR__</p>\n<form id=\"login\"><label>成员邮箱<input name=\"email\" type=\"email\" required autocomplete=\"username\"></label><label>账号密码<input name=\"password\" type=\"password\" required autocomplete=\"current-password\"></label><button id=\"submit\" type=\"submit\">登录开发者中心</button></form>\n<p><a href=\"/research-atlas-v0.5.html?space=research&module=settings\">返回 Research Atlas</a></p></div></main>\n<script>document.getElementById(\"login\").addEventListener(\"submit\",async function(event){event.preventDefault();const btn=document.getElementById(\"submit\");const msg=document.getElementById(\"message\");btn.disabled=true;msg.textContent=\"\";const data=Object.fromEntries(new FormData(event.target).entries());try{const r=await fetch(\"/api/login\",{method:\"POST\",headers:{\"Content-Type\":\"application/json\"},body:JSON.stringify(data),cache:\"no-store\"});const x=await r.json();if(!r.ok)throw Error(x.detail||\"登录失败\");location.assign(\"/devstudio\");}catch(error){msg.textContent=error instanceof Error?error.message:\"身份服务暂不可用\";btn.disabled=false;}});</script></body></html>".replace("__ERR__",escaped);
  return new Response(html,{status,headers:HEADERS});
}
export async function GET():Promise<Response>{
  // Access must be verified by the backend; never trust mock HTML role switches.
  if(!teamAuthEnabled())return loginPage("此环境尚未启用团队身份认证，管理员入口已锁定。",503);
  const token=await getTeamToken();
  if(!token)return loginPage("请使用团队成员账号登录。",200);
  const base=process.env.BACKEND_URL,key=process.env.API_BEARER_TOKEN;
  if(!base||!key)return loginPage("团队身份服务尚未完成配置。",503);
  try{
    const response=await fetch(base.replace(/\/$/,"")+"/api/auth/me",{
      cache:"no-store",signal:AbortSignal.timeout(10000),
      headers:{"Authorization":"Bearer "+key,"X-Research-Session":token},
    });
    if(!response.ok)return loginPage("登录状态失效，请重新登录。",200);
    const data=await response.json();
    if(!data.member||data.member.role!=="admin"){
      return loginPage("当前账号没有开发者中心管理权限。",403);
    }
  }catch{return loginPage("暂时无法核实管理员权限，入口已安全锁定。",503);}
  const marker="\nrender();\n</script>";
  if(!DEV_CENTER_HTML.includes(marker))return new Response("Invalid developer UI template",{status:500});
  const html=DEV_CENTER_HTML
    .replace("当前 HTML 为设计原型，不代表已上线。","实际版本与研发结果以服务端登记的证据为准。")
    .replace("演示数据仅说明原型交互。上线后这四项统计需要读取统一的真实后台状态。","这里显示经过认证的研发后台记录，CI 与科研评审状态需分别验证。")
    .replace("当前页面是独立 HTML 原型。","当前页面属于 Research Atlas 同一个网站。")
    .replace("当前 HTML 未连接","服务端研发管理功能需独立验收")
    .replace(marker,"\n"+DEV_CENTER_BRIDGE+"\nrender();\nloadDevStudio();\n</script>");
  return new Response(html,{status:200,headers:HEADERS});
}
