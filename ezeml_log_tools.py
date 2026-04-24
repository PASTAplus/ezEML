#!/usr/bin/env python3
"""Log analysis tools for ezEML server logs.

This module provides two complementary tools for diagnosing errors in ezEML
application logs:

**Summarize** — scan a log file for lines matching a pattern (e.g. all
``500 Internal Server Error`` occurrences), then print aggregate statistics
(counts by function, exception class, and day) together with a "most-recent N
errors" detail section.  Each detail entry includes the immediately preceding
timestamped log record for the same process, giving operators instant context
without having to dig through the raw file.

**Trace** — given a search string that identifies a specific error line,
return every log line for that process from the nearest preceding
``**** INCOMING REQUEST:`` through the matched line (inclusive of any
traceback continuation lines).  The result is a self-contained, chronological
snippet that shows the exact sequence of steps the server executed before the
error occurred.

Command-line usage
------------------
Summarize all 500 errors in a log file::

    python ezeml_log_tools.py summarize webapp/ezeml-log.txt

Summarize with a custom pattern and show the last 20 errors::

    python ezeml_log_tools.py summarize webapp/ezeml-log.txt \\
        --error-pattern "500 Internal Server Error" \\
        --show-recent 20

Show the request trace for the most recent 500 error::

    python ezeml_log_tools.py trace webapp/ezeml-log.txt

Trace a specific error line using a literal (non-regex) search string::

    python ezeml_log_tools.py trace webapp/ezeml-log.txt \\
        --pattern "2026-04-21 20:07:21,987 [PID 155449] [ERROR] [USER: Colin Smith]" \\
        --literal

Trace the first (oldest) occurrence::

    python ezeml_log_tools.py trace webapp/ezeml-log.txt \\
        --pattern "500 Internal Server Error" \\
        --occurrence 1

Programmatic usage
------------------
Parse and summarize errors::

    from ezeml_log_tools import parse_log, summarize

    events = parse_log("webapp/ezeml-log.txt", r"500 Internal Server Error", ignore_case=True)
    summarize(events, top_n=10, show_recent=10, show_traceback_lines=0)

Retrieve a request trace::

    from ezeml_log_tools import get_request_trace, print_trace

    lines = get_request_trace("webapp/ezeml-log.txt", "500 Internal Server Error")
    print_trace(lines)
"""

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Shared regular expressions
# ---------------------------------------------------------------------------

#: Matches the standard ezEML log-line header, capturing timestamp, PID,
#: log level, optional user name, and the remainder of the line.
LOG_HEADER_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) "
    r"\[PID (?P<pid>\d+)\] "
    r"\[(?P<level>[A-Z]+)\]"
    r"(?: \[USER: (?P<user>[^\]]+)\])? "
    r"(?P<rest>.*)$"
)

#: Matches the ``**** INCOMING REQUEST:`` marker inside a log-line message,
#: capturing the URL and HTTP method.
REQUEST_RE = re.compile(r"\*\*\*\* INCOMING REQUEST:\s+(?P<url>\S+)\s+\[(?P<method>[A-Z]+)\]")

#: Matches a Python traceback frame line such as
#: ``  File "/webapp/views.py", line 42, in my_func``.
TRACE_FRAME_RE = re.compile(r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>.+)$')

# Correlate request/traceback context close in time to the logged error event.
MAX_CORRELATION_WINDOW = timedelta(minutes=30)
PREFERRED_PATH_PATTERNS = ("/webapp/", "/ezeml/")
GENERIC_LOGGER_NAME = "webapp"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RequestContext:
    """A recorded **** INCOMING REQUEST: line associated with a PID."""

    timestamp: datetime
    route: str


@dataclass
class TracebackContext:
    """Buffered Python traceback lines associated with a PID."""

    timestamp: Optional[datetime]
    pid: Optional[str]
    lines: list[str]
    function: str
    exception: str


@dataclass
class ErrorEvent:
    """A single matched error occurrence extracted from the log file."""

    timestamp: datetime
    pid: str
    user: str
    route: str
    function: str
    exception: str
    status_message: str
    traceback_lines: list[str]
    #: The immediately preceding timestamped log record for the same PID,
    #: or ``None`` when the error is the first record seen for that PID.
    preceding_line: Optional[str] = None


# ---------------------------------------------------------------------------
# Summarize helpers
# ---------------------------------------------------------------------------

