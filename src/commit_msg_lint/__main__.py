"""CLI entry point for commit-msg-lint git hook."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import CommitLintError, Config, lint, suggest


def main(argv: list[str] | None = None) -> int:
    """Run commit-msg-lint CLI.

    Returns:
        0: Clean message
        1: Message has lint findings
        2: Usage error, I/O error, or input exceeds size limit
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="commit-msg-lint",
        description="Validate commit messages against Conventional Commits 1.0.0.",
    )
    parser.add_argument(
        "path",
        help="Path to the commit message file (e.g. .git/COMMIT_EDITMSG)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Rewrite file with suggestion if suggestion lints clean",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code != 0 else 0

    target_path = Path(args.path)
    if not target_path.is_file():
        sys.stderr.write(f"Error: File not found: {args.path}\n")
        return 2

    try:
        raw_bytes = target_path.read_bytes()
        if len(raw_bytes) > 65_536:
            sys.stderr.write(
                f"Error: File exceeds maximum allowed size (65536 bytes): {args.path}\n"
            )
            return 2
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        sys.stderr.write(f"Error: File is not valid UTF-8: {args.path}\n")
        return 2
    except OSError as err:
        sys.stderr.write(f"Error reading file: {err}\n")
        return 2

    config = Config()
    try:
        findings = lint(content, config=config)
    except CommitLintError as err:
        sys.stderr.write(f"Error: {err}\n")
        return 2

    if not findings:
        return 0

    suggestion = suggest(content, config=config)
    if args.fix and suggestion is not None:
        try:
            target_path.write_text(suggestion, encoding="utf-8")
            return 0
        except OSError as err:
            sys.stderr.write(f"Error writing fix to file: {err}\n")
            return 2

    for finding in findings:
        sys.stdout.write(f"{finding}\n")

    if suggestion is not None:
        first_line = suggestion.splitlines()[0] if suggestion else ""
        sys.stdout.write(f"suggestion: {first_line}\n")

    return 1


if __name__ == "__main__":
    sys.exit(main())
