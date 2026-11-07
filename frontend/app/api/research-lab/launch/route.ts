import {NextRequest,NextResponse} from "next/server";
import {adminGate,dispatchLaunch,launchConfigured,privateResponseHeaders,
        recentLaunches,validateLaunch,workflowUrl} from "@/lib/research-lab-launch";

export const dynamic="force-dynamic";

function fail(detail:string,status:number){
 return NextResponse.json({detail},{status,headers:privateResponseHeaders});
}
function normalizeError(error:unknown){
 const code=error instanceof Error?error.message:"UNEXPECTED_ERROR";
 if(code==="EXPERIMENT_ALREADY_RUNNING")return {detail:"有正式科研实验正在运行或排队，请等待结束后再启动。",status:409};
 if(code==="GITHUB_PERMISSION_DENIED")return {detail:"GitHub Token 无权限；需对 research-agent-lab 仓库授权 Actions: Read and write。",status:503};
 if(code==="GITHUB_WORKFLOW_NOT_FOUND")return {detail:"GitHub 工作流不存在，或 Token 无权访问该仓库。",status:503};
 if(code==="LAUNCH_TOKEN_MISSING")return {detail:"未设置服务端 RESEARCH_LAB_GITHUB_TOKEN。",status:503};
 if(code==="INVALID_PARAMETERS"||code==="INVALID_NAMESPACE"||code==="GRAPH_REQUIRES_TEAM_EVIDENCE")
   return {detail:"实验配置无效或与证据来源不兼容，请检查后重试。",status:400};
 return {detail:"GitHub 实验调度暂不可用，请查看安全配置或稍后重试。",status:503};
}
export async function GET(){
 const gate=await adminGate();
 if(!gate.ok)return fail(gate.detail,gate.status);
 if(!launchConfigured())return NextResponse.json({
   configured:false,workflow_url:workflowUrl,runs:[],
   detail:"尚未配置 RESEARCH_LAB_GITHUB_TOKEN；管理员需在 Vercel 服务端环境变量中授权专用 GitHub Actions Token。"
 },{headers:privateResponseHeaders});
 try{
  const runs=await recentLaunches();
  return NextResponse.json({configured:true,workflow_url:workflowUrl,runs},
    {headers:privateResponseHeaders});
 }catch(error){
  const info=normalizeError(error);
  return fail(info.detail,info.status);
 }
}
export async function POST(request:NextRequest){
 const gate=await adminGate();
 if(!gate.ok)return fail(gate.detail,gate.status);
 if(!launchConfigured())return fail("启动功能尚未配置管理员专用 GitHub Token。",503);
 // Same-origin only, no cross-site forms or text/plain to bypass JSON checks.
 const origin=request.headers.get("origin");
 if(!origin||origin!==request.nextUrl.origin)return fail("跨站启动请求已拒绝。",403);
 if(!request.headers.get("content-type")?.toLowerCase().startsWith("application/json"))
   return fail("仅支持 application/json 参数。",415);
 let raw:unknown;
 try{
   const input=await request.text();
   if(input.length>3500)return fail("实验参数超出安全限制。",413);
   raw=JSON.parse(input);
 }catch{return fail("JSON 参数无效。",400);}
 try{
  const payload=validateLaunch(raw);
  const status=await dispatchLaunch(payload);
  return NextResponse.json(status,{status:202,headers:privateResponseHeaders});
 }catch(error){
  const info=normalizeError(error);
  return fail(info.detail,info.status);
 }
}
