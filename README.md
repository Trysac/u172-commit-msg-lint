# commit-msg-lint

[![PyPI version](https://img.shields.io/pypi/v/trysac-commit-msg-lint)](https://pypi.org/project/trysac-commit-msg-lint/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-commit-msg-lint)](LICENSE)
[![CI](https://github.com/Trysac/u172-commit-msg-lint/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u172-commit-msg-lint/actions/workflows/ci.yml)

Validate commit messages against Conventional Commits 1.0.0 with ten rules, git comment and scissors handling, and conservative automatic fix suggestions for a commit-msg hook

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-commit-msg-lint
# or
uv add trysac-commit-msg-lint
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import commit_msg_lint

# normalize() trims surrounding whitespace and lower-cases the text.
print(commit_msg_lint.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    commit_msg_lint.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
