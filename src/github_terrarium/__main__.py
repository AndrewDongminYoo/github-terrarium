"""Read-only diagnostic command; no output branch mutations."""

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .config import load_config
from .github import GraphQLClient
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
    args = parser.parse_args(argv)
    try:
        if args.day >= datetime.now(UTC).date():
            raise ValueError("Probe day must be a completed UTC day")
        config = load_config(args.config, args.repository)
        client = GraphQLClient(
            os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
        )
        result = probe(config, args.day, client)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
