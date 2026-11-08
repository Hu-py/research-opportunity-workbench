"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { createBrowserClient } from "@supabase/ssr";

type AuthorizationDetails = {
  authorization_id: string;
  client: { name: string; [key: string]: unknown };
  redirect_uri: string;
  scope?: string;
};

function ConsentForm() {
  const search = useSearchParams();
  const authorizationId = search.get("authorization_id") || "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [details, setDetails] = useState<AuthorizationDetails | null>(null);
  const [state, setState] = useState<"checking"|"login"|"consent"|"redirecting"|"error">("checking");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [agree, setAgree] = useState(false);

  const configured = Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
  const supabase = useMemo(() => {
    if (!configured) return null;
    return createBrowserClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!
    );
  }, [configured]);

  const load = useCallback(async () => {
    if (!authorizationId || authorizationId.length > 300) {
      setError("缺少或无效的 OAuth 授权请求编号。请从 ChatGPT 的连接授权流程进入本页面。");
      setState("error");
      return;
    }
    if (!supabase) {
      setError("授权页面尚未配置 Supabase 的项目 URL 和公开 Publishable Key。请联系平台管理员。");
      setState("error");
      return;
    }
    setError("");
    const { data: userData, error: authError } = await supabase.auth.getUser();
    if (authError || !userData.user) {
      setDetails(null);
      setState("login");
      return;
    }
    setUserEmail(userData.user.email || "已登录用户");
    const { data, error: detailError } = await supabase.auth.oauth.getAuthorizationDetails(authorizationId);
    if (detailError || !data) {
      setError("无法验证 OAuth 授权请求。请回到 ChatGPT 重新发起连接。");
      setState("error");
      return;
    }
    if (!("authorization_id" in data)) {
      // Previously approved: Supabase returns an authoritative callback URL.
      setState("redirecting");
      window.location.assign(data.redirect_url);
      return;
    }
    setDetails({
      authorization_id: data.authorization_id,
      client: data.client,
      redirect_uri: data.redirect_uri,
      scope: data.scope || "",
    });
    setState("consent");
  }, [authorizationId, supabase]);

  useEffect(() => { void load(); }, [load]);

  async function login(method: "password"|"otp") {
    if (!supabase || busy) return;
    setError(""); setMessage(""); setBusy(true);
    try {
      if (method === "password") {
        if (!email || !password) throw new Error("请填写邮箱和密码");
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        setPassword("");
        await load();
      } else {
        if (!email) throw new Error("请填写已登记的团队邮箱");
        const redirect = new URL("/oauth/consent", window.location.origin);
        redirect.searchParams.set("authorization_id", authorizationId);
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: {
            shouldCreateUser: false,
            emailRedirectTo: redirect.toString(),
          }
        });
        if (error) throw error;
        setMessage("登录邮件已发送（或邮箱未注册）。请检查邮件并通过其中的链接返回。");
      }
    } catch {
      // Never expose identity-provider internals, tokens, or email details.
      setError("登录失败。请确认该邮箱已在 Supabase Authentication → Users 中登记，或检查密码。");
    } finally { setBusy(false); }
  }

  async function decide(approved: boolean) {
    if (!supabase || !details || busy) return;
    if (approved && !agree) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = approved
        ? await supabase.auth.oauth.approveAuthorization(authorizationId)
        : await supabase.auth.oauth.denyAuthorization(authorizationId);
      if (result.error || !result.data?.redirect_url) throw new Error("OAuth consent failed");
      setState("redirecting");
      window.location.assign(result.data.redirect_url);
    } catch {
      setError("授权处理失败。没有向 ChatGPT 授予新的访问权限，请重新发起授权。");
      setBusy(false);
    }
  }

  return (
    <main style={{ minHeight:"100vh", background:"#f7f9fc", padding:"54px 16px", color:"#172436" }}>
      <div style={{ maxWidth:560, margin:"auto", background:"white", border:"1px solid #e1e6eb", borderRadius:20, padding:"32px 30px", boxShadow:"0 10px 28px rgba(0,20,50,.05)" }}>
        <div style={{color:"#657589",fontSize:12,letterSpacing:"0.14em",fontWeight:700}}>RESEARCH ATLAS · 团队科研工作台</div>
        <h1 style={{fontSize:26,fontWeight:700,margin:"16px 0 10px"}}>团队科研顾问访问授权</h1>
        <p style={{color:"#526275",lineHeight:1.8,marginBottom:24}}>
          仅在你明确批准后，已登记的科研智能体客户端才可能访问经过筛选的团队科研元数据。
          本页面不会要求输入数据库密码或 ChatGPT API Key。
        </p>
        {state==="checking" && <p role="status">正在核验登录状态及授权请求…</p>}
        {state==="redirecting" && <p role="status">正在返回授权申请方…</p>}
        {state==="error" && <p role="alert" style={{color:"#b42318"}}>{error}</p>}
        {state==="login" && (
          <section>
            <h2 style={{fontSize:18,fontWeight:650,marginBottom:12}}>先登录 Supabase 授权账户</h2>
            <p style={{fontSize:13,color:"#657589",lineHeight:1.7,marginBottom:16}}>
              此账户与科研平台现有团队登录独立。必须使用管理员预先登记的 Supabase Auth 用户。
            </p>
            <label style={{display:"block",fontSize:13,fontWeight:600,marginBottom:6}}>邮箱地址</label>
            <input type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)}
              style={{width:"100%",padding:12,border:"1px solid #bbc5d0",borderRadius:8,marginBottom:14}} />
            <label style={{display:"block",fontSize:13,fontWeight:600,marginBottom:6}}>Supabase Auth 密码（可选）</label>
            <input type="password" autoComplete="current-password" value={password}
              onChange={e=>setPassword(e.target.value)}
              style={{width:"100%",padding:12,border:"1px solid #bbc5d0",borderRadius:8,marginBottom:16}} />
            <div style={{display:"flex",gap:10,flexWrap:"wrap"}}>
              <button disabled={busy} onClick={()=>void login("password")} style={primaryButton}>密码登录</button>
              <button disabled={busy} onClick={()=>void login("otp")} style={secondaryButton}>发送邮箱登录链接</button>
            </div>
            {message && <p role="status" style={{color:"#166534",marginTop:14}}>{message}</p>}
            {error && <p role="alert" style={{color:"#b42318",marginTop:14}}>{error}</p>}
          </section>
        )}
        {state==="consent" && details && (
          <section>
            <div style={{padding:16,background:"#f3f6fa",borderRadius:10,marginBottom:18}}>
              <p style={{fontWeight:650,marginBottom:6}}>申请应用：{String(details.client.name || "未知客户端")}</p>
              <p style={{fontSize:13,color:"#546477",overflowWrap:"anywhere"}}>回调地址：{details.redirect_uri}</p>
              <p style={{fontSize:13,color:"#546477",marginTop:8}}>当前授权用户：{userEmail}</p>
            </div>
            <p style={{fontWeight:600,marginBottom:6}}>身份范围（OAuth Scopes）</p>
            <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:14}}>
              {(details.scope || "email").split(/\s+/).filter(Boolean).map(item=>
                <span key={item} style={{fontSize:12,border:"1px solid #d8dfe7",borderRadius:20,padding:"5px 10px"}}>{item}</span>)}
            </div>
            <p style={{fontSize:13,color:"#526275",lineHeight:1.7}}>
              上述范围只控制身份信息。科研数据的实际访问权限由服务器端用户 ID、OAuth 客户端白名单和独立写入开关决定。
              默认仅允许读取经过筛选的论文及数据目录元数据，不允许访问原始私有数据文件；人工会议评审不能由智能体代填。
            </p>
            <label style={{display:"flex",gap:9,alignItems:"flex-start",margin:"20px 0",fontSize:13,lineHeight:1.7}}>
              <input type="checkbox" checked={agree} onChange={e=>setAgree(e.target.checked)} style={{marginTop:4}} />
              <span>我已经核对申请应用和回调地址，理解此授权将允许其向服务器提出科研元数据请求。</span>
            </label>
            {error && <p role="alert" style={{color:"#b42318"}}>{error}</p>}
            <div style={{display:"flex",gap:12}}>
              <button disabled={busy||!agree} onClick={()=>void decide(true)} style={primaryButton}>同意授权</button>
              <button disabled={busy} onClick={()=>void decide(false)} style={secondaryButton}>拒绝</button>
            </div>
          </section>
        )}
        <p style={{borderTop:"1px solid #edf0f3",paddingTop:16,marginTop:24,fontSize:12,color:"#8190a0",lineHeight:1.7}}>
          如果这次授权不是你主动发起的，请选择拒绝。授权后的访问仍受团队管理员设置控制，可在 Supabase 中撤销。
        </p>
      </div>
    </main>
  );
}
const primaryButton: React.CSSProperties={border:0,background:"#176b75",color:"white",padding:"11px 18px",borderRadius:9,fontWeight:650,cursor:"pointer"};
const secondaryButton: React.CSSProperties={background:"white",border:"1px solid #b7c2ce",color:"#24364b",padding:"11px 18px",borderRadius:9,fontWeight:600,cursor:"pointer"};

export default function OAuthConsentPage() {
  return <Suspense fallback={<main style={{padding:32}}>正在加载团队授权页面…</main>}>
    <ConsentForm/>
  </Suspense>;
}
