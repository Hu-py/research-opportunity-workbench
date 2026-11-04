import { NextResponse } from "next/server";
import { checkPassword, createSession, setTeamToken, teamAuthEnabled } from "@/lib/session";
export async function POST(request:Request) {
  const json=await request.json().catch(()=>({}));
  if(typeof json.password!=="string" || json.password.length>512){
    return NextResponse.json({detail:"Invalid password"},{status:400});
  }
  if(teamAuthEnabled()){
    if(typeof json.email!=="string" || json.email.length>255){
      return NextResponse.json({detail:"请输入团队成员邮箱"},{status:400});
    }
    const base=process.env.BACKEND_URL;
    const key=process.env.API_BEARER_TOKEN;
    if(!base || !key){
      return NextResponse.json({detail:"团队登录尚未配置后端连接"},{status:503});
    }
    try{
      const response=await fetch(base.replace(/\/$/,"")+"/api/auth/login",{
        method:"POST",cache:"no-store",signal:AbortSignal.timeout(12000),
        headers:{"Content-Type":"application/json","Authorization":"Bearer "+key},
        body:JSON.stringify({email:json.email,password:json.password}),
      });
      if(!response.ok)return NextResponse.json({detail:response.status===401?"邮箱或密码错误":"身份服务暂不可用"},{status:response.status});
      const data=await response.json();
      if(typeof data.token!=="string" || !data.token)return NextResponse.json({detail:"登录会话无效"},{status:502});
      await setTeamToken(data.token,Number(data.expires_in)||604800);
      return NextResponse.json({ok:true,member:data.member});
    }catch{
      return NextResponse.json({detail:"无法连接团队认证服务"},{status:502});
    }
  }
  if(!process.env.APP_PASSWORD || !process.env.SESSION_SECRET || process.env.SESSION_SECRET.length<32){
    return NextResponse.json({detail:"Login is not configured on server"},{status:503});
  }
  if(!checkPassword(json.password))return NextResponse.json({detail:"密码不正确"},{status:401});
  await createSession();
  return NextResponse.json({ok:true});
}
