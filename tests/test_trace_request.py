"""Tests for ezeml_log_tools – request-trace deep-dive functionality (trace path)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ezeml_log_tools import get_request_trace, print_trace  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_tmp(content: bytes) -> str:
    """Write *content* to a temporary file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".log")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
    except Exception:
        os.close(fd)
        raise
    return path


# ---------------------------------------------------------------------------
# Sample log fragments
# ---------------------------------------------------------------------------

SAMPLE_BASIC = """\
2026-04-17 10:00:00,000 [PID 100] [INFO] webapp -> **** INCOMING REQUEST: /eml/save [POST]
2026-04-17 10:00:00,100 [PID 100] [INFO] webapp -> step A
2026-04-17 10:00:00,200 [PID 100] [INFO] webapp -> step B
2026-04-17 10:00:00,300 [PID 100] [ERROR] webapp -> 500 Internal Server Error
""".encode()

SAMPLE_MULTI_PID = """\
2026-04-17 11:00:00,000 [PID 200] [INFO] webapp -> **** INCOMING REQUEST: /eml/load [GET]
2026-04-17 11:00:00,050 [PID 300] [INFO] webapp -> **** INCOMING REQUEST: /eml/save [POST]
2026-04-17 11:00:00,100 [PID 200] [INFO] webapp -> step A pid 200
2026-04-17 11:00:00,150 [PID 300] [INFO] webapp -> step A pid 300
2026-04-17 11:00:00,200 [PID 200] [ERROR] webapp -> 500 Internal Server Error
""".encode()

SAMPLE_NO_PRECEDING_REQUEST = """\
2026-04-17 12:00:00,000 [PID 400] [ERROR] webapp -> 500 Internal Server Error
""".encode()

SAMPLE_WITH_TRACEBACK = """\
2026-04-17 13:00:00,000 [PID 500] [INFO] webapp -> **** INCOMING REQUEST: /eml/check [POST]
2026-04-17 13:00:00,100 [PID 500] [ERROR] webapp -> Something went wrong
Traceback (most recent call last):
  File "/webapp/views.py", line 10, in check
    do_check()
ValueError: bad input
2026-04-17 13:00:00,200 [PID 500] [ERROR] webapp -> 500 Internal Server Error
""".encode()

SAMPLE_MULTIPLE_REQUESTS = """\
2026-04-17 14:00:00,000 [PID 600] [INFO] webapp -> **** INCOMING REQUEST: /eml/a [POST]
2026-04-17 14:00:00,100 [PID 600] [INFO] webapp -> step a1
2026-04-17 14:00:00,200 [PID 600] [ERROR] webapp -> 500 Internal Server Error
2026-04-17 14:00:01,000 [PID 600] [INFO] webapp -> **** INCOMING REQUEST: /eml/b [POST]
2026-04-17 14:00:01,100 [PID 600] [INFO] webapp -> step b1
2026-04-17 14:00:01,200 [PID 600] [ERROR] webapp -> 500 Internal Server Error
""".encode()

SAMPLE_NO_MATCH = """\
2026-04-17 15:00:00,000 [PID 700] [INFO] webapp -> **** INCOMING REQUEST: /eml/ok [GET]
2026-04-17 15:00:00,100 [PID 700] [INFO] webapp -> all good
""".encode()


# ---------------------------------------------------------------------------
# Tests for get_request_trace
# ---------------------------------------------------------------------------


def test_returns_lines_from_request_to_match():
    """Trace starts at INCOMING REQUEST and ends at the matched line."""
    path = _write_tmp(SAMPLE_BASIC)
    try:
        trace = get_request_trace(path, r"500 Internal Server Error")
    finally:
        os.unlink(path)

    assert any("INCOMING REQUEST" in line for line in trace)
    assert any("step A" in line for line in trace)
    assert any("step B" in line for line in trace)
    assert any("500 Internal Server Error" in line for line in trace)

    request_idx = next(i for i, l in enumerate(trace) if "INCOMING REQUEST" in l)
    error_idx = next(i for i, l in enumerate(trace) if "500 Internal Server Error" in l)
    assert request_idx < error_idx


def test_excludes_other_pid_lines():
    """Lines from a different PID do not appear in the trace."""
    path = _write_tmp(SAMPLE_MULTI_PID)
    try:
        trace = get_request_trace(path, r"500 Internal Server Error")
    finally:
        os.unlink(path)

    assert trace, "Expected a non-empty trace"
    for line in trace:
        assert "PID 300" not in line, "PID 300 lines must not appear in PID 200 trace"
    assert any("PID 200" in line for line in trace)


def test_no_preceding_request_returns_just_match():
    """When no INCOMING REQUEST precedes the match, only the matched line is returned."""
    path = _write_tmp(SAMPLE_NO_PRECEDING_REQUEST)
    try:
        trace = get_request_trace(path, r"500 Internal Server Error")
    finally:
        os.unlink(path)

    assert len(trace) == 1
    assert "500 Internal Server Error" in trace[0]
    assert "INCOMING REQUEST" not in trace[0]


def test_traceback_continuation_lines_included():
    """Traceback lines (no timestamp header) are included in the trace."""
    path = _write_tmp(SAMPLE_WITH_TRACEBACK)
    try:
        trace = get_request_trace(path, r"500 Internal Server Error")
    finally:
        os.unlink(path)

    assert any("Traceback" in line for line in trace)
    assert any("ValueError" in line for line in trace)
    assert any("INCOMING REQUEST" in line for line in trace)
    assert any("500 Internal Server Error" in line for line in trace)