def parse_timestamp(value: str) -> datetime:
    """Parse an ezEML log timestamp string into a :class:`datetime`.

    Parameters
    ----------
    value:
        Timestamp in the format ``YYYY-MM-DD HH:MM:SS,mmm``
        (e.g. ``2026-04-17 06:43:03,561``).

    Returns
    -------
    datetime
        The parsed datetime object.
    """
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S,%f")


def parse_traceback(traceback_lines: list[str]) -> tuple[str, str]:
    """Extract the most relevant function name and exception message from traceback lines.

    The *function* is chosen from the last ``File …, in <func>`` frame that
    references a preferred application path (``/webapp/`` or ``/ezeml/``); if
    none match, the last frame overall is used.

    The *exception* is the last non-empty line in the traceback block, which
    is typically the ``ExceptionClass: message`` line.

    Parameters
    ----------
    traceback_lines:
        All lines from ``Traceback (most recent call last):`` through the
        final exception line.

    Returns
    -------
    tuple[str, str]
        A ``(function, exception)`` pair.  Each value is ``"unknown"`` when
        the corresponding information cannot be extracted.
    """
    frames = []
    for line in traceback_lines:
        match = TRACE_FRAME_RE.match(line)
        if match:
            frames.append((match.group("file"), match.group("func")))

    function = "unknown"
    if frames:
        preferred = [
            frame for frame in frames
            if any(pattern in frame[0].lower() for pattern in PREFERRED_PATH_PATTERNS)
        ]
        chosen = preferred[-1] if preferred else frames[-1]
        function = f"{chosen[1]} ({chosen[0]})"

    exception = "unknown"
    for line in reversed(traceback_lines):
        cleaned = line.strip()
        if cleaned:
            exception = cleaned
            break

    return function, exception


def normalize_route(url: str, method: str) -> str:
    """Return a canonical ``METHOD /path[?query]`` route string.

    Parameters
    ----------
    url:
        The raw URL from the ``**** INCOMING REQUEST:`` log line.
    method:
        The HTTP method (e.g. ``GET``, ``POST``).

    Returns
    -------
    str
        A compact route label such as ``POST /eml/save`` or
        ``GET /eml/load?id=42``.
    """
    parsed = urlparse(url)
    if parsed.path:
        path = parsed.path
        if parsed.query:
            path = f"{path}?{parsed.query}"
    else:
        path = url
    return f"{method} {path}"


def print_top(title: str, counts: Counter, top_n: int) -> None:
    """Print a ranked summary table to stdout.

    Parameters
    ----------
    title:
        Section heading (printed followed by ``:``)
    counts:
        A :class:`~collections.Counter` mapping item labels to their counts.
    top_n:
        Maximum number of rows to display.
    """
    print(f"\n{title}:")
    if not counts:
        print("  (none)")
        return
    for key, count in counts.most_common(top_n):
        print(f"  {count:>4}  {key}")


# ---------------------------------------------------------------------------
# Core summarize API
# ---------------------------------------------------------------------------

