export async function api<T>(path:string, options?:RequestInit):Promise<T> {
  const response=await fetch("/api/proxy/"+path.replace(/^\/+/,""),{
    ...options,
    headers:{"Content-Type":"application/json",...(options?.headers || {})},
    cache:"no-store",
  });
  if (!response.ok) {
    let message="请求失败 "+response.status;
    try {
      const body=await response.json();
      message=typeof body.detail==="string"?body.detail:message;
    } catch {}
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
