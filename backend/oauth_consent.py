"""Minimal, separate OAuth consent UI served directly by the Render FastAPI app.

No Next.js/Vercel dependency; external Research MCP remains disabled by
default. The browser handles Supabase OAuth sign-in and consent directly with
its public publishable API key. Never issue or store OAuth access tokens here.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response


router = APIRouter()


def _settings():
    if os.getenv("OAUTH_CONSENT_ENABLED", "").strip().lower() != "true":
        raise HTTPException(status_code=404, detail="Authorization page disabled")
    url = os.getenv("OAUTH_CONSENT_SUPABASE_URL", "").strip().rstrip("/")
    publishable = os.getenv("OAUTH_CONSENT_PUBLISHABLE_KEY", "").strip()
    u = urlparse(url)
    if (u.scheme != "https" or not u.hostname
            or not u.hostname.endswith(".supabase.co")
            or u.path not in ("", "/") or u.username or u.password
            or u.query or u.fragment
            or not re.fullmatch(r"sb_publishable_[A-Za-z0-9_-]{12,128}", publishable)):
        # Fail closed without leaking settings or secrets in the response.
        raise HTTPException(status_code=503, detail="Consent not configured")
    return url, publishable, u.hostname


HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Research Atlas | OAuth 授权</title>
<style>
:root{color-scheme:light;--ink:#16243a;--muted:#5e6d7e;--teal:#126a72}
*{box-sizing:border-box}body{margin:0;background:#f7f9fc;color:var(--ink);font-family:system-ui,-apple-system,"PingFang SC","Noto Sans SC",sans-serif;padding:5vh 16px}
main{max-width:570px;margin:0 auto;padding:32px;background:white;border:1px solid #e4e9ef;border-radius:16px;box-shadow:0 7px 20px #152d4910}
h1{font-size:24px;margin:14px 0}h2{font-size:18px}p{color:var(--muted);line-height:1.7}
#brand{font-size:12px;letter-spacing:.12em;color:var(--teal);font-weight:700}
label{display:block;margin:14px 0 6px;font-size:13px;font-weight:650}input[type=email],input[type=password]{padding:11px;border:1px solid #b9c6d2;border-radius:8px;width:100%;font-size:15px}
button{background:var(--teal);color:white;border:0;border-radius:8px;padding:11px 16px;font-weight:650;cursor:pointer;margin:6px 8px 6px 0}button.secondary{background:white;color:#34465e;border:1px solid #b5c4d0}
button:disabled{opacity:.5;cursor:not-allowed}.hidden{display:none!important}
#error{color:#a21d23}#notice{color:#166534}.client{background:#f4f7fa;border-radius:9px;padding:12px;overflow-wrap:anywhere}
small{font-size:12px;color:#718096}.muted{color:#66788b}
</style></head>
<body><main><div id="brand">RESEARCH ATLAS · 团队科研工作台</div>
<h1>科研顾问访问授权</h1>
<p>此页面专门用于确认 ChatGPT 等 OAuth 客户端的身份授权，和科研工作台管理前端相互独立。只有通过服务器白名单校验的账号与应用才能读取团队研究数据。</p>
<section id="checking"><p>正在检查授权请求和登录状态……</p></section>
<section id="login" class="hidden">
<h2>登录授权账户</h2>
<p>使用已登记在本项目 Supabase Authentication → Users 中的账户；原科研工作台的登录密码不通用。</p>
<label for="email">邮箱</label><input id="email" autocomplete="email" type="email" required>
<label for="password">Supabase Auth 密码（可选）</label><input id="password" autocomplete="current-password" type="password">
<div><button id="password-login">密码登录</button><button id="email-login" class="secondary">发送邮箱登录链接</button></div></section>
<section id="consent" class="hidden">
<h2>确认应用权限</h2><div class="client">
<div><b>申请应用：</b><span id="client-name"></span></div>
<div><b>回调地址：</b><span id="redirect-uri"></span></div>
<div><b>授权用户：</b><span id="user-email"></span></div>
<div><b>身份范围：</b><span id="scope"></span></div></div>
<p>这些 OAuth 范围主要提供身份验证。科研数据读取和提交仍受服务器端的用户与客户端白名单保护；人工评阅不能由 Agent 代填。</p>
<label><input type="checkbox" id="confirmed"> 我确认这是自己主动发起的连接，并已核对申请应用。</label>
<div><button id="approve" disabled>同意授权</button><button class="secondary" id="deny">拒绝授权</button></div>
</section>
<p id="notice" role="status"></p><p id="error" role="alert"></p>
<hr style="border:0;border-top:1px solid #e7edf3;margin-top:25px">
<small>请勿向此页面提供数据库密码、Supabase Secret Key 或 API service_role 密钥。如非本人发起，请选择拒绝。</small>
</main><script type="module" src="/oauth/consent/app.js"></script></body></html>"""