def parse_log(path: str, error_pattern: str, ignore_case: bool) -> list[ErrorEvent]:
    """Scan a log file and return all lines matching *error_pattern*.

    For each matched line the function assembles an :class:`ErrorEvent` that
    includes route, function, exception, and traceback context (derived by
    correlating nearby ``**** INCOMING REQUEST:`` and ``Traceback`` blocks for
    the same PID), together with the immediately preceding timestamped record
    for that PID.

    Parameters
    ----------
    path:
        Path to the ezEML log file.
    error_pattern:
        Regular-expression pattern applied to the message portion of each log
        line.  Matching lines become :class:`ErrorEvent` instances.
    ignore_case:
        When ``True`` the pattern is compiled with :data:`re.IGNORECASE`.

    Returns
    -------
    list[ErrorEvent]
        One entry per matched line, in file order.

    Examples
    --------
    ::

        events = parse_log("webapp/ezeml-log.txt",
                           r"500 Internal Server Error",
                           ignore_case=True)
        for event in events:
            print(event.timestamp, event.function)
    """
    flags = re.IGNORECASE if ignore_case else 0
    error_re = re.compile(error_pattern, flags)

    events: list[ErrorEvent] = []
    last_request_by_pid: dict[str, RequestContext] = {}
    last_traceback_by_pid: dict[str, TracebackContext] = {}
    last_timestamped_record_by_pid: dict[str, str] = {}

    traceback_buffer: list[str] = []
    traceback_context_ts: Optional[datetime] = None
    traceback_context_pid: Optional[str] = None

    current_ts: Optional[datetime] = None
    current_pid: Optional[str] = None

    def finalize_traceback_if_needed() -> None:
        nonlocal traceback_buffer, traceback_context_ts, traceback_context_pid
        if not traceback_buffer:
            return
        function, exception = parse_traceback(traceback_buffer)
        if traceback_context_pid:
            last_traceback_by_pid[traceback_context_pid] = TracebackContext(
                timestamp=traceback_context_ts,
                pid=traceback_context_pid,
                lines=traceback_buffer[:],
                function=function,
                exception=exception,
            )
        traceback_buffer = []
        traceback_context_ts = None
        traceback_context_pid = None

    with open(path, "rb") as infile:
        for raw_line in infile:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
            header_match = LOG_HEADER_RE.match(line)

            if header_match:
                finalize_traceback_if_needed()

                current_ts = parse_timestamp(header_match.group("timestamp"))
                current_pid = header_match.group("pid")
                user = header_match.group("user") or "unknown"
                rest = header_match.group("rest")

                # Capture the preceding timestamped record for this PID before
                # updating the dict with the current line.
                preceding_line = last_timestamped_record_by_pid.get(current_pid)

                logger_name = ""
                message = rest
                if " -> " in rest:
                    logger_name, message = rest.split(" -> ", 1)

                request_match = REQUEST_RE.search(message)
                if request_match:
                    route = normalize_route(
                        request_match.group("url"), request_match.group("method")
                    )
                    last_request_by_pid[current_pid] = RequestContext(
                        timestamp=current_ts, route=route
                    )

                if error_re.search(message):
                    route = "unknown"
                    req_ctx = last_request_by_pid.get(current_pid)
                    if req_ctx and current_ts - req_ctx.timestamp <= MAX_CORRELATION_WINDOW:
                        route = req_ctx.route

                    tb_ctx = last_traceback_by_pid.get(current_pid)
                    function = "unknown"
                    exception = message
                    traceback_lines: list[str] = []
                    used_traceback_context = False
                    if (
                        tb_ctx
                        and tb_ctx.timestamp
                        and current_ts - tb_ctx.timestamp <= MAX_CORRELATION_WINDOW
                    ):
                        used_traceback_context = True
                        function = tb_ctx.function
                        exception = tb_ctx.exception
                        traceback_lines = tb_ctx.lines

                    # Keep traceback-derived function context when logger is generic.
                    if logger_name and logger_name != GENERIC_LOGGER_NAME and not used_traceback_context:
                        function = logger_name

                    events.append(
                        ErrorEvent(
                            timestamp=current_ts,
                            pid=current_pid,
                            user=user,
                            route=route,
                            function=function,
                            exception=exception,
                            status_message=message,
                            traceback_lines=traceback_lines,
                            preceding_line=preceding_line,
                        )
                    )

                # Update the last-seen timestamped record for this PID.
                last_timestamped_record_by_pid[current_pid] = line
                continue

            if line.startswith("Traceback (most recent call last):"):
                traceback_buffer = [line]
                traceback_context_ts = current_ts
                traceback_context_pid = current_pid
                continue

            if traceback_buffer:
                traceback_buffer.append(line)

    finalize_traceback_if_needed()
    return events


