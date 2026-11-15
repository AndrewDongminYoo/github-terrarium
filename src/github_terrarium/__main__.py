"""Read-only diagnostic command; no output branch mutations."""

import argparse
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .config import load_config
from .github import GraphQLClient
from .growth import advance
from .models import canonical_json
from .normalize import collect
from .probe import probe
from .state import read_json, validate_state


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
    command = commands.add_parser(
        "grow", help="Reconcile local growth state without network access"
    )
    command.add_argument("--snapshot", type=Path, required=True)
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--state", type=Path)
    source.add_argument("--bootstrap", action="store_true")
    command.add_argument("--recover-through", type=date.fromisoformat)
    args = parser.parse_args(argv)
    try:
        if args.command == "grow":
            previous = (
                validate_state(read_json(args.state))
                if args.state is not None
                else None
            )
            result = advance(
                read_json(args.snapshot), previous, recover_through=args.recover_through
            )
            print(canonical_json(result), end="")
            return 0
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
