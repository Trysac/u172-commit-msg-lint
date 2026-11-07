"""Tests for commit_msg_lint exercising all acceptance criteria and rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from commit_msg_lint import (
    CommitLintError,
    Config,
    lint,
    parse,
    suggest,
)
from commit_msg_lint.__main__ import main


def test_acceptance_item_1() -> None:
    msg = "feat(api)!: add v2 endpoint\n\nBody text\n\nBREAKING CHANGE: v1 removed\nRefs: #12"
    c = parse(msg)
    assert c.type == "feat"
    assert c.scope == "api"
    assert c.breaking is True
    assert c.description == "add v2 endpoint"
    assert c.body == "Body text"
    assert list(c.footers) == [("BREAKING CHANGE", "v1 removed"), ("Refs", "#12")]


def test_acceptance_item_2() -> None:
    assert lint("fix: correct rounding") == []
    assert [f.rule for f in lint("Fix: correct rounding")] == ["C003"]
    assert [f.rule for f in lint("feature: x")] == ["C002"]
    assert [f.rule for f in lint("fix correct rounding")] == ["C001"]


def test_acceptance_item_3() -> None:
    assert [f.rule for f in lint("fix: correct rounding.")] == ["C005"]

    header_73 = "fix: " + "a" * 68
    assert len(header_73) == 73
    assert [f.rule for f in lint(header_73)] == ["C004"]

    findings_missing_blank = lint("fix: a\nbody")
    assert [f.rule for f in findings_missing_blank] == ["C007"]
    assert findings_missing_blank[0].line == 2


def test_acceptance_item_4() -> None:
    res_c008 = lint("feat: x\n\nbreaking change: y")
    assert [f.rule for f in res_c008] == ["C008"]

    parsed_breaking_dash = parse("feat: x\n\nBREAKING-CHANGE: y")
    assert parsed_breaking_dash.breaking is True
    assert lint("feat: x\n\nBREAKING-CHANGE: y") == []

    parsed_closes = parse("feat: x\n\nCloses #12")
    assert parsed_closes.footers == (("Closes", "12"),)


def test_acceptance_item_5() -> None:
    cfg_scopes = Config(scopes=("api", "cli"))
    assert [f.rule for f in lint("feat(web): x", config=cfg_scopes)] == ["C009"]
    assert lint("feat(api): x", config=cfg_scopes) == []

    cfg_req_scope = Config(require_scope=True)
    assert [f.rule for f in lint("feat: x", config=cfg_req_scope)] == ["C010"]
    assert lint("feat(api): x", config=cfg_req_scope) == []


def test_acceptance_item_6() -> None:
    assert suggest("Feature: Add thing.") == "feat: Add thing"
    assert suggest("fix:correct\nbody") == "fix: correct\n\nbody"
    assert suggest("random text") is None


def test_acceptance_item_7() -> None:
    msg = (
        "fix: correct rounding\n"
        "# This is a comment\n"
        "# ------------------------ >8 ------------------------\n"
        "bad: header here that would fail\n"
    )
    assert lint(msg) == []

    assert lint("Merge branch 'main' into x") == []
    assert lint('Revert "feat: x"') == []

    # Also test fixup! and squash!
    assert lint("fixup! fix: x") == []
    assert lint("squash! fix: x") == []

    # Test ignore_merges=False
    cfg_no_ignore = Config(ignore_merges=False)
    assert len(lint("Merge branch 'main' into x", config=cfg_no_ignore)) > 0


def test_acceptance_item_8(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = tmp_path / "cli_test"
    d.mkdir()

    # Test 1: invalid message
    f1 = d / "c1.txt"
    f1.write_text("Fix: correct rounding", encoding="utf-8")
    code1 = main([str(f1)])
    captured1 = capsys.readouterr()
    assert code1 == 1
    assert "C003 type_case: type must be lowercase (line 1)" in captured1.out
    assert "suggestion: fix: correct rounding" in captured1.out

    # Test 2: valid message returns 0 with no output
    f2 = d / "c2.txt"
    f2.write_text("fix: correct rounding", encoding="utf-8")
    code2 = main([str(f2)])
    captured2 = capsys.readouterr()
    assert code2 == 0
    assert captured2.out == ""
    assert captured2.err == ""

    # Test 3: missing file returns 2
    code3 = main([str(d / "nonexistent.txt")])
    assert code3 == 2

    # Test 4: file over 65_536 bytes returns 2
    f4 = d / "c4.txt"
    f4.write_bytes(b"a" * 65_537)
    code4 = main([str(f4)])
    assert code4 == 2


def test_c006_empty_scope() -> None:
    findings = lint("feat(): x")
    assert any(f.rule == "C006" for f in findings)


def test_c001_with_c007() -> None:
    # When C001 fires, only C001 and C007 are evaluated
    findings = lint("not a conventional commit\nbody without blank line")
    rules = [f.rule for f in findings]
    assert rules == ["C001", "C007"]


def test_size_limit_exceptions() -> None:
    large_input = "feat: " + ("a" * 65_536)
    with pytest.raises(CommitLintError) as exc_info:
        parse(large_input)
    assert exc_info.value.code == "input_too_large"

    with pytest.raises(CommitLintError) as exc_info:
        lint(large_input)
    assert exc_info.value.code == "input_too_large"

    with pytest.raises(CommitLintError) as exc_info:
        suggest(large_input)
    assert exc_info.value.code == "input_too_large"


def test_parse_empty_or_all_comments() -> None:
    with pytest.raises(CommitLintError) as exc:
        parse("")
    assert exc.value.code == "invalid_header"

    with pytest.raises(CommitLintError) as exc:
        parse("# only comments")
    assert exc.value.code == "invalid_header"

    # lint on empty gives C001
    assert [f.rule for f in lint("")] == ["C001"]


def test_footer_continuations_and_multiline_body() -> None:
    msg = (
        "feat: add feature\n\n"
        "Para 1 line 1\n"
        "Para 1 line 2\n\n"
        "Para 2 line 1\n\n"
        "BREAKING CHANGE: something changed\n"
        " with continuation details\n"
        "Signed-off-by: Alice <test@example.com>"
    )
    c = parse(msg)
    assert c.type == "feat"
    assert c.scope is None
    assert c.breaking is True
    assert c.description == "add feature"
    assert c.body == "Para 1 line 1\nPara 1 line 2\n\nPara 2 line 1"
    assert len(c.footers) == 2
    assert c.footers[0] == ("BREAKING CHANGE", "something changed\n with continuation details")
    assert c.footers[1] == ("Signed-off-by", "Alice <test@example.com>")


def test_suggest_aliases_and_fixes() -> None:
    assert suggest("bugfix: fix issue") == "fix: fix issue"
    assert suggest("fixes: fix issue") == "fix: fix issue"
    assert suggest("doc: update readme") == "docs: update readme"
    assert suggest("tests: add suite") == "test: add suite"
    # If already clean, suggest returns None
    assert suggest("fix: already valid") is None


def test_cli_fix_flag(tmp_path: Path) -> None:
    f = tmp_path / "cli_fix" / "msg.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("Feature: Add new button.\nbody text", encoding="utf-8")
    ret = main([str(f), "--fix"])
    assert ret == 0
    assert f.read_text(encoding="utf-8") == "feat: Add new button\n\nbody text"


def test_cli_invalid_args() -> None:
    # No args
    assert main([]) == 2


def test_cli_additional_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Test argv default to sys.argv
    f = tmp_path / "sys_argv_test.txt"
    f.write_text("fix: test sys argv", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["commit-msg-lint", str(f)])
    assert main() == 0

    # Non-utf8 file
    f_non_utf8 = tmp_path / "non_utf8.bin"
    f_non_utf8.write_bytes(b"\xff\xfe\x00\x00")
    assert main([str(f_non_utf8)]) == 2

    # Finding representation
    from commit_msg_lint import Finding

    fd = Finding("C001", "invalid_header", "some error", 1)
    assert str(fd) == "C001 invalid_header: some error (line 1)"

    # Empty scope with case issue, long header, period, etc.
    empty_scope_findings = lint("FEAT(): " + "x" * 70 + ".", config=Config(require_scope=True))
    rules = [f.rule for f in empty_scope_findings]
    assert "C006" in rules
    assert "C003" in rules
    assert "C004" in rules
    assert "C005" in rules
    assert "C010" in rules

    # Not allowed type on empty scope
    empty_scope_not_allowed = lint("custom(): x")
    assert "C002" in [f.rule for f in empty_scope_not_allowed]

    # Non-empty scopes config validation
    cfg_scopes = Config(scopes=("core", "ui"))
    assert lint("feat: x", config=cfg_scopes) == []
    assert [f.rule for f in lint("feat(other): x", config=cfg_scopes)] == ["C009"]

    # Parse body with non-footer paragraphs
    c_multibody = parse("feat: header\n\nbody line 1\n\nbody line 2\nnot a footer")
    assert c_multibody.footers == ()
    assert c_multibody.body == "body line 1\n\nbody line 2\nnot a footer"

    # Clean message stripping multiple blank lines
    from commit_msg_lint import clean_message

    assert clean_message("feat: x\n\n\n") == ["feat: x"]

    # Suggest with rest having a blank line already (rest[0] == "")
    assert suggest("feature: something\n\nalready blank") == "feat: something\n\nalready blank"
    # Suggest returning None if candidate still has findings
    assert suggest("feature: something.\n\nbreaking change: bad") is None
    # Suggest on empty message
    assert suggest("") is None