def summarize(
    events: list[ErrorEvent],
    top_n: int,
    show_recent: int,
    show_traceback_lines: int,
) -> None:
    """Print a summary report for a list of :class:`ErrorEvent` objects.

    The report includes:

    * Overall counts and time-range statistics (last 24 h / 7 d with
      comparison to the prior period).
    * Ranked tables for top functions, top exception classes, and counts
      by calendar day.
    * A "most recent N errors" detail section with per-event function,
      exception, status message, optional preceding log record (``Prev``),
      and optional traceback snippet.

    Parameters
    ----------
    events:
        Error events as returned by :func:`parse_log`, expected to be
        sorted in ascending timestamp order.
    top_n:
        Number of rows to display in each ranked summary table.
    show_recent:
        How many of the most-recent errors to list in detail.
    show_traceback_lines:
        Number of traceback lines to include per detail entry.
        Pass ``0`` to suppress traceback output.

    Examples
    --------
    ::

        events = parse_log("webapp/ezeml-log.txt",
                           r"500 Internal Server Error",
                           ignore_case=True)
        summarize(events, top_n=10, show_recent=10, show_traceback_lines=5)
    """
    if not events:
        print("No matching errors were found.")
        return

    first_ts = events[0].timestamp
    last_ts = events[-1].timestamp

    by_function = Counter(event.function for event in events)
    by_exception = Counter(event.exception for event in events)
    by_day = Counter(event.timestamp.strftime("%Y-%m-%d") for event in events)

    now = last_ts
    in_last_24h = 0
    in_prev_24h = 0
    in_last_7d = 0
    in_prev_7d = 0
    for event in events:
        age = now - event.timestamp
        if age <= timedelta(hours=24):
            in_last_24h += 1
        elif age <= timedelta(hours=48):
            in_prev_24h += 1

        if age <= timedelta(days=7):
            in_last_7d += 1
        elif age <= timedelta(days=14):
            in_prev_7d += 1

    print(f"Matched errors: {len(events)}")
    print(f"Time range: {first_ts} to {last_ts}")
    print(f"Last 24h: {in_last_24h} (previous 24h: {in_prev_24h})")
    print(f"Last 7d : {in_last_7d} (previous 7d : {in_prev_7d})")

    print_top("Top functions", by_function, top_n)
    print_top("Top exceptions", by_exception, top_n)
    print_top("Counts by day", by_day, top_n)

    print(f"\nMost recent {min(show_recent, len(events))} matching errors:")
    for event in events[-show_recent:]:
        print(f"\n- {event.timestamp} | PID {event.pid} | user={event.user}")
        if event.preceding_line is not None:
            print(f"  Prev     : {event.preceding_line}")
        print(f"  Function : {event.function}")
        print(f"  Exception: {event.exception}")
        print(f"  Status   : {event.status_message}")
        if show_traceback_lines > 0 and event.traceback_lines:
            print("  Traceback:")
            for tb_line in event.traceback_lines[-show_traceback_lines:]:
                print(f"    {tb_line}")


# ---------------------------------------------------------------------------
# Core trace API
# ---------------------------------------------------------------------------

def get_request_trace(
    path: str,
    pattern: str,
    ignore_case: bool = True,
    occurrence: int = -1,
    literal: bool = False,
) -> list[str]:
    """Return the log lines from the nearest INCOMING REQUEST to a pattern match.

    Scans *path* and collects every line that matches *pattern*.  For each
    match the function assembles the sequence of log lines belonging to the
    same PID that starts at the closest preceding ``**** INCOMING REQUEST:``
    line and ends at (and includes) the matched line.  Continuation lines such
    as tracebacks are included because they carry no PID header of their own
    and are therefore always attributed to the preceding PID.

    The pattern is matched against the **full raw log line** so that users can
    paste any portion of a log entry — including timestamp, PID, level, and
    user fields — as their search string.

    Parameters
    ----------
    path:
        Path to the log file.
    pattern:
        Search string used to identify the error line of interest.  Treated as
        a regular expression by default; pass ``literal=True`` to search for
        the exact string (regex metacharacters such as ``[``, ``]``, and ``.``
        are automatically escaped).
    ignore_case:
        When ``True`` (the default) the pattern is matched case-insensitively.
    occurrence:
        Which match to return when the pattern appears more than once.
        ``1`` selects the first (oldest) occurrence, ``2`` the second, and so
        on.  Negative indices count from the end: ``-1`` (the default) selects
        the last (most recent) occurrence.
    literal:
        When ``True`` the pattern is treated as a plain fixed string rather
        than a regular expression.  This is the safe choice when pasting a
        real log line as the search term.

    Returns
    -------
    list[str]
        The log lines that form the trace, ordered chronologically from the
        INCOMING REQUEST line to the matched error line.  Returns an empty list
        when no line in the file matches *pattern*.

    Examples
    --------
    Most-recent 500 error trace::

        lines = get_request_trace("webapp/ezeml-log.txt",
                                  "500 Internal Server Error")
        for line in lines:
            print(line)

    Trace using a literal log-line string (safe for brackets, dots, etc.)::

        lines = get_request_trace(
            "webapp/ezeml-log.txt",
            "2026-04-21 20:07:21,987 [PID 155449] [ERROR] [USER: Colin Smith]",
            literal=True,
        )
        print_trace(lines)
    """
    flags = re.IGNORECASE if ignore_case else 0
    search_pattern = re.escape(pattern) if literal else pattern
    error_re = re.compile(search_pattern, flags)

    # Each entry in *all_traces* is the complete line buffer for one match.
    all_traces: list[list[str]] = []

    # Per-PID buffer that resets each time an INCOMING REQUEST is seen for
    # that PID.  We always append every line to the buffer of the "current"
    # PID so that continuation lines (tracebacks, etc.) are captured.
    buffer_by_pid: dict[str, list[str]] = {}
    current_pid: Optional[str] = None

    with open(path, "rb") as fh:
        for raw_line in fh:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
            header_match = LOG_HEADER_RE.match(line)

            if header_match:
                current_pid = header_match.group("pid")
                rest = header_match.group("rest")

                # Strip the optional "logger_name -> " prefix to get the bare
                # message for the INCOMING REQUEST check.
                message = rest.split(" -> ", 1)[1] if " -> " in rest else rest

                if REQUEST_RE.search(message):
                    # Start a fresh buffer for this PID from the request line.
                    buffer_by_pid[current_pid] = [line]
                else:
                    # Append to this PID's active buffer (create one if it
                    # doesn't exist yet — the request may have been before the
                    # beginning of the file).
                    if current_pid not in buffer_by_pid:
                        buffer_by_pid[current_pid] = []
                    buffer_by_pid[current_pid].append(line)

                    if error_re.search(line):
                        # Snapshot the buffer; keep it alive in case further
                        # lines continue (e.g. a second error from same PID).
                        all_traces.append(list(buffer_by_pid[current_pid]))
            else:
                # Continuation line (traceback frame, etc.) — append to the
                # current PID's buffer so tracebacks are part of the trace.
                if current_pid is not None:
                    if current_pid not in buffer_by_pid:
                        buffer_by_pid[current_pid] = []
                    buffer_by_pid[current_pid].append(line)

    if not all_traces:
        return []

    # Positive occurrence values are 1-based (1 = first/oldest).
    # Negative values use Python's native end-relative indexing (-1 = last).
    try:
        if occurrence > 0:
            return all_traces[occurrence - 1]
        return all_traces[occurrence]
    except IndexError:
        return all_traces[-1]


