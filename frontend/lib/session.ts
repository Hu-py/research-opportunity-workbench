import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

const COOKIE_NAME = "research_session";
const LIFETIME = 60 * 60 * 24 * 7;

function isLocalOpen() {
  return process.env.NODE_ENV !== "production" && !process.env.APP_PASSWORD;
}
function signature(value: string) {
  const secret = process.env.SESSION_SECRET || "";
  return createHmac("sha256", secret).update(value).digest("hex");
}
export function checkPassword(attempt: string) {
  const expected = process.env.APP_PASSWORD;
  if (!expected || !process.env.SESSION_SECRET || process.env.SESSION_SECRET.length < 32) return false;
  const a = createHmac("sha256", "password-compare").update(attempt).digest();
  const b = createHmac("sha256", "password-compare").update(expected).digest();
  return timingSafeEqual(a,b);
}
export async function authenticated() {
  if (isLocalOpen()) return true;
  if (!process.env.APP_PASSWORD || !process.env.SESSION_SECRET || process.env.SESSION_SECRET.length < 32) return false;
  const cookie = (await cookies()).get(COOKIE_NAME)?.value || "";
  const parts = cookie.split(".");
  if (parts.length !== 2) return false;
  const [expires, given] = parts;
  if (!/^\d+$/.test(expires) || Number(expires) <= Math.floor(Date.now()/1000)) return false;
  const expected = signature(expires);
  if (!/^[0-9a-f]{64}$/.test(given)) return false;
  return timingSafeEqual(Buffer.from(given,"hex"),Buffer.from(expected,"hex"));
}
export async function createSession() {
  const expires = String(Math.floor(Date.now()/1000) + LIFETIME);
  (await cookies()).set(COOKIE_NAME, expires+"."+signature(expires),{
    httpOnly:true,secure:process.env.NODE_ENV==="production",
    sameSite:"strict",path:"/",maxAge:LIFETIME,
  });
}
export async function removeSession() {
  (await cookies()).delete(COOKIE_NAME);
}
