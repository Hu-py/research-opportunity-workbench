"""Credential-free SC05 MCP service/OAuth handshake probe.

Checks the *public protocol* only. Passing does not validate an Owner grant,
ChatGPT's approved tool snapshot, or token refresh. Never sends credentials,
OpenAI calls, or DeepSeek requests; outputs no response bodies or headers with
secrets. Intended for isolated Render URL and Actions diagnostics.
"""
from __future__ import annotations

import argparse
import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def fetch(url: str, *, method: str = "GET", body: bytes | None = None,
          timeout: float = 30.0) -> tuple[int, dict, dict]:
    req = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "User-Agent": "ResearchAtlas-SC05-noauth-probe/1",
        },
    )
    try:
        with urlopen(req, timeout=timeout, context=ssl.create_default_context()) as reply:
            status = reply.status
            data = reply.read(24576)
            headers = dict(reply.headers.items())
    except HTTPError as exc:
        status = exc.code
        data = exc.read(24576)
        headers = dict(exc.headers.items())
    except (URLError, TimeoutError, OSError) as exc:
        # Do not log URLs, traceback text, header/body or tokens.
        return 0, {}, {"network_error_class": type(exc).__name__}
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeError):
        parsed = {}
    return status, parsed if isinstance(parsed, dict) else {}, {
        "bearer_challenge": "bearer" in headers.get("WWW-Authenticate", "").lower(),
        "content_type": headers.get("Content-Type", "").split(";")[0],
    }


def probe(base: str, timeout: float = 30.0) -> dict:
    base = base.rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path:
        raise ValueError("Expected a HTTPS origin with no path")
    summary: dict = {
        "origin": base, "model_calls": 0, "owner_tokens_used": 0,
        "checks": {}, "pass": False,
        "limits": ["Cannot test existing Owner grant or ChatGPT workspace tool snapshot",
                   "Cannot determine OAuth refresh-token behavior without a real grant"],
    }
    health, health_json, health_extra = fetch(base+"/api/health",timeout=timeout)
    summary["checks"]["api_health"] = {
        "http": health, "ok": health == 200,
        "note":health_extra.get("network_error_class", ""),
    }
    status, prm, extra = fetch(
        base+"/.well-known/oauth-protected-resource",timeout=timeout)
    summary["checks"]["protected_resource"] = {
        "http": status, "ok": (
            status == 200 and prm.get("resource") == base+"/mcp" and
            { "experiments:read", "experiments:run" }.issubset(
                set(prm.get("scopes_supported", []))) and
            base in prm.get("authorization_servers", [])
        ),
        "note":extra.get("network_error_class",""),
    }
    status, oauth, extra = fetch(
        base+"/.well-known/oauth-authorization-server",timeout=timeout)
    summary["checks"]["oauth_metadata"] = {
        "http": status, "ok": (
            status == 200 and oauth.get("issuer") == base and
            oauth.get("authorization_endpoint") == base+"/oauth/authorize" and
            oauth.get("token_endpoint") == base+"/oauth/token" and
            "refresh_token" in oauth.get("grant_types_supported", []) and
            "S256" in oauth.get("code_challenge_methods_supported", [])
        ),
        "note":extra.get("network_error_class",""),
    }
    status, unused, extra = fetch(
        base+"/mcp",method="POST",
        body=b'{"jsonrpc":"2.0","id":167,"method":"tools/list"}',
        timeout=timeout)
    summary["checks"]["unauthenticated_mcp_challenge"] = {
        "http": status, "ok": status == 401 and extra.get("bearer_challenge",False),
        "bearer_challenge":extra.get("bearer_challenge",False),
        "note":extra.get("network_error_class",""),
    }
    summary["pass"] = all(x["ok"] for x in summary["checks"].values())
    summary["next_action"] = (
        "If Owner MCP still fails, refresh the ChatGPT workspace MCP action snapshot "
        "then reconnect the Owner OAuth account; this probe cannot test that private state."
        if summary["pass"] else
        "Inspect failing public endpoint's HTTP/network status and Render gateway logs "
        "before changing ChatGPT settings."
    )
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base",required=True)
    ap.add_argument("--output")
    ap.add_argument("--timeout",type=float,default=30)
    args=ap.parse_args()
    report=probe(args.base,args.timeout)
    serialized=json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)
    if args.output:
        with open(args.output,"w",encoding="utf-8") as f:
            f.write(serialized+"\n")
    print(serialized)
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
