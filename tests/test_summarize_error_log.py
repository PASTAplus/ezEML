"""Tests for ezeml_log_tools – preceding-context capture and display (summarize path)."""

import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ezeml_log_tools import parse_log, summarize  # noqa: E402

# ---------------------------------------------------------------------------
# Sample log fragments
# ---------------------------------------------------------------------------

SAMPLE_LOG_PRECEDING = """\
2026-04-17 06:43:03,560 [PID 2447] [ERROR] webapp -> Exception on /eml/check_data_tables [POST]
2026-04-17 06:43:03,561 [PID 2447] [ERROR] webapp -> 500 Internal Server Error
""".encode()

SAMPLE_LOG_NO_PRECEDING = """\
2026-04-17 07:00:00,000 [PID 9999] [ERROR] webapp -> 500 Internal Server Error
""".encode()

SAMPLE_LOG_TRACEBACK_BETWEEN = """\
2026-04-17 08:00:00,000 [PID 1111] [INFO] webapp -> **** INCOMING REQUEST: /eml/save [POST]
2026-04-17 08:00:00,100 [PID 1111] [ERROR] webapp -> Something went wrong
Traceback (most recent call last):
  File "/webapp/views.py", line 42, in save
    do_save()
ValueError: bad value
2026-04-17 08:00:00,200 [PID 1111] [ERROR] webapp -> 500 Internal Server Error
""".encode()

SAMPLE_LOG_DIFFERENT_PID = """\
2026-04-17 09:00:00,000 [PID 1234] [INFO] webapp -> **** INCOMING REQUEST: /eml/load [GET]
2026-04-17 09:00:01,000 [PID 5678] [ERROR] webapp -> 500 Internal Server Error
""".encode()


def _write_tmp(content: bytes) -> str:
    """Write *content* to a named temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".log")
    os.write(fd, content)
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# parse_log tests
# ---------------------------------------------------------------------------


def test_preceding_line_same_pid():
    """Preceding timestamped record for the same PID is captured."""
    path = _write_tmp(SAMPLE_LOG_PRECEDING)
    try:
        events = parse_log(path, r"500 Internal Server Error", ignore_case=False)
    finally:
        os.unlink(path)

    assert len(events) == 1
    event = events[0]
    assert event.preceding_line is not None
    assert "Exception on /eml/check_data_tables [POST]" in event.preceding_line


def test_no_preceding_line_when_first_record():
    """When the error is the very first record for a PID, preceding_line is None."""
    path = _write_tmp(SAMPLE_LOG_NO_PRECEDING)
    try:
        events = parse_log(path, r"500 Internal Server Error", ignore_case=False)
    finally:
        os.unlink(path)

    assert len(events) == 1
    assert events[0].preceding_line is None


def test_preceding_line_skips_traceback_continuation():
    """When a traceback falls between two timestamped records the preceding
    line reported is the last *timestamped* record for that PID, not a
    traceback continuation line."""
    path = _write_tmp(SAMPLE_LOG_TRACEBACK_BETWEEN)
    try:
        events = parse_log(path, r"500 Internal Server Error", ignore_case=False)
    finally:
        os.unlink(path)

    assert len(events) == 1
    event = events[0]
    # The preceding line must be a timestamped record, not a traceback line.
    assert event.preceding_line is not None
    assert event.preceding_line.startswith("2026-04-17")
    assert "Something went wrong" in event.preceding_line
    assert "Traceback" not in event.preceding_line
    assert "File " not in event.preceding_line


def test_no_preceding_line_for_different_pid():
    """A record from a different PID does not appear as the preceding line."""
    path = _write_tmp(SAMPLE_LOG_DIFFERENT_PID)
    try:
        events = parse_log(path, r"500 Internal Server Error", ignore_case=False)
    finally:
        os.unlink(path)

    assert len(events) == 1
    # PID 5678 has never been seen before, so preceding_line should be None.
    assert events[0].preceding_line is None


# ---------------------------------------------------------------------------
# summarize() output tests
# ---------------------------------------------------------------------------


def _capture_summarize(events, show_recent=10, show_traceback_lines=0, top_n=5):
    """Run summarize() and return captured stdout as a string."""
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        summarize(
            events=events,
            top_n=top_n,
            show_recent=show_recent,
            show_traceback_lines=show_traceback_lines,
        )
    finally:
        sys.stdout = old_stdout
    return captured.getvalue()


def test_summarize_prints_preceding_line():
    """summarize() prints a 'Prev' line when preceding_line is set."""
    path = _write_tmp(SAMPLE_LOG_PRECEDING)
    try:
        events = parse_log(path, r"500 Internal Server Error", ignore_case=False)
    finally:
        os.unlink(path)

    output = _capture_summarize(events)
    assert "Prev" in output
    assert "Exception on /eml/check_data_tables [POST]" in output


def test_summarize_omits_preceding_line_when_none():
    """summarize() does not print a 'Prev' line when preceding_line is None."""
    path = _write_tmp(SAMPLE_LOG_NO_PRECEDING)
    try:
        events = parse_log(path, r"500 Internal Server Error", ignore_case=False)
    finally:
        os.unlink(path)

    output = _capture_summarize(events)
    assert "Prev" not in output


def test_summarize_preceding_line_with_traceback_enabled():
    """Preceding line display is unaffected by traceback display being enabled."""
    path = _write_tmp(SAMPLE_LOG_PRECEDING)
    try:
        events = parse_log(path, r"500 Internal Server Error", ignore_case=False)
    finally:
        os.unlink(path)

    output_no_tb = _capture_summarize(events, show_traceback_lines=0)
    output_with_tb = _capture_summarize(events, show_traceback_lines=5)

    for output in (output_no_tb, output_with_tb):
        assert "Prev" in output
        assert "Exception on /eml/check_data_tables [POST]" in output


def test_summarize_no_route_in_output():
    """summarize() does not print 'Top routes' section or per-event Route field."""
    path = _write_tmp(SAMPLE_LOG_PRECEDING)
    try:
        events = parse_log(path, r"500 Internal Server Error", ignore_case=False)
    finally:
        os.unlink(path)

    output = _capture_summarize(events)
    assert "Top routes" not in output
    assert "Route    :" not in output
