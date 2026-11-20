import { notFound, redirect } from "next/navigation";
import { getTeamToken, teamAuthEnabled } from "@/lib/session";
import ExperimentManager from "./experiment-manager";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function ExperimentManagementPage() {
  if (!teamAuthEnabled()) notFound();
  const token = await getTeamToken();
  if (!token) redirect("/devstudio");
  const base = process.env.BACKEND_URL;
  const bearer = process.env.API_BEARER_TOKEN;
  if (!base || !bearer) notFound();
  try {
    const response = await fetch(base.replace(/\/$/, "") + "/api/auth/me", {
      cache: "no-store", signal: AbortSignal.timeout(12000),
      headers: {
        Authorization: "Bearer " + bearer,
        "X-Research-Session": token,
      },
    });
    if (response.status === 401) redirect("/devstudio");
    if (!response.ok) notFound();
    const payload = await response.json();
    const role: string = payload.member?.role || "";
    if (role !== "owner" && role !== "admin") notFound();
    return <ExperimentManager currentRole={role}/>;
  } catch (error) {
    if (error && typeof error === "object" && "digest" in error) throw error;
    notFound();
  }
}
