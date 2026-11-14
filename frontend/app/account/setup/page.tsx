"use client";

import { FormEvent, useEffect, useState } from "react";

type Mode = "owner" | "reset" | "redeem";
type ServerMessage = { detail?: string; message?: string; ok?: boolean };

export default function AccountSetup() {
  const [mode, setMode] = useState<Mode>("owner");
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);
  useEffect(() => {
    const fragment = new URLSearchParams(location.hash.replace(/^#/, ""));
    const supplied = fragment.get("token") || "";
    if (supplied) {
      setToken(supplied);
      setMode("redeem");
      // Remove fragment from browser history after reading the one-time secret.
      history.replaceState(null, "", location.pathname);
    } else if (new URLSearchParams(location.search).get("mode") === "reset") {
      setMode("reset");
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setSuccess(false);
    if (mode === "redeem" && password !== confirm) {
      setMessage("两次密码不一致");
      return;
    }
    setPending(true);
    const operation = mode === "redeem" ? "redeem" : mode === "reset" ? "reset_request" : "owner_request";
    const payload = mode === "redeem" ? { token, password } : { email };
    try {
      const response = await fetch("/api/account/onboarding", {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operation, ...payload }),
      });
      const result = (await response.json()) as ServerMessage;
      if (!response.ok) throw new Error(result.detail || "操作失败");
      setSuccess(true);
      setMessage(result.message || "操作已完成");
      setPassword("");
      setConfirm("");
      setToken("");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "无法访问账户服务");
    } finally {
      setPending(false);
    }
  }

  return (
    <main style={{ minHeight:"100vh", background:"#fcfcfb", display:"grid",
                   placeItems:"center", padding:24, color:"#141414" }}>
      <section style={{ background:"#fff", width:"min(100%,460px)", padding:30,
                        border:"1px solid #e5e5e5", borderRadius:8 }}>
        <div style={{ fontSize:11, color:"#777", letterSpacing:"0.08em" }}>
          RESEARCH ATLAS / ACCOUNT
        </div>
        <h1 style={{ fontSize:24, margin:"14px 0 6px" }}>
          {mode==="redeem" ? "验证邮箱并设置密码" : mode==="reset" ? "重置账户密码" : "首次 Owner 账户开通"}
        </h1>
        <p style={{ color:"#777", lineHeight:1.8, fontSize:13, marginBottom:22 }}>
          {mode==="redeem"
            ? "验证链接仅可使用一次。设置完成后，使用邮箱和新密码登录。"
            : mode==="reset"
              ? "如果邮箱已注册，系统会发送限时密码重置链接。"
              : "只有系统预先指定的 Owner 邮箱可以完成首次开通。请检查该邮箱收件箱。"}
        </p>
        <form onSubmit={submit}>
          {mode==="redeem" ? (
            <>
              <label style={{ display:"block", fontSize:13, marginBottom:12 }}>
                新密码（至少 12 个字符）
                <input type="password" required minLength={12} maxLength={256}
                  autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)}
                  style={{display:"block",width:"100%",padding:11,marginTop:7,border:"1px solid #ddd"}}/>
              </label>
              <label style={{ display:"block", fontSize:13, marginBottom:12 }}>
                再次输入新密码
                <input type="password" required minLength={12} maxLength={256}
                  autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)}
                  style={{display:"block",width:"100%",padding:11,marginTop:7,border:"1px solid #ddd"}}/>
              </label>
            </>
          ) : (
            <label style={{ display:"block", fontSize:13, marginBottom:12 }}>
              账户邮箱
              <input type="email" required value={email} onChange={e=>setEmail(e.target.value)}
                autoComplete="email" placeholder="you@example.com"
                style={{display:"block",width:"100%",padding:11,marginTop:7,border:"1px solid #ddd"}}/>
            </label>
          )}
          <button disabled={pending || (mode==="redeem"&&!token)} type="submit"
            style={{background:"#111",color:"#fff",border:0,padding:12,width:"100%",
                    borderRadius:5,marginTop:8,cursor:"pointer"}}>
            {pending?"正在提交…":mode==="redeem"?"验证并设置密码":"发送邮箱验证链接"}
          </button>
        </form>
        {message && <p role="status" style={{color:success?"#235e42":"#9a3838",marginTop:16,fontSize:13}}>
          {message}
        </p>}
        <div style={{display:"flex",gap:16,flexWrap:"wrap",marginTop:24,fontSize:12}}>
          <a href="/devstudio" style={{color:"#555"}}>返回登录</a>
          {mode!=="redeem" && <button type="button" onClick={()=>{setMode(mode==="reset"?"owner":"reset");setMessage("");}}
             style={{background:"none",border:0,padding:0,cursor:"pointer",color:"#555"}}>
            {mode==="reset"?"首次 Owner 开通":"忘记密码"}
          </button>}
        </div>
      </section>
    </main>
  );
}
