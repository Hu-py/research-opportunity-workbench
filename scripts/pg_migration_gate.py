"""Guarded Render PostgreSQL -> isolated Supabase PostgreSQL migration helper.

Requires an operator-controlled execution environment with network access to
BOTH databases and PostgreSQL client binaries 17+.  This script is not an
online HTTP endpoint.  It never prints database URIs, passwords, or row values.

Typical source URL environment: DATABASE_URL (already configured on Render)
Destination URL environment: MIGRATION_TARGET_DATABASE_URL (a SEPARATE,
NEWLY CREATED, EMPTY Supabase project; not Research Agent Lab).

No production writes happen unless the operator explicitly runs 'restore' or
'secure-target', each with a separate confirmation flag.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, unquote, urlsplit


@dataclass(frozen=True)
class PgTarget:
    host: str
    port: int
    user: str
    password: str
    dbname: str
    sslmode: str = "require"

    @property
    def fingerprint(self):
        # Not a secret, but do not log the host or database user.
        return sha256(f"{self.host.lower()}:{self.port}/{self.dbname}".encode()).hexdigest()[:20]


def parse_postgres_url(raw: str) -> PgTarget:
    if not raw:
        raise ValueError("Database URL is missing from the specified environment variable")
    parsed = urlsplit(raw)
    if parsed.scheme not in ("postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"):
        raise ValueError("Only PostgreSQL connection strings are supported")
    if not parsed.hostname or not parsed.username or not parsed.path.strip("/"):
        raise ValueError("PostgreSQL URL must include host, username, database")
    if parsed.port and not 0 < parsed.port < 65536:
        raise ValueError("Invalid PostgreSQL port")
    args = parse_qs(parsed.query)
    sslmode = args.get("sslmode", ["require"])[0]
    if sslmode not in ("require", "verify-full", "verify-ca"):
        raise ValueError("Unsupported SSL mode; TLS is required for migration")
    return PgTarget(
        host=parsed.hostname, port=parsed.port or 5432,
        user=unquote(parsed.username), password=unquote(parsed.password or ""),
        dbname=unquote(parsed.path.lstrip("/")), sslmode=sslmode,
    )


def pg_env(target: PgTarget) -> dict:
    return {**os.environ, "PGHOST":target.host, "PGPORT":str(target.port),
            "PGUSER":target.user, "PGPASSWORD":target.password,
            "PGDATABASE":target.dbname, "PGSSLMODE":target.sslmode,
            "PGCONNECT_TIMEOUT":"12"}


def run_command(argv: list[str], target: PgTarget, capture=False):
    # Password is passed through an environment variable, NEVER command args.
    try:
        completed = subprocess.run(argv, env=pg_env(target),
                                   capture_output=True, text=True,
                                   check=False, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("PostgreSQL client command failed or timed out") from exc
    if completed.returncode:
        # Stderr could include private provider details; never print it here.
        raise RuntimeError(f"PostgreSQL command failed (exit {completed.returncode}); inspect private job logs")
    return completed.stdout if capture else None


def read_inventory(target: PgTarget) -> dict:
    # psycopg is installed on Render through the [postgres] extra.
    import psycopg
    from psycopg import sql
    try:
        with psycopg.connect(host=target.host,port=target.port,dbname=target.dbname,
                             user=target.user,password=target.password,
                             sslmode=target.sslmode,connect_timeout=12) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute("SELECT current_setting('server_version_num')::integer")
                version=int(cur.fetchone()[0])
                cur.execute("""SELECT c.relname, c.relrowsecurity
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relkind IN ('r','p')
                    ORDER BY c.relname""")
                rows=cur.fetchall()
                counts={}
                rls={}
                for name,flag in rows:
                    cur.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(
                        sql.Identifier("public"),sql.Identifier(name)))
                    counts[name]=int(cur.fetchone()[0])
                    rls[name]=bool(flag)
                cur.execute("SELECT pg_database_size(current_database())")
                database_bytes=int(cur.fetchone()[0])
                cur.execute("""SELECT extname FROM pg_extension ORDER BY extname""")
                extensions=[x[0] for x in cur.fetchall()]
                return {"fingerprint":target.fingerprint,
                        "postgres_major":version//10000,
                        "table_counts":counts,
                        "rls_enabled":rls,
                        "database_bytes":database_bytes,
                        "extensions":extensions}
    except Exception as exc:
        # Intentionally suppress connection-string and value-bearing details.
        raise RuntimeError("PostgreSQL inventory failed; verify private network and credentials") from exc


def checksum(path: Path) -> str:
    digest=sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def guarded_backup(source: PgTarget, archive: Path):
    if archive.exists() or archive.with_suffix(archive.suffix+".manifest.json").exists():
        raise ValueError("Backup path already exists; refusing to overwrite any archive")
    if not archive.parent.exists():
        archive.parent.mkdir(parents=True,exist_ok=False,mode=0o700)
    elif archive.parent.stat().st_mode & 0o077:
        raise ValueError("Backup directory is not private (mode 0700 required)")
    before=read_inventory(source)
    # PostgreSQL client must be available and suitable for the source major.
    version=subprocess.run(["pg_dump","--version"],capture_output=True,text=True,check=True).stdout
    match=re.search(r"PostgreSQL\)?\s+(\d+)",version)
    if not match or int(match.group(1)) < before["postgres_major"]:
        raise RuntimeError("pg_dump must be at least the source PostgreSQL major version")
    flags=["pg_dump","--format=custom","--schema=public",
           "--no-owner","--no-privileges","--no-subscriptions",
           "--file",str(archive)]
    previous_umask=os.umask(0o077)  # Archive and manifest must never be world-readable, even briefly.
    try:
        run_command(flags,source)
        os.chmod(archive,0o600)
        after=read_inventory(source)
        if before["table_counts"]!=after["table_counts"]:
            raise RuntimeError("Source row counts changed while backing up; rerun after pausing writes")
        manifest={"created_at":datetime.now(timezone.utc).isoformat(),
                  "source":{key:before[key] for key in
                            ("fingerprint","postgres_major","table_counts",
                             "database_bytes","extensions")},
                  "archive_sha256":checksum(archive),
                  "archive_bytes":archive.stat().st_size,
                  "requires_manual_privacy_review":True}
        manifest_file=archive.with_suffix(archive.suffix+".manifest.json")
        with manifest_file.open("x",encoding="utf-8") as stream:
            json.dump(manifest,stream,sort_keys=True,indent=2)
        os.chmod(manifest_file,0o600)
        return {"backup_saved":True,"archive_bytes":manifest["archive_bytes"],
                "tables":len(before["table_counts"]),
                "manifest_file":str(manifest_file)}
    except Exception:
        # Never treat an incomplete backup file as valid.
        if archive.exists():
            archive.unlink()
        raise
    finally:
        os.umask(previous_umask)


def verify_archive(archive: Path):
    manifest_path=archive.with_suffix(archive.suffix+".manifest.json")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if checksum(archive)!=manifest["archive_sha256"]:
        raise ValueError("Archive checksum mismatch: refuse restore")
    toc=subprocess.run(["pg_restore","--list",str(archive)],
                       capture_output=True,text=True,check=False,timeout=60)
    if toc.returncode!=0 or "TABLE DATA" not in toc.stdout:
        raise ValueError("Invalid or empty PostgreSQL logical backup")
    return manifest,toc.stdout


def filter_supabase_toc(raw: str) -> str:
    """Skip only the pre-existing public schema declaration/comment.

    We must not use --clean, because the target contains Supabase system
    schemas and deleting their contents would be catastrophic.
    """
    kept=[]
    for line in raw.splitlines():
        if re.search(r";\s*\d+\s+\d+\s+SCHEMA\s+-\s+public(?:\s|$)",line):
            continue
        if re.search(r";\s*\d+\s+\d+\s+COMMENT\s+-\s+SCHEMA\s+public(?:\s|$)",line):
            continue
        kept.append(line)
    return "\n".join(kept)+"\n"


def guarded_restore(target: PgTarget, archive: Path, confirmed: bool):
    if not confirmed:
        raise ValueError("Explicit --confirm-empty-target is required")
    manifest,toc=verify_archive(archive)
    if target.fingerprint==manifest["source"]["fingerprint"]:
        raise ValueError("Source and target database identity are identical")
    before=read_inventory(target)
    if before["table_counts"]:
        raise ValueError("Target public schema has existing tables; never restore into a populated project")
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",
                                     prefix="safe-pg-toc-",suffix=".txt",delete=False) as stream:
        path=Path(stream.name)
        os.chmod(path,0o600)
        stream.write(filter_supabase_toc(toc))
    try:
        run_command(["pg_restore","--dbname",target.dbname,"--format=custom","--exit-on-error",
                     "--single-transaction","--no-owner","--no-privileges",
                     "--use-list",str(path),str(archive)],target)
    finally:
        path.unlink(missing_ok=True)
    after=read_inventory(target)
    if after["table_counts"]!=manifest["source"]["table_counts"]:
        raise RuntimeError("Table row counts differ after restore; do not cut over")
    return {"restored":True,"same_table_counts":True,
            "tables":len(after["table_counts"]),
            "rls_unprotected_tables":[t for t in manifest["source"]["table_counts"]
                                      if not after["rls_enabled"].get(t,False)]}


def secure_target(target: PgTarget, archive: Path, confirmed: bool):
    if not confirmed:
        raise ValueError("Explicit --confirm-rls-lockdown is required")
    manifest,_=verify_archive(archive)
    if target.fingerprint==manifest["source"]["fingerprint"]:
        raise ValueError("Refusing to modify source database; target identity matches backup source")
    import psycopg
    from psycopg import sql
    inv=read_inventory(target)
    if inv["table_counts"]!=manifest["source"]["table_counts"]:
        raise ValueError("Target data is incomplete or not the source snapshot; cannot lock down")
    # Apply RLS and REVOKE to app-owned tables only, within one transaction.
    # No public API policies are needed: FastAPI connects with DB credentials.
    with psycopg.connect(host=target.host,port=target.port,dbname=target.dbname,
                         user=target.user,password=target.password,
                         sslmode=target.sslmode,connect_timeout=12) as conn:
        with conn.cursor() as cur:
            for name in sorted(inv["table_counts"]):
                obj=sql.SQL("{}.{}").format(sql.Identifier("public"),sql.Identifier(name))
                cur.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(obj))
                cur.execute(sql.SQL("REVOKE ALL ON TABLE {} FROM anon, authenticated, service_role, PUBLIC").format(obj))
            # Existing default API grants on future tables must also be
            # reviewed in the Supabase dashboard; see release runbook.
    after=read_inventory(target)
    if any(not after["rls_enabled"].get(t,False) for t in inv["table_counts"]):
        raise RuntimeError("Not all app tables have RLS enabled")
    return {"rls_lockdown":True,"tables":len(inv["table_counts"])}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["source-inventory","target-inventory",
                                          "backup","verify","restore","secure-target"])
    parser.add_argument("--archive",type=Path,default=Path("private-backups/research-atlas.dump"))
    parser.add_argument("--source-env",default="DATABASE_URL")
    parser.add_argument("--target-env",default="MIGRATION_TARGET_DATABASE_URL")
    parser.add_argument("--confirm-empty-target",action="store_true")
    parser.add_argument("--confirm-rls-lockdown",action="store_true")
    options=parser.parse_args(argv)
    try:
        if options.action=="verify":
            manifest,_=verify_archive(options.archive)
            result={"archive_valid":True,"tables":len(manifest["source"]["table_counts"]),
                    "bytes":manifest["archive_bytes"]}
        elif options.action in ("source-inventory","backup"):
            source=parse_postgres_url(os.getenv(options.source_env,""))
            result=read_inventory(source) if options.action=="source-inventory" else guarded_backup(source,options.archive)
        else:
            target=parse_postgres_url(os.getenv(options.target_env,""))
            if options.action=="target-inventory":
                result=read_inventory(target)
            elif options.action=="restore":
                result=guarded_restore(target,options.archive,options.confirm_empty_target)
            else:
                result=secure_target(target,options.archive,options.confirm_rls_lockdown)
        print(json.dumps(result,sort_keys=True,ensure_ascii=False))
        return 0
    except Exception as exc:
        print("Migration gate failed: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    sys.exit(main())
