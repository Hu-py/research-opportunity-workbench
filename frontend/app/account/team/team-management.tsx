"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";

type Member = {id:string; email:string; name:string; role:string; active:boolean};
type Invitation = {id:string; email:string; name:string; role:string; status:string; expires_at:number};
type ApiError = {detail?:string};
const ink="#141414", border="1px solid #e8e8e8";

async function request<T>(path:string, options?:RequestInit):Promise<T>{
  const res=await fetch("/api/proxy/"+path,{...options,cache:"no-store",
    headers:{"Content-Type":"application/json",...(options?.headers||{})}});
  if(!res.ok){const error=await res.json().catch(()=>({})) as ApiError;
    throw new Error(error.detail || "请求失败 (HTTP "+res.status+")");}
  return res.json() as Promise<T>;
}

export default function TeamManagement({currentRole}:{currentRole:string}){
  const [members,setMembers]=useState<Member[]>([]);
  const [invitations,setInvitations]=useState<Invitation[]>([]);
  const [email,setEmail]=useState("");
  const [name,setName]=useState("");
  const [role,setRole]=useState("researcher");
  const [loading,setLoading]=useState(true);
  const [sending,setSending]=useState(false);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");

  const reload=useCallback(async()=>{
    setLoading(true);
    try{
      const [m,i]=await Promise.all([
        request<{items:Member[]}>("team/members"),
        request<{items:Invitation[]}>("team/invitations"),
      ]);
      setMembers(m.items||[]);
      setInvitations(i.items||[]);
      setError("");
    }catch(e){setError(e instanceof Error?e.message:"加载失败");}
    finally{setLoading(false);}
  },[]);
  useEffect(()=>{void reload();},[reload]);

  async function invite(e:FormEvent<HTMLFormElement>){
    e.preventDefault();setSending(true);setError("");setMessage("");
    try{
      const result=await request<{message:string}>("team/invitations",{
        method:"POST",body:JSON.stringify({email,name,role}),
      });
      setMessage(result.message);
      setEmail("");setName("");
      await reload();
    }catch(err){setError(err instanceof Error?err.message:"邀请失败");}
    finally{setSending(false);}
  }

  async function updateMember(m:Member,action:"role"|"active",value:string|boolean){
    const payload=action==="role"?{role:value}:{active:value};
    const label=action==="active"?(value?"重新启用":"停用"):"变更角色";
    if(!confirm("确定要"+label+" "+m.email+" 吗？"))return;
    setError("");setMessage("");
    try{
      await request("team/members/"+encodeURIComponent(m.id),{
        method:"PATCH",body:JSON.stringify(payload),
      });
      setMessage("成员设置已保存，并已进入审计日志");
      await reload();
    }catch(err){setError(err instanceof Error?err.message:"更新失败");}
  }

  const input={width:"100%",padding:10,border,borderRadius:5,background:"#fff"} as const;
  const panel={border,background:"#fff",borderRadius:8,padding:22,marginTop:20} as const;
  return <main style={{background:"#fcfcfb",minHeight:"100vh",color:ink,padding:"30px min(5vw,60px)"}}>
    <div style={{maxWidth:1000,margin:"auto"}}>
      <a href="/devstudio" style={{color:"#777",fontSize:12}}>返回 Development Studio</a>
      <h1 style={{fontSize:26,margin:"15px 0 6px"}}>团队成员与邀请</h1>
      <p style={{fontSize:13,color:"#777",lineHeight:1.8}}>
        管理员发送邮箱邀请，成员通过验证链接自行设置密码。Owner 权限不能通过普通角色编辑授予。
      </p>
      {error&&<p role="alert" style={{color:"#a23b32"}}>{error}</p>}
      {message&&<p role="status" style={{color:"#246343"}}>{message}</p>}
      <section style={panel}>
        <h2 style={{fontSize:17,margin:"0 0 16px"}}>邀请新成员</h2>
        <form onSubmit={invite} style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(190px,1fr))",gap:12}}>
          <label style={{fontSize:12}}>邮箱<input style={{...input,marginTop:6}} type="email" required
            value={email} onChange={e=>setEmail(e.target.value)} placeholder="member@example.com"/></label>
          <label style={{fontSize:12}}>成员名称<input style={{...input,marginTop:6}} required minLength={2}
            value={name} onChange={e=>setName(e.target.value)}/></label>
          <label style={{fontSize:12}}>角色<select style={{...input,marginTop:6}} value={role}
            onChange={e=>setRole(e.target.value)}>
            <option value="researcher">Researcher · 科研成员</option>
            <option value="viewer">Viewer · 只读成员</option>
            {currentRole==="owner"&&<option value="admin">Admin · 管理员</option>}
          </select></label>
          <div style={{display:"flex",alignItems:"end"}}>
            <button disabled={sending} type="submit" style={{...input,background:"#151515",color:"#fff",cursor:"pointer"}}>
              {sending?"发送中…":"发送邀请邮件"}
            </button>
          </div>
        </form>
        <p style={{color:"#888",fontSize:11,margin:"13px 0 0"}}>
          邀请仅通过已配置的邮件服务发送；若邮件服务不可用，系统会返回明确错误，不会假装发送成功。
        </p>
      </section>
      <section style={panel}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12}}>
          <h2 style={{fontSize:17,margin:0}}>团队成员</h2>
          <button type="button" onClick={()=>void reload()} style={{background:"#fff",padding:8,border,borderRadius:5}}>刷新</button>
        </div>
        {loading?<p>加载中…</p>:
          <div style={{overflowX:"auto"}}>
            <table style={{width:"100%",borderCollapse:"collapse",marginTop:12,fontSize:12}}>
              <thead><tr>{["成员","身份","状态","管理"].map(x=><th key={x} style={{textAlign:"left",padding:"10px 8px",borderBottom:border}}>{x}</th>)}</tr></thead>
              <tbody>{members.map(m=><tr key={m.id}>
                <td style={{padding:"12px 8px",borderBottom:border}}><strong>{m.name}</strong><div style={{color:"#777"}}>{m.email}</div></td>
                <td style={{padding:"12px 8px",borderBottom:border}}>
                  {(m.role==="owner"||currentRole!=="owner"&&m.role==="admin")?m.role:
                    <select aria-label={"修改"+m.email+"的角色"} value={m.role}
                      onChange={e=>void updateMember(m,"role",e.target.value)}>
                      {["admin","researcher","viewer"].filter(x=>x!=="admin"||currentRole==="owner").map(x=><option value={x} key={x}>{x}</option>)}
                    </select>}
                </td>
                <td style={{padding:"12px 8px",borderBottom:border}}>{m.active?"启用":"停用"}</td>
                <td style={{padding:"12px 8px",borderBottom:border}}>
                  {m.role!=="owner"&&(currentRole==="owner"||m.role!=="admin")&&
                    <button type="button" style={{padding:"7px 11px",border,borderRadius:5,background:"#fff"}}
                      onClick={()=>void updateMember(m,"active",!m.active)}>{m.active?"停用":"启用"}</button>}
                </td>
              </tr>)}</tbody>
            </table>
          </div>}
      </section>
      <section style={panel}>
        <h2 style={{fontSize:17,margin:"0 0 12px"}}>邀请记录</h2>
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
            <thead><tr>{["邮箱","邀请角色","状态","到期"].map(x=><th key={x} style={{textAlign:"left",padding:"10px 8px",borderBottom:border}}>{x}</th>)}</tr></thead>
            <tbody>{invitations.map(x=><tr key={x.id}>
              <td style={{padding:"10px 8px",borderBottom:border}}>{x.email}</td>
              <td style={{padding:"10px 8px",borderBottom:border}}>{x.role}</td>
              <td style={{padding:"10px 8px",borderBottom:border}}>{x.status}</td>
              <td style={{padding:"10px 8px",borderBottom:border}}>{new Date(x.expires_at*1000).toLocaleString("zh-CN")}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  </main>;
}
