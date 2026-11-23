import { NextResponse } from "next/server";
import {configured,labRead,privateHeaders,safeDetail,sessionGate} from "@/lib/research-lab-server";

export const dynamic="force-dynamic";
type Context={params:Promise<{id:string}>};
export async function GET(_request:Request,context:Context) {
  const gate=await sessionGate();
  if(!gate.ok)return NextResponse.json({detail:gate.detail},{status:gate.status,headers:privateHeaders});
  if(!configured())return NextResponse.json({detail:"科研实验数据库尚未连接"},{status:503,headers:privateHeaders});
  const {id}=await context.params;
  if(!/^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(id))
    return NextResponse.json({detail:"无效的实验编号"},{status:400,headers:privateHeaders});
  try {
    const rows=await labRead({
      select:"id,line_id,strategy,status,model_calls,results,created_at",
      id:"eq."+id,limit:"1"
    }) as Record<string,unknown>[];
    if(!rows.length)return NextResponse.json({detail:"实验不存在"},{status:404,headers:privateHeaders});
    return NextResponse.json(safeDetail(rows[0]),{headers:privateHeaders});
  }catch{
    return NextResponse.json({detail:"无法读取实验详情"},{status:503,headers:privateHeaders});
  }
}
