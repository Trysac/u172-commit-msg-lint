# commit-msg-lint

Validate commit messages against Conventional Commits 1.0.0 with ten rules, git comment and scissors handling, and conservative automatic fix suggestions for a commit-msg hook.

## Features

- **Strict Conventional Commits 1.0.0**: Exact grammar matching for header (`type(scope)!: description`), body, and footers (`BREAKING CHANGE: ...`, `Closes #12`).
- **Ten deterministic rules**: C001 through C010 with structured findings sorted by line and rule ID.
- **Git-aware**: Automatically strips git comments (`#`), strips everything after the scissors line (`# ------------------------ >8 ------------------------`), and ignores default Git merge and revert commits.
- **Safe suggestions**: Proposes targeted fixes (alias mapping, missing space after colon, trailing period removal, missing blank line insertion) only when the resulting message lints cleanly.
- **Hook and CLI**: Usable directly as `.git/hooks/commit-msg` with optional `--fix` mode.
- **Zero runtime dependencies**: Pure Python standard library.

## Installation

```bash
pip install commit-msg-lint
```

## Usage Example

```python
from commit_msg_lint import Config, lint, parse, suggest

commit = parse("feat(api)!: add v2 endpoint\n\nBody text\n\nBREAKING CHANGE: v1 removed\nRefs: #12")
assert commit.type == "feat" and commit.breaking is True

findings = lint("Fix: correct rounding.")
# [Finding(rule='C003', ...), Finding(rule='C005', ...)]

fixed = suggest("Fix: correct rounding.")
assert fixed == "fix: correct rounding"
```

## Public API Summary

- `parse(message: str) -> Commit`: Parses input into a `Commit` object.
- `Config`: Configuration dataclass for linting (types, scopes, require_scope, max_header, ignore_merges).
- `lint(message: str, config: Config = Config()) -> list[Finding]`: Returns rule violations, sorted by line and rule ID.
- `suggest(message: str, config: Config = Config()) -> str | None`: Returns a suggested fix string or `None` if no fix is possible or safe.
- `CommitLintError`: Exception raised for inputs exceeding 65,536 bytes or invalid format.
- `Commit`, `Finding`: Dataclasses representing parsed state and rule violations.

## Why not conventional-commits/commitlint?

This utility provides an exact grammar-based Conventional Commits 1.0.0 implementation without requiring a Node.js toolchain, and offers safe, deterministic fix suggestions that only apply if they result in a clean lint.

## Security

See [docs/SECURITY.md](docs/SECURITY.md) for details on the threat model.
