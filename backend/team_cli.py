"""Create the first administrator with a terminal password prompt.

Example: python -m backend.team_cli bootstrap-admin --email name@example.org
"""
import argparse
import getpass
import os
from research_workbench.core import session_factory
from backend.team import create_member

def main(argv=None):
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="command",required=True)
    cmd=sub.add_parser("bootstrap-admin")
    cmd.add_argument("--email",required=True)
    cmd.add_argument("--name",default="Team Administrator")
    args=p.parse_args(argv)
    if args.command=="bootstrap-admin":
        password=getpass.getpass("New admin password (12+ characters): ")
        repeat=getpass.getpass("Repeat password: ")
        if password!=repeat:raise SystemExit("Passwords do not match")
        with session_factory()() as db:
            try:create_member(db,args.email,args.name,password,role="admin",initial=True)
            except ValueError as exc:raise SystemExit(str(exc))
        print("Admin created. Do not store passwords in GitHub or logs.")
if __name__=="__main__":
    main()
