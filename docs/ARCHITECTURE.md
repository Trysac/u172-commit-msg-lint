# Architecture

## Design Overview

`commit-msg-lint` is an enterprise-grade Conventional Commits 1.0.0 parser and linter written in Python using only the standard library.

### Pipeline

1. **Input Size Check**: Every entrypoint (`parse`, `lint`, `suggest`, `main`) enforces `MAX_INPUT_BYTES = 65_536`.
2. **Git Cleaning**:
   - Normalizes CRLF and CR to LF.
   - Removes git scissors comments (`# ------------------------ >8 ------------------------` and all subsequent content).
   - Drops lines starting with `#`.
   - Drops trailing blank lines.
3. **Merge and Revert Bypass**:
   - If `config.ignore_merges` is active, commits matching git defaults (`Merge `, `Revert "`, `fixup!`, `squash!`) pass immediately.
4. **Header and Body Parsing**:
   - Header regex: `^(?P<type>[A-Za-z]+)(\((?P<scope>[^()\r\n]+)\))?(?P<bang>!)?: (?P<desc>\S.*)$`.
   - Blank line check: Line 2 must be blank if body/footers exist (`C007`).
   - Trailing footers regex: `^(BREAKING CHANGE|[A-Za-z][A-Za-z0-9-]*)(: | #)(.*)$`.
   - Continuation lines within a footer block are merged into the active footer value.
5. **Deterministic Rule Engine**:
   - Rules evaluate C001 through C010.
   - When `C001` fires, only `C001` and `C007` are evaluated.
   - Results are sorted by `(line, rule)`.
6. **Safe Auto-Suggestion Engine**:
   - Applies aliases (`feature` -> `feat`, `bugfix` / `fixes` -> `fix`, `doc` -> `docs`, `tests` -> `test`).
   - Inserts missing space after `:`.
   - Strips single trailing `.`;
   - Inserts blank line after line 1.
   - Returns suggestion only if original had findings and suggestion passes all rules cleanly.
