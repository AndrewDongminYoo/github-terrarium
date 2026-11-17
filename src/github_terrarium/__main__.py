"""Collection, offline growth, bundle, publication, generation, and restore commands."""

import argparse
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .bundle import build_files, source_commit, validate_bundle, write_bundle
from .config import load_config
from .generate import generate, summary_markdown
from .github import GraphQLClient
from .growth import advance
from .models import canonical_json
from .normalize import collect
from .probe import probe
from .publish import PublishConflict, expected_parent, publish, repository, restore
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
    command = commands.add_parser(
        "build", help="Build and validate a three-file output bundle offline"
    )
    command.add_argument("--snapshot", type=Path, required=True)
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--state", type=Path)
    source.add_argument("--bootstrap", action="store_true")
    command.add_argument("--bundle-dir", type=Path, required=True)
    command.add_argument("--source-commit", type=source_commit, required=True)
    command = commands.add_parser(
        "validate", help="Validate an existing three-file output bundle"
    )
    command.add_argument("--bundle-dir", type=Path, required=True)
    command = commands.add_parser(
        "publish", help="Publish a bundle to the output branch without force"
    )
    command.add_argument("--bundle-dir", type=Path, required=True)
    command.add_argument("--repository", type=repository, required=True)
    command.add_argument("--expected-parent", type=expected_parent, required=True)
    command.add_argument("--bootstrap", action="store_true")
    command.add_argument("--remote", help="Override the GitHub remote URL")
    command = commands.add_parser(
        "restore", help="Restore a historical output bundle through a new commit"
    )
    command.add_argument("--repository", type=repository, required=True)
    command.add_argument("--from-commit", type=source_commit, required=True)
    command.add_argument("--expected-parent", type=source_commit, required=True)
    command.add_argument("--remote", help="Override the GitHub remote URL")
    command = commands.add_parser(
        "generate", help="Collect, grow, build, and publish with one conflict retry"
    )
    command.add_argument("--config", type=Path, required=True)
    command.add_argument("--repository", type=repository, required=True)
    command.add_argument("--bootstrap", action="store_true")
    command.add_argument(
        "--source-commit",
        type=source_commit,
        default=os.environ.get("GITHUB_SHA"),
        help="Defaults to GITHUB_SHA",
    )
    command.add_argument("--remote", help="Override the GitHub remote URL")
    command.add_argument(
        "--summary", type=Path, help="Append a Markdown job summary to this file"
    )
    args = parser.parse_args(argv)
    if args.command == "generate" and args.source_commit is None:
        parser.error("--source-commit or GITHUB_SHA is required")
    if args.command == "publish" and (args.expected_parent == "absent") != (
        args.bootstrap
    ):
        parser.error("--bootstrap requires --expected-parent absent and vice versa")
    try:
        if args.command == "generate":
            result = generate(
                load_config(args.config, args.repository),
                args.repository,
                args.source_commit,
                bootstrap=args.bootstrap,
                remote=args.remote,
                token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
            )
            print(canonical_json(result), end="")
            _summary(args, result)
            return 0
        if args.command == "publish":
            result = publish(
                args.bundle_dir,
                args.repository,
                args.expected_parent,
                bootstrap=args.bootstrap,
                remote=args.remote,
                token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
            )
            print(canonical_json(result), end="")
            return 0
        if args.command == "restore":
            result = restore(
                args.repository,
                args.from_commit,
                args.expected_parent,
                remote=args.remote,
                token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
            )
            print(canonical_json(result), end="")
            return 0
        if args.command == "build":
            previous = (
                validate_state(read_json(args.state))
                if args.state is not None
                else None
            )
            files = build_files(
                advance(read_json(args.snapshot), previous), args.source_commit
            )
            result = write_bundle(files, args.bundle_dir, previous=previous)
            print(canonical_json(result), end="")
            return 0
        if args.command == "validate":
            print(canonical_json(validate_bundle(args.bundle_dir)), end="")
            return 0
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
    except PublishConflict as error:
        print(f"conflict: {error}", file=sys.stderr)
        _summary(args, code=3, message=f"conflict: {error}")
        return 3
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        _summary(args, code=1, message=f"error: {error}")
        return 1
    print(canonical_json(result), end="")
    return 0


def _summary(args, result=None, *, code=0, message=None):
    """Append a `generate --summary` report; a write failure keeps the exit code."""
    path = getattr(args, "summary", None)
    if path is None:
        return
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    text = summary_markdown(result, code=code, message=message, token=token)
    try:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(text)
    except OSError as error:
        print(f"warning: summary not written: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
