import { NextRequest, NextResponse } from "next/server";
import { authenticated } from "@/lib/session";

type Context = {params: Promise<{segments: string[]}>};
async function forward(request: NextRequest, context: Context) {
  if (!(await authenticated())) {
    return NextResponse.json({detail:"请先登录"},{status:401});
  }
  const base=process.env.BACKEND_URL;
  if (!base || !/^https?:\/\//.test(base)) {
    return NextResponse.json({detail:"BACKEND_URL 尚未配置"},{status:503});
  }
  const {segments}=await context.params;
  if (!segments.length || segments.some((s)=>!/^[\w-]{1,90}$/.test(s))) {
    return NextResponse.json({detail:"Invalid API path"},{status:400});
  }
  const endpoint=new URL(base.replace(/\/$/,"")+"/api/"+segments.join("/"));
  endpoint.search=request.nextUrl.search;
  try {
    const response=await fetch(endpoint,{
      method:request.method,
      headers:{
        "Content-Type":"application/json",
        ...(process.env.API_BEARER_TOKEN?{"Authorization":"Bearer "+process.env.API_BEARER_TOKEN}:{})
      },
      body:request.method==="GET"?undefined:await request.text(),
      redirect:"manual",cache:"no-store",signal:AbortSignal.timeout(55000),
    });
    const body=await response.text();
    return new NextResponse(body,{
      status:response.status,
      headers:{"Content-Type":response.headers.get("content-type") || "application/json","Cache-Control":"no-store"}
    });
  } catch {
    return NextResponse.json({detail:"后端暂时不可达，请检查 FastAPI 服务"},{status:502});
  }
}
export const dynamic="force-dynamic";
export {forward as GET, forward as POST, forward as PUT, forward as PATCH};
