"""Conventional Commits 1.0.0 parser, linter, and fixer.

Exported public API:
- parse(message: str) -> Commit
- Config
- lint(message: str, config: Config = Config()) -> list[Finding]
- suggest(message: str, config: Config = Config()) -> str | None
- CommitLintError
- Commit
- Finding
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

__all__ = [
    "Commit",
    "CommitLintError",
    "Config",
    "Finding",
    "__version__",
    "lint",
    "parse",
    "suggest",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

MAX_INPUT_BYTES = 65_536

# Git scissors line regex
SCISSORS_PATTERN = re.compile(r"^#\s*-{2,}\s*>8\s*-{2,}.*$", re.MULTILINE)

# Conventional Commits 1.0.0 Header regex:
# ^(?P<type>[A-Za-z]+)(\((?P<scope>[^()\r\n]+)\))?(?P<bang>!)?: (?P<desc>\S.*)$
HEADER_RE = re.compile(
    r"^(?P<type>[A-Za-z]+)(?:\((?P<scope>[^()\r\n]+)\))?(?P<bang>!)?: (?P<desc>\S.*)$"
)

# Empty scope detection: e.g. feat(): x
EMPTY_SCOPE_RE = re.compile(r"^(?P<type>[A-Za-z]+)\(\)(?P<bang>!)?: (?P<desc>\S.*)$")

# Footer line regex:
# ^(BREAKING CHANGE|[A-Za-z][A-Za-z0-9-]*)(: | #)(.*)$
FOOTER_START_RE = re.compile(
    r"^(?P<token>BREAKING CHANGE|[A-Za-z][A-Za-z0-9-]*)(?P<sep>: | #)(?P<val>.*)$"
)

# Rule C008 breaking change token regex: (?i)^breaking[ -]change(: | #)
BREAKING_TOKEN_CANDIDATE_RE = re.compile(r"^(?i:breaking[ -]change)(?:: | #)")

# Rule definitions
RULE_MESSAGES = {
    "C001": ("invalid_header", "header must follow Conventional Commits format"),
    "C002": ("type_not_allowed", "commit type is not allowed"),
    "C003": ("type_case", "type must be lowercase"),
    "C004": ("header_too_long", "header exceeds maximum length"),
    "C005": ("description_period", "description must not end with a period"),
    "C006": ("empty_scope", "scope must not be empty"),
    "C007": ("missing_blank_line", "blank line required after header"),
    "C008": (
        "breaking_token",
        "breaking change footer must be 'BREAKING CHANGE' or 'BREAKING-CHANGE'",
    ),
    "C009": ("scope_not_allowed", "scope is not allowed"),
    "C010": ("scope_required", "scope is required"),
}


class CommitLintError(Exception):
    """Base error raised by commit_msg_lint."""

    def __init__(self, message: str, code: str = "input_too_large") -> None:
        # Limit message length to at most 200 characters
        safe_msg = message[:200]
        super().__init__(safe_msg)
        self.code = code


@dataclass(frozen=True)
class Commit:
    """Parsed Conventional Commit message."""

    type: str
    scope: str | None
    breaking: bool
    description: str
    body: str | None
    footers: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Config:
    """Configuration for commit message linting."""

    types: tuple[str, ...] = (
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
    )
    scopes: tuple[str, ...] = ()
    require_scope: bool = False
    max_header: int = 72
    ignore_merges: bool = True


@dataclass(frozen=True)
class Finding:
    """A rule violation found during linting."""

    rule: str
    name: str
    message: str
    line: int

    def __str__(self) -> str:
        return f"{self.rule} {self.name}: {self.message} (line {self.line})"


def clean_message(raw: str) -> list[str]:
    """Clean message according to git commit cleaning rules.

    1. Convert CRLF to LF
    2. Drop everything from the scissors line
    3. Drop lines starting with '#'
    4. Strip trailing blank lines
    """
    # CRLF to LF
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Drop scissors
    scissors_match = SCISSORS_PATTERN.search(text)
    if scissors_match:
        text = text[: scissors_match.start()]

    lines = text.split("\n")
    # Drop lines starting with '#'
    filtered: list[str] = [line for line in lines if not line.startswith("#")]

    # Strip trailing blank lines
    while filtered and filtered[-1] == "":
        filtered.pop()

    return filtered


def _is_merge_or_fixup(header: str) -> bool:
    """Check if header matches git merge, revert, fixup!, or squash! patterns."""
    if header.startswith("Merge "):
        return True
    if header.startswith('Revert "'):
        return True
    return bool(header.startswith("fixup!") or header.startswith("squash!"))


def _extract_footers(paragraphs: list[list[str]]) -> tuple[list[str], list[tuple[str, str]]] | None:
    """Check if trailing paragraph qualifies as footers.

    Footers are the trailing paragraph whose every line (or group of continuation lines)
    matches FOOTER_START_RE with continuation lines appended.
    Returns (body_paragraphs_lines, footers) or None if trailing paragraph is not footers.
    """
    if not paragraphs:
        return None

    last_para = paragraphs[-1]
    if not last_para:
        return None

    # Check if last_para is entirely footers
    # First line must start a footer
    m = FOOTER_START_RE.match(last_para[0])
    if not m:
        return None

    footers: list[tuple[str, str]] = []
    current_token: str | None = None
    current_val: list[str] = []

    for line in last_para:
        match = FOOTER_START_RE.match(line)
        if match:
            if current_token is not None:
                footers.append((current_token, "\n".join(current_val)))
            current_token = match.group("token")
            current_val = [match.group("val")]
        else:
            # Continuation line
            if current_token is None:
                return None
            current_val.append(line)

    if current_token is not None:
        footers.append((current_token, "\n".join(current_val)))

    # Remaining body is preceding paragraphs
    body_lines: list[str] = []
    for i, p in enumerate(paragraphs[:-1]):
        if i > 0:
            body_lines.append("")
        body_lines.extend(p)

    return body_lines, footers


def parse(message: str) -> Commit:
    """Parse a Conventional Commit message.

    Raises:
        CommitLintError: If input exceeds 65,536 UTF-8 bytes or format is invalid.
    """
    if len(message.encode("utf-8")) > MAX_INPUT_BYTES:
        raise CommitLintError("Input exceeds maximum allowed size", code="input_too_large")

    cleaned = clean_message(message)
    if not cleaned:
        raise CommitLintError("Message is empty", code="invalid_header")

    header = cleaned[0]
    match = HEADER_RE.match(header)
    if not match:
        raise CommitLintError(f"Invalid commit header: {header[:50]}", code="invalid_header")

    ctype = match.group("type")
    scope = match.group("scope")
    bang = match.group("bang") == "!"
    desc = match.group("desc")

    body_str: str | None = None
    footers: list[tuple[str, str]] = []

    if len(cleaned) > 1:
        # Group remainder into paragraphs separated by empty lines
        lines_after_header = cleaned[1:]
        # First line of remainder might be empty or not
        # Standard Conventional Commits expects a blank line, but parser parses paragraphs
        paragraphs: list[list[str]] = []
        current_para: list[str] = []
        for line in lines_after_header:
            if line == "":
                if current_para:
                    paragraphs.append(current_para)
                    current_para = []
            else:
                current_para.append(line)
        if current_para:
            paragraphs.append(current_para)

        footer_res = _extract_footers(paragraphs)
        if footer_res is not None:
            body_lines, footers = footer_res
            body_str = "\n".join(body_lines) if body_lines else None
        else:
            # All paragraphs form the body
            body_lines = []
            for i, p in enumerate(paragraphs):
                if i > 0:
                    body_lines.append("")
                body_lines.extend(p)
            body_str = "\n".join(body_lines) if body_lines else None

    # Determine breaking
    breaking = bang
    for token, _ in footers:
        if token in ("BREAKING CHANGE", "BREAKING-CHANGE"):
            breaking = True
            break

    return Commit(
        type=ctype,
        scope=scope,
        breaking=breaking,
        description=desc,
        body=body_str,
        footers=tuple(footers),
    )


DEFAULT_CONFIG = Config()


def lint(message: str, config: Config = DEFAULT_CONFIG) -> list[Finding]:
    """Lint a commit message against Conventional Commits 1.0.0 and rules C001-C010.

    Returns a list of findings sorted by (line, rule).
    """
    if len(message.encode("utf-8")) > MAX_INPUT_BYTES:
        raise CommitLintError("Input exceeds maximum allowed size", code="input_too_large")

    cleaned = clean_message(message)
    if not cleaned:
        rule_id = "C001"
        name, desc = RULE_MESSAGES[rule_id]
        return [Finding(rule=rule_id, name=name, message=desc, line=1)]

    header = cleaned[0]

    # Check ignore_merges
    if config.ignore_merges and _is_merge_or_fixup(header):
        return []

    findings: list[Finding] = []

    # Check C007: missing_blank_line (line 2 of cleaned message not empty if there are > 1 lines)
    if len(cleaned) > 1 and cleaned[1] != "":
        name, desc = RULE_MESSAGES["C007"]
        findings.append(Finding(rule="C007", name=name, message=desc, line=2))

    # Match header
    header_match = HEADER_RE.match(header)
    if not header_match:
        # Check if empty scope triggered
        empty_scope_match = EMPTY_SCOPE_RE.match(header)
        if empty_scope_match:
            name, desc = RULE_MESSAGES["C006"]
            findings.append(Finding(rule="C006", name=name, message=desc, line=1))
            # Empty scope is evaluated along with other rules.
            # If empty_scope_match is present, report C006.
        else:
            name, desc = RULE_MESSAGES["C001"]
            findings.append(Finding(rule="C001", name=name, message=desc, line=1))
            # "When C001 fires only C001 and C007 are evaluated."
            findings.sort(key=lambda f: (f.line, f.rule))
            return findings

    # If header matched, evaluate C002, C003, C004, C005, C009, C010
    if header_match:
        ctype = header_match.group("type")
        scope = header_match.group("scope")
        desc = header_match.group("desc")

        # C003: type_case (type must be lowercase)
        if ctype != ctype.lower():
            name, msg = RULE_MESSAGES["C003"]
            findings.append(Finding(rule="C003", name=name, message=msg, line=1))

        # C002: type_not_allowed (compared lowercase)
        if ctype.lower() not in [t.lower() for t in config.types]:
            name, msg = RULE_MESSAGES["C002"]
            findings.append(Finding(rule="C002", name=name, message=msg, line=1))

        # C004: header_too_long (code points)
        if len(header) > config.max_header:
            name, msg = RULE_MESSAGES["C004"]
            findings.append(Finding(rule="C004", name=name, message=msg, line=1))

        # C005: description_period (ends with '.')
        if desc.endswith("."):
            name, msg = RULE_MESSAGES["C005"]
            findings.append(Finding(rule="C005", name=name, message=msg, line=1))

        # C006: empty scope (already handled if regex didn't match, but just in case)
        # C009: scope_not_allowed (when scopes is non-empty)
        if scope is not None and config.scopes and scope not in config.scopes:
            name, msg = RULE_MESSAGES["C009"]
            findings.append(Finding(rule="C009", name=name, message=msg, line=1))

        # C010: scope_required
        if config.require_scope and (scope is None or scope == ""):
            name, msg = RULE_MESSAGES["C010"]
            findings.append(Finding(rule="C010", name=name, message=msg, line=1))
    elif empty_scope_match:
        # Also check C004, C005, etc. on empty_scope_match
        ctype = empty_scope_match.group("type")
        desc = empty_scope_match.group("desc")
        if ctype != ctype.lower():
            name, msg = RULE_MESSAGES["C003"]
            findings.append(Finding(rule="C003", name=name, message=msg, line=1))
        if ctype.lower() not in [t.lower() for t in config.types]:
            name, msg = RULE_MESSAGES["C002"]
            findings.append(Finding(rule="C002", name=name, message=msg, line=1))
        if len(header) > config.max_header:
            name, msg = RULE_MESSAGES["C004"]
            findings.append(Finding(rule="C004", name=name, message=msg, line=1))
        if desc.endswith("."):
            name, msg = RULE_MESSAGES["C005"]
            findings.append(Finding(rule="C005", name=name, message=msg, line=1))
        if config.require_scope:
            name, msg = RULE_MESSAGES["C010"]
            findings.append(Finding(rule="C010", name=name, message=msg, line=1))

    # Check C008: breaking_token
    # A line matching (?i)^breaking[ -]change(: | #) must be spelled
    # exactly BREAKING CHANGE or BREAKING-CHANGE.
    if len(cleaned) > 1:
        # Find the start of the last paragraph
        # Walk backwards
        last_para_lines: list[tuple[int, str]] = []  # (1-based line number in cleaned, line)
        in_last_para = False
        for line_idx in range(len(cleaned) - 1, 0, -1):  # don't include line 0 (header)
            line_text = cleaned[line_idx]
            if line_text != "":
                in_last_para = True
                last_para_lines.append((line_idx + 1, line_text))
            elif in_last_para:
                # Reached empty line before last paragraph
                break

        # Check lines in last paragraph in normal order
        for line_num, line_text in reversed(last_para_lines):
            if BREAKING_TOKEN_CANDIDATE_RE.match(line_text) and not (
                line_text.startswith("BREAKING CHANGE: ")
                or line_text.startswith("BREAKING CHANGE #")
                or line_text.startswith("BREAKING-CHANGE: ")
                or line_text.startswith("BREAKING-CHANGE #")
            ):
                name, msg = RULE_MESSAGES["C008"]
                findings.append(Finding(rule="C008", name=name, message=msg, line=line_num))

    # Findings sort by line then rule
    findings.sort(key=lambda f: (f.line, f.rule))
    return findings


# Alias map for suggest
TYPE_ALIASES = {
    "feature": "feat",
    "bugfix": "fix",
    "fixes": "fix",
    "doc": "docs",
    "tests": "test",
}

# Regex to match header components for suggestion
# e.g., 'Feature: Add thing.', 'fix:correct', 'Feature(api): Add thing.'
SUGGEST_HEADER_RE = re.compile(
    r"^(?P<type>[A-Za-z]+)(?P<scope>\([^()\r\n]+\))?(?P<bang>!)?:(?P<space>\s*)(?P<desc>.*)$"
)


def suggest(message: str, config: Config = DEFAULT_CONFIG) -> str | None:
    """Propose a safe corrected commit message, or None.

    Applies only these fixes, in order:
    1. Map type alias (feature->feat, bugfix->fix, etc.) and lowercase it
    2. Insert a missing space after ':'
    3. Drop one trailing '.' from the description
    4. Insert the blank line after the header

    Returns the result only when the original had findings and the result lints clean, else None.
    """
    if len(message.encode("utf-8")) > MAX_INPUT_BYTES:
        raise CommitLintError("Input exceeds maximum allowed size", code="input_too_large")

    initial_findings = lint(message, config)
    if not initial_findings:
        return None

    cleaned = clean_message(message)
    if not cleaned:
        return None

    header = cleaned[0]
    rest = cleaned[1:]

    # Attempt to parse header for fixing
    match = SUGGEST_HEADER_RE.match(header)
    new_header = header
    if match:
        raw_type = match.group("type")
        raw_scope = match.group("scope") or ""
        raw_bang = match.group("bang") or ""
        raw_space = match.group("space")
        raw_desc = match.group("desc")

        # 1. Map type alias and lowercase it
        lower_type = raw_type.lower()
        fixed_type = TYPE_ALIASES.get(lower_type, lower_type)

        # 2. Insert a missing space after ':'
        # If space was empty, make it a single space ' '
        fixed_space = raw_space if raw_space else " "

        # 3. Drop one trailing '.' from the description
        fixed_desc = raw_desc
        if fixed_desc.endswith("."):
            fixed_desc = fixed_desc[:-1]

        new_header = f"{fixed_type}{raw_scope}{raw_bang}:{fixed_space}{fixed_desc}"

    # 4. Insert blank line after header if rest starts immediately
    new_lines = [new_header]
    if rest:
        if rest[0] != "":
            new_lines.append("")
        new_lines.extend(rest)

    candidate = "\n".join(new_lines)
    if candidate == message:
        return None

    candidate_findings = lint(candidate, config)
    if not candidate_findings:
        return candidate

    return None