def test_no_match_returns_empty_list():
    """Returns an empty list when the pattern matches nothing."""
    path = _write_tmp(SAMPLE_NO_MATCH)
    try:
        trace = get_request_trace(path, r"500 Internal Server Error")
    finally:
        os.unlink(path)

    assert trace == []


def test_default_occurrence_returns_last_match():
    """Without specifying occurrence the most recent match is returned."""
    path = _write_tmp(SAMPLE_MULTIPLE_REQUESTS)
    try:
        trace = get_request_trace(path, r"500 Internal Server Error")
    finally:
        os.unlink(path)

    # The last INCOMING REQUEST was /eml/b
    assert any("/eml/b" in line for line in trace)
    assert not any("/eml/a" in line for line in trace)


def test_occurrence_first_returns_oldest_match():
    """occurrence=1 selects the first (oldest) match."""
    path = _write_tmp(SAMPLE_MULTIPLE_REQUESTS)
    try:
        trace = get_request_trace(path, r"500 Internal Server Error", occurrence=1)
    finally:
        os.unlink(path)

    assert any("/eml/a" in line for line in trace)
    assert not any("/eml/b" in line for line in trace)


def test_occurrence_negative_two():
    """occurrence=-2 selects the second-to-last match."""
    path = _write_tmp(SAMPLE_MULTIPLE_REQUESTS)
    try:
        trace = get_request_trace(path, r"500 Internal Server Error", occurrence=-2)
    finally:
        os.unlink(path)

    assert any("/eml/a" in line for line in trace)


def test_case_insensitive_matching():
    """Pattern matching is case-insensitive by default."""
    path = _write_tmp(SAMPLE_BASIC)
    try:
        trace_lower = get_request_trace(path, r"internal server error", ignore_case=True)
        trace_upper = get_request_trace(path, r"INTERNAL SERVER ERROR", ignore_case=True)
    finally:
        os.unlink(path)

    assert trace_lower
    assert trace_upper
    assert trace_lower == trace_upper


def test_case_sensitive_no_match():
    """Case-sensitive matching fails when the case does not match."""
    path = _write_tmp(SAMPLE_BASIC)
    try:
        trace = get_request_trace(path, r"internal server error", ignore_case=False)
    finally:
        os.unlink(path)

    assert trace == []


# ---------------------------------------------------------------------------
# Tests for print_trace
# ---------------------------------------------------------------------------


def test_print_trace_empty(capsys):
    """print_trace() reports that no matching line was found when given []."""
    print_trace([])
    captured = capsys.readouterr()
    assert "No matching line found" in captured.out


def test_print_trace_outputs_all_lines(capsys):
    """print_trace() prints every line in the trace."""
    lines = ["line one", "line two", "line three"]
    print_trace(lines)
    captured = capsys.readouterr()
    for line in lines:
        assert line in captured.out


# ---------------------------------------------------------------------------
# Tests for --literal / full-line matching
# ---------------------------------------------------------------------------

SAMPLE_WITH_USER = """\
2026-04-21 20:07:21,987 [PID 155449] [INFO] webapp -> **** INCOMING REQUEST: /eml/check [POST]
2026-04-21 20:07:21,990 [PID 155449] [INFO] webapp -> step A
2026-04-21 20:07:21,987 [PID 155449] [ERROR] [USER: Colin Smith] webapp -> 500 Internal Server Error
""".encode()


def test_literal_pattern_matches_full_log_line():
    """literal=True matches a pasted log line containing regex metacharacters."""
    # The pattern is an exact prefix of the error line.  Without literal=True
    # the brackets would be interpreted as a regex character class and would
    # fail to match the literal text.
    search_string = "2026-04-21 20:07:21,987 [PID 155449] [ERROR] [USER: Colin Smith]"
    path = _write_tmp(SAMPLE_WITH_USER)
    try:
        trace = get_request_trace(path, search_string, literal=True)
    finally:
        os.unlink(path)

    assert trace, "Expected a non-empty trace for the literal pattern"
    assert any("INCOMING REQUEST" in line for line in trace)
    assert any("500 Internal Server Error" in line for line in trace)


def test_literal_pattern_no_escape_fails_with_special_chars():
    """Without literal=True a regex-invalid string raises an error; literal=True handles it safely."""
    # An unclosed bracket is invalid regex syntax and raises re.error without
    # escaping, but is treated as a plain substring search when literal=True.
    invalid_regex = "[USER: Colin Smith"
    path = _write_tmp(SAMPLE_WITH_USER)
    try:
        # literal=False → expect re.error (invalid regex)
        import re
        raised = False
        try:
            get_request_trace(path, invalid_regex, literal=False)
        except re.error:
            raised = True
        assert raised, "Invalid regex should raise re.error when literal=False"

        # literal=True → no exception; the substring IS found (it's a prefix of
        # "[USER: Colin Smith]") so we should get a non-empty trace.
        trace = get_request_trace(path, invalid_regex, literal=True)
        assert trace, "literal=True should find the line as a plain substring"
        assert any("INCOMING REQUEST" in line for line in trace)
    finally:
        os.unlink(path)


def test_full_line_pattern_matches_header_fields():
    """Pattern is matched against the full raw line, not just the message portion."""
    # Use a pattern that only appears in the header (PID + level), not in the message.
    path = _write_tmp(SAMPLE_WITH_USER)
    try:
        trace = get_request_trace(path, r"PID 155449.*ERROR", ignore_case=False)
    finally:
        os.unlink(path)

    assert trace, "Pattern matching PID+level in the header should return a trace"
    assert any("500 Internal Server Error" in line for line in trace)
