import { NextResponse } from "next/server";
import { checkPassword, createSession } from "@/lib/session";
export async function POST(request: Request) {
  const json = await request.json().catch(() => ({}));
  if (typeof json.password !== "string" || json.password.length > 512) {
    return NextResponse.json({detail:"Invalid password"},{status:400});
  }
  if (!process.env.APP_PASSWORD || !process.env.SESSION_SECRET || process.env.SESSION_SECRET.length < 32) {
    return NextResponse.json({detail:"Login is not configured on server"},{status:503});
  }
  if (!checkPassword(json.password)) {
    return NextResponse.json({detail:"密码不正确"},{status:401});
  }
  await createSession();
  return NextResponse.json({ok:true});
}
