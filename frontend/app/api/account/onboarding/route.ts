import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
const paths: Record<string, string> = {
  owner_request: "/api/account/owner/request",
  reset_request: "/api/account/reset/request",
  redeem: "/api/account/setup/redeem",
};

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin)
    return NextResponse.json({ detail: "跨站请求被拒绝" }, { status: 403 });
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || typeof body.operation !== "string" ||
      !(body.operation in paths))
    return NextResponse.json({ detail: "无效操作" }, { status: 400 });
  const base = process.env.BACKEND_URL;
  const key = process.env.API_BEARER_TOKEN;
  if (!base || !key)
    return NextResponse.json({ detail: "账户服务尚未配置" }, { status: 503 });
  const { operation, ...payload } = body;
  try {
    const upstream = await fetch(base.replace(/\/$/, "") + paths[operation], {
      method: "POST", cache: "no-store", redirect: "manual",
      signal: AbortSignal.timeout(20000),
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key },
      body: JSON.stringify(payload),
    });
    const data = await upstream.json().catch(() => ({ detail: "账户服务响应异常" }));
    return NextResponse.json(data, {
      status: upstream.status,
      headers: { "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex" },
    });
  } catch {
    return NextResponse.json({ detail: "账户服务暂不可达" }, { status: 502 });
  }
}
