import { NextRequest, NextResponse } from "next/server";
import { getTeamToken, teamAuthEnabled } from "@/lib/session";

export const runtime="nodejs";
export const dynamic="force-dynamic";

const MAX_PROXY_PDF_BYTES=4_000_000; // Vercel serverless payload threshold is about 4.5 MB.
const json=(detail:string,status:number)=>
  NextResponse.json({detail},{status,headers:{"Cache-Control":"no-store"}});

/** Server-side binary bridge; secret bearer never enters the browser. */
export async function POST(request:NextRequest) {
  if (!teamAuthEnabled()) return json("Owner-only research access is unavailable",404);
  const token=await getTeamToken();
  const base=process.env.BACKEND_URL?.replace(/\/$/,"");
  const bearer=process.env.API_BEARER_TOKEN;
  if (!token) return json("请先登录 Research Atlas Owner 账号",401);
  if (!base||!/^https:\/\//.test(base)||!bearer)
    return json("测试后端尚未配置",503);
  if (request.headers.get("content-type")?.split(";")[0].trim()!=="application/pdf")
    return json("请选择 PDF 文件",415);
  const len=Number(request.headers.get("content-length")||0);
  if (len>MAX_PROXY_PDF_BYTES) return json("文件超过网页上传限制（4 MB）；请使用已有的论文记录",413);
  try {
    const auth=await fetch(base+"/api/auth/me",{
      cache:"no-store",signal:AbortSignal.timeout(12000),
      headers:{"Authorization":"Bearer "+bearer,"X-Research-Session":token},
    });
    if (!auth.ok) return json("Owner 会话已经失效，请重新登录",401);
    const me=await auth.json();
    if (me.member?.role!=="owner"||me.member?.active===false)
      return json("只有 Owner 可以上传并运行 SC05 实验",403);

    const data=Buffer.from(await request.arrayBuffer());
    if (data.length>MAX_PROXY_PDF_BYTES) return json("文件超过网页上传限制（4 MB）",413);
    if (data.length<100||data.toString("ascii",0,4)!=="%PDF")
      return json("文件不是有效的 PDF",422);
    const rawTitle=(request.headers.get("x-paper-title")||"Published research paper");
    const title=rawTitle.replace(/[^\x20-\x7E]/g," ").trim().slice(0,280)||"Published research paper";
    const res=await fetch(base+"/api/personal-research/me/sc05/cases/pdf",{
      method:"POST",cache:"no-store",redirect:"manual",
      signal:AbortSignal.timeout(50000),
      headers:{"Authorization":"Bearer "+bearer,
               "X-Research-Session":token,
               "Content-Type":"application/pdf",
               "X-Research-Paper-Title":title},
      body:data,
    });
    const body=await res.text();
    return new NextResponse(body,{
      status:res.status,
      headers:{"Content-Type":res.headers.get("content-type")||"application/json",
               "Cache-Control":"private, no-store"},
    });
  } catch {
    return json("上传失败，请检查测试后端连接或 PDF 文件",502);
  }
}