# Browser code is served by the same trusted origin to permit a restrictive CSP.
# The imported module is pinned. No untrusted user content is assigned via innerHTML.
JAVASCRIPT = r'''
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.86.0/+esm";
const cfg = __PUBLIC_SETTINGS__;
const supabase = createClient(cfg.url,cfg.key,{
  auth:{flowType:"pkce",persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}
});
const $ = id=>document.getElementById(id);
const authId = new URLSearchParams(location.search).get("authorization_id");
const setError = message => { $("error").textContent=message||""; };
const setNotice = message => { $("notice").textContent=message||""; };
const show = name => ["checking","login","consent"].forEach(x=>$(x).classList.toggle("hidden",x!==name));
let consentDetails=null;
async function load(){
  if (!authId || !/^[a-zA-Z0-9_-]{10,300}$/.test(authId)){
    setError("未找到有效 OAuth 授权请求。请从 ChatGPT 连接过程重新进入。");
    show("checking"); $("checking").textContent="授权请求无效。";
    return;
  }
  const {data:userData,error:userError}=await supabase.auth.getUser();
  if (userError || !userData?.user){show("login");return;}
  $("user-email").textContent=userData.user.email||"已登录用户";
  const {data,error}=await supabase.auth.oauth.getAuthorizationDetails(authId);
  if(error||!data){setError("授权请求已失效或无法读取，请重新发起连接。");show("checking");return;}
  if (!("authorization_id" in data)){
    // Supabase confirmed an earlier authorization: returned redirect is
    // generated by the trusted OAuth provider, never by query-string input.
    if(data.redirect_url){location.assign(data.redirect_url);return;}
    setError("授权响应无效。");return;
  }
  consentDetails=data;
  $("client-name").textContent=String(data.client?.name||"未知客户端");
  $("redirect-uri").textContent=String(data.redirect_uri||"");
  $("scope").textContent=String(data.scope||"未声明");
  show("consent");
}
async function signIn(method){
  setError("");setNotice("");
  const email=$("email").value.trim();
  if(!email){setError("请填写已登记的邮箱。");return;}
  $("password-login").disabled=$("email-login").disabled=true;
  try{
    if(method==="password"){
      const {error}=await supabase.auth.signInWithPassword({
        email,password:$("password").value
      });
      if(error)throw error;
      $("password").value="";
      await load();
    }else{
      const back=new URL(location.pathname+location.search,location.origin);
      const {error}=await supabase.auth.signInWithOtp({
        email,options:{shouldCreateUser:false,emailRedirectTo:back.toString()}
      });
      if(error)throw error;
      setNotice("邮箱登录链接已经请求发送，请检查邮件并由链接返回。");
    }
  }catch{setError("登录未成功。请确认邮箱已在 Supabase Authentication → Users 中登记。");}
  finally{$("password-login").disabled=$("email-login").disabled=false;}
}
async function decide(approve){
  if(!consentDetails || (approve && !$("confirmed").checked))return;
  $("approve").disabled=$("deny").disabled=true;
  setError("");
  try{
    const {data,error}=approve?
      await supabase.auth.oauth.approveAuthorization(authId):
      await supabase.auth.oauth.denyAuthorization(authId);
    if(error||!data?.redirect_url)throw new Error("OAuth error");
    location.assign(data.redirect_url);
  }catch{
    setError("处理授权失败，请重新从 ChatGPT 发起连接。");
    $("approve").disabled=!$("confirmed").checked;
    $("deny").disabled=false;
  }
}
$("password-login").addEventListener("click",()=>signIn("password"));
$("email-login").addEventListener("click",()=>signIn("otp"));
$("confirmed").addEventListener("change",()=>{$("approve").disabled=!$("confirmed").checked;});
$("approve").addEventListener("click",()=>decide(true));
$("deny").addEventListener("click",()=>decide(false));
load().catch(()=>{setError("授权服务器暂时无法访问。");show("checking");});
'''


def _headers(host):
    return {
        "Cache-Control": "no-store, private",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": (
            "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'unsafe-inline'; "
            f"connect-src https://{host}; "
            "img-src 'self'; form-action 'self'"
        ),
    }


@router.get("/oauth/consent", response_class=HTMLResponse, include_in_schema=False)
def consent_page():
    _, _, host = _settings()
    return HTMLResponse(HTML, headers=_headers(host))


@router.get("/oauth/consent/app.js", include_in_schema=False)
def consent_js():
    url, key, host = _settings()
    settings = json.dumps({"url": url, "key": key}, separators=(",", ":")).replace("<", "\\u003c")
    return Response(
        content=JAVASCRIPT.replace("__PUBLIC_SETTINGS__", settings),
        media_type="text/javascript",
        headers=_headers(host),
    )
