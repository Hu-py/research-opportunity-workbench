import { NextResponse } from "next/server";
import { authenticated, getTeamToken, teamAuthEnabled } from "@/lib/session";
export async function GET() {
  const team=teamAuthEnabled();
  if(!team)return NextResponse.json({authenticated:await authenticated(),team:false,member:null},{headers:{"Cache-Control":"no-store"}});
  const token=await getTeamToken(),base=process.env.BACKEND_URL,key=process.env.API_BEARER_TOKEN;
  if(!token || !base || !key)return NextResponse.json({authenticated:false,team:true,member:null},{headers:{"Cache-Control":"no-store"}});
  try {
    const response=await fetch(base.replace(/\/$/,"")+"/api/auth/me",{
      cache:"no-store",signal:AbortSignal.timeout(12000),
      headers:{"Authorization":"Bearer "+key,"X-Research-Session":token},
    });
    if(!response.ok)return NextResponse.json({authenticated:false,team:true,member:null},{headers:{"Cache-Control":"no-store"}});
    const payload=await response.json();
    return NextResponse.json({authenticated:Boolean(payload.member),team:true,member:payload.member},{headers:{"Cache-Control":"no-store"}});
  }catch{
    return NextResponse.json({authenticated:false,team:true,member:null},{headers:{"Cache-Control":"no-store"}});
  }
}