def print_trace(trace: list[str]) -> None:
    """Print a request trace to stdout.

    Prints each line in *trace* followed by a newline.  When *trace* is empty
    a human-friendly message is printed instead.

    Parameters
    ----------
    trace:
        A list of log lines as returned by :func:`get_request_trace`.
    """
    if not trace:
        print("No matching line found in the log.")
        return
    for line in trace:
        print(line)


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _build_summarize_parser(subparsers: argparse.Action) -> None:
    """Register the ``summarize`` sub-command on *subparsers*."""
    p = subparsers.add_parser(
        "summarize",
        help="Summarize matching errors across a log file.",
        description=(
            "Scan an ezEML log file for lines matching --error-pattern and print "
            "aggregate statistics (top functions, exceptions, counts by day) plus "
            "a detail section showing the most-recent N errors with context."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples\n"
            "--------\n"
            "  # Summarize all 500 errors (default pattern)\n"
            "  python ezeml_log_tools.py summarize webapp/ezeml-log.txt\n\n"
            "  # Custom pattern, show 20 recent errors, include 5 traceback lines\n"
            "  python ezeml_log_tools.py summarize webapp/ezeml-log.txt \\\n"
            "      --error-pattern 'InternalServerError' \\\n"
            "      --show-recent 20 --traceback-lines 5\n"
        ),
    )
    p.add_argument(
        "log_file",
        nargs="?",
        default="webapp/ezeml-log.txt",
        help="Path to log file (default: webapp/ezeml-log.txt)",
    )
    p.add_argument(
        "--error-pattern",
        default=r"500 Internal Server Error",
        help="Regex pattern to match error messages (default: '500 Internal Server Error')",
    )
    p.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive matching for --error-pattern",
    )

    def positive_int(value: str) -> int:
        integer = int(value)
        if integer < 1:
            raise argparse.ArgumentTypeError("Value must be >= 1.")
        return integer

    def nonnegative_int(value: str) -> int:
        integer = int(value)
        if integer < 0:
            raise argparse.ArgumentTypeError("Value must be >= 0.")
        return integer

    p.add_argument(
        "--max-errors",
        type=positive_int,
        default=500,
        help="Analyze at most the most-recent N matching errors (default: 500)",
    )
    p.add_argument(
        "--top",
        type=positive_int,
        default=10,
        help="Show top N rows in summary tables (default: 10)",
    )
    p.add_argument(
        "--show-recent",
        type=nonnegative_int,
        default=10,
        help="Show details for the most-recent N matching errors (default: 10)",
    )
    p.add_argument(
        "--traceback-lines",
        type=nonnegative_int,
        default=0,
        help="Include the last N traceback lines per detail entry (default: 0)",
    )


