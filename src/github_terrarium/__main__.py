"""Read-only diagnostic command; no output branch mutations."""

import argparse
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .config import load_config
from .github import GraphQLClient
from .models import canonical_json
from .normalize import collect
from .probe import probe


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("probe", help="Read first-page public API samples")
    command.add_argument("--config", type=Path, default=Path("terrarium.toml"))
    command.add_argument(
        "--repository", default=os.environ.get("GITHUB_REPOSITORY", "")
    )
    command.add_argument(
        "--day",
        type=date.fromisoformat,
        default=datetime.now(UTC).date() - timedelta(days=1),
    )
    command = commands.add_parser(
        "collect", help="Collect complete public daily counts"
    )
    command.add_argument("--config", type=Path, default=Path("terrarium.toml"))
    command.add_argument(
        "--repository", default=os.environ.get("GITHUB_REPOSITORY", "")
    )
    command.add_argument("--start", type=date.fromisoformat, required=True)
    command.add_argument(
        "--end", type=date.fromisoformat, default=datetime.now(UTC).date()
    )
    command.add_argument(
        "--expected-subject", help="Reject a different immutable user ID"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "probe" and args.day >= datetime.now(UTC).date():
            raise ValueError("Probe day must be a completed UTC day")
        config = load_config(args.config, args.repository)
        client = GraphQLClient(
            os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
        )
        if args.command == "probe":
            result = probe(config, args.day, client)
        else:
            result = collect(
                config,
                args.start,
                args.end,
                client,
                expected_subject=args.expected_subject,
            )
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(canonical_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
