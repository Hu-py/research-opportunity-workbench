import { NextResponse } from "next/server";
import {configured,labRead,privateHeaders,safeListItem,sessionGate} from "@/lib/research-lab-server";

export const dynamic="force-dynamic";
export async function GET() {
  const gate=await sessionGate();
  if(!gate.ok)return NextResponse.json({detail:gate.detail},{status:gate.status,headers:privateHeaders});
  if(!configured())return NextResponse.json({
    configured:false,items:[],
    detail:"尚未连接独立科研实验数据库，请在 Vercel 配置 RESEARCH_LAB_SUPABASE_URL 和 RESEARCH_LAB_SUPABASE_SECRET_KEY"
  },{headers:privateHeaders});
  try {
    const raw=await labRead({
      select:"id,line_id,strategy,status,model_calls,results,created_at",
      order:"created_at.desc",limit:"25"
    }) as Record<string,unknown>[];
    return NextResponse.json({configured:true,items:raw.map(safeListItem)},{headers:privateHeaders});
  } catch {
    return NextResponse.json({configured:true,items:[],detail:"科研实验数据读取失败，请核对独立 Supabase 连接权限"},
      {status:503,headers:privateHeaders});
  }
}