def _build_trace_parser(subparsers: argparse.Action) -> None:
    """Register the ``trace`` sub-command on *subparsers*."""
    p = subparsers.add_parser(
        "trace",
        help="Show the request trace leading up to a specific error line.",
        description=(
            "Find the log line matching --pattern and print every log line for "
            "that process from the nearest preceding '**** INCOMING REQUEST:' "
            "through the matched line.  The result shows the exact sequence of "
            "steps the server executed before the error occurred."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples\n"
            "--------\n"
            "  # Most-recent 500 error trace (default pattern)\n"
            "  python ezeml_log_tools.py trace webapp/ezeml-log.txt\n\n"
            "  # Literal search — safe for strings with brackets, dots, etc.\n"
            "  python ezeml_log_tools.py trace webapp/ezeml-log.txt \\\n"
            "      --pattern '2026-04-21 20:07:21,987 [PID 155449] [ERROR] [USER: Colin Smith]' \\\n"
            "      --literal\n\n"
            "  # Select the first (oldest) occurrence\n"
            "  python ezeml_log_tools.py trace webapp/ezeml-log.txt \\\n"
            "      --pattern 'Some error text' --occurrence 1\n"
        ),
    )
    p.add_argument(
        "log_file",
        nargs="?",
        default="webapp/ezeml-log.txt",
        help="Path to log file (default: webapp/ezeml-log.txt)",
    )
    p.add_argument(
        "--pattern",
        default=r"500 Internal Server Error",
        help="Search pattern identifying the error line (default: '500 Internal Server Error')",
    )
    p.add_argument(
        "--literal",
        action="store_true",
        help=(
            "Treat --pattern as a plain fixed string rather than a regular expression. "
            "Use this when the search string contains special characters such as "
            "brackets, dots, or parentheses (e.g. when pasting a raw log line)."
        ),
    )
    p.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive matching for --pattern",
    )
    p.add_argument(
        "--occurrence",
        type=int,
        default=-1,
        help=(
            "Which match to display when the pattern appears more than once. "
            "1 = first (oldest), -1 = last (most recent, default). "
            "Negative values count from the end."
        ),
    )


def main() -> None:
    """Entry point for the ``ezeml_log_tools`` command-line interface.

    Exposes two sub-commands:

    ``summarize``
        Aggregate error statistics across the whole log file.
    ``trace``
        Deep-dive into the request sequence leading up to one specific error.

    Run ``python ezeml_log_tools.py --help`` or
    ``python ezeml_log_tools.py <subcommand> --help`` for full option details.
    """
    parser = argparse.ArgumentParser(
        prog="ezeml_log_tools",
        description="Log analysis tools for ezEML server logs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Run 'ezeml_log_tools <subcommand> --help' for per-command options.\n\n"
            "Quick examples\n"
            "--------------\n"
            "  python ezeml_log_tools.py summarize webapp/ezeml-log.txt\n"
            "  python ezeml_log_tools.py trace webapp/ezeml-log.txt --pattern 'My error'\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<subcommand>")
    subparsers.required = True

    _build_summarize_parser(subparsers)
    _build_trace_parser(subparsers)

    args = parser.parse_args()

    if args.command == "summarize":
        events = parse_log(args.log_file, args.error_pattern, not args.case_sensitive)
        events = sorted(events, key=lambda e: e.timestamp)
        if args.max_errors > 0:
            events = events[-args.max_errors:]
        summarize(
            events=events,
            top_n=args.top,
            show_recent=args.show_recent,
            show_traceback_lines=args.traceback_lines,
        )

    elif args.command == "trace":
        trace = get_request_trace(
            args.log_file,
            args.pattern,
            ignore_case=not args.case_sensitive,
            occurrence=args.occurrence,
            literal=args.literal,
        )
        print_trace(trace)


if __name__ == "__main__":
    main()
