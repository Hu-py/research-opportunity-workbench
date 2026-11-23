import { NextResponse } from "next/server";
import { authenticated, getTeamToken, teamAuthEnabled } from "@/lib/session";
export const maxDuration = 60;

export async function GET() {
  const team=teamAuthEnabled();
  if(!team)return NextResponse.json({authenticated:await authenticated(),team:false,member:null},{headers:{"Cache-Control":"no-store"}});
  const token=await getTeamToken(),base=process.env.BACKEND_URL,key=process.env.API_BEARER_TOKEN;
  if(!base || !key)return NextResponse.json({authenticated:false,team:true,member:null,connection_error:true,detail:"团队认证服务未配置后端连接"},{headers:{"Cache-Control":"no-store"}});
  if(!token)return NextResponse.json({authenticated:false,team:true,member:null},{headers:{"Cache-Control":"no-store"}});
  try {
    const response=await fetch(base.replace(/\/$/,"")+"/api/auth/me",{
      cache:"no-store",signal:AbortSignal.timeout(55000),
      headers:{"Authorization":"Bearer "+key,"X-Research-Session":token},
    });
    const payload=await response.json().catch(()=>({}));
    if(!response.ok){
      const backendDetail=typeof payload.detail==="string"?payload.detail:"";
      const configurationError=backendDetail==="Authentication required"
        || backendDetail==="API auth is not configured"
        || backendDetail==="Team authentication is disabled";
      return NextResponse.json({
        authenticated:false,team:true,member:null,
        connection_error:configurationError || response.status>=500 || response.status===404,
        detail:backendDetail==="Authentication required"
          ? "Vercel 与 Render 的 API_BEARER_TOKEN 不匹配"
          : backendDetail==="API auth is not configured"
            ? "Render API 尚未配置 API_BEARER_TOKEN"
            : backendDetail==="Team authentication is disabled"
              ? "Render API 尚未开启 TEAM_AUTH_ENABLED"
              : response.status>=500 || response.status===404 ? "团队认证服务暂不可用" : undefined
      },{headers:{"Cache-Control":"no-store"}});
    }
    if(payload.enabled===false){
      return NextResponse.json({authenticated:false,team:true,member:null,connection_error:true,detail:"Render API 尚未开启 TEAM_AUTH_ENABLED"},{headers:{"Cache-Control":"no-store"}});
    }
    return NextResponse.json({authenticated:Boolean(payload.member),team:true,member:payload.member},{headers:{"Cache-Control":"no-store"}});
  }catch{
    return NextResponse.json({authenticated:false,team:true,member:null,connection_error:true,detail:"无法连接团队认证服务。Render 免费实例休眠后首次唤醒可能需要约 40–60 秒，请稍后重试。"},{headers:{"Cache-Control":"no-store"}});
  }
}
