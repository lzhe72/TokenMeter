"""Explicit migration/provision commands; never creates default credentials."""
import argparse
import json
import sys
import re
from pathlib import Path
from sqlalchemy.engine import make_url

from .migrations import migrate
from .provision import provision


def validate_test_database(database_url, run_id):
    if not run_id or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", run_id):
        raise ValueError("Synthetic accounts require an isolated test run ID")
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "sqlite" or not parsed.database or not Path(parsed.database).is_absolute() or parsed.query:
        raise ValueError("Synthetic accounts require an absolute isolated SQLite file")
    target = Path(parsed.database)
    for path in (target, *target.parents):
        if path.is_symlink():
            raise ValueError("Refusing symlink test database")
    marker = target.parent / ".tokenmeter-test-database.json"
    if marker.is_symlink() or not marker.is_file():
        raise ValueError("Missing isolated database marker")
    expected = {"owner": "tokenmeter-test-database", "run_id": run_id, "database": target.name}
    if json.loads(marker.read_text()) != expected:
        raise ValueError("Database ownership does not match")


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("migrate", "provision"):
        command = commands.add_parser(name)
        command.add_argument("--database-url", required=True)
        if name == "provision":
            command.add_argument("--accounts", required=True, type=Path)
            command.add_argument("--test-run-id")
    args = parser.parse_args(argv)
    try:
        if args.command == "migrate":
            migrate(args.database_url)
            result = {"operation": "migrate", "schema_version": "0001"}
        else:
            payload = json.loads(args.accounts.read_text())
            if payload.get("test_only") is True:
                validate_test_database(args.database_url, args.test_run_id)
            count = provision(args.database_url, payload["users"])
            result = {"operation": "provision", "created_accounts": count}
        print(json.dumps(result))
        return 0
    except Exception as error:
        # Validation and DB exceptions can contain the password-bearing input.
        print(json.dumps({"error": {"code": "operation_failed", "message": type(error).__name__}}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
