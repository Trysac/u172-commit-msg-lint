# Use Pure Standard-Library Parser and Rule Engine for Conventional Commits

Status: accepted (generated, pending human review)

## Context

Release tooling and changelog generators rely on Conventional Commits 1.0.0. Existing linters like @commitlint/cli require a full Node.js runtime and dependency chain in repositories that are otherwise purely Python. Contributors often face cryptic commit hook failures without automated fix suggestions.

## Decision

Implement a pure Python standard-library parser, linter, and suggestion engine adhering strictly to Conventional Commits 1.0.0. The engine enforces an explicit 64 KiB input ceiling, handles git comments and scissors markers, evaluates ten deterministic rules (C001-C010), and proposes conservative corrections for alias naming, spacing, trailing punctuation, and missing blank lines.

## Consequences

Zero external runtime dependencies. Consistent behavior across local git hooks and CI runners. Fix suggestions are guaranteed to be clean under the configured lint rules before being suggested or applied.
