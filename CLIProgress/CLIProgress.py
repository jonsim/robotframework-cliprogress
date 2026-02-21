# Copyright (c) 2026 Jonathan Simmonds
#
# Prints Robot test progress to stdout as execution happens.
#
# Usage:
#   robot --listener CLIProgress.py path/to/tests
#
# It's recommended to also call with:
# --console=none to avoid Robot's default console markers getting interleaved.
# --maxerrorlines=10000 to avoid truncating all but the longest error messages.
# --maxmaxassignlength=10000 to avoid truncating all but the longest variables.
#
import enum
import functools
import re
import shutil
import sys
import time


@functools.total_ordering
class Verbosity(enum.Enum):
    QUIET = 0
    NORMAL = 1
    DEBUG = 2

    def __eq__(self, value):
        if isinstance(value, Verbosity):
            return self.value == value.value
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, Verbosity):
            return self.value < other.value
        return NotImplemented

    @classmethod
    def from_string(cls, s):
        s = s.upper()
        if s in cls.__members__:
            return cls[s]
        return cls.NORMAL


# ANSI escape codes for colors and styles.
class _ANSICode:
    def __init__(self, code: str):
        self.code = code

    def __call__(self, text: str) -> str:
        return f"{self.code}{text}{ANSI.RESET}"

    def __repr__(self) -> str:
        return self.code

    def __str__(self) -> str:
        return self.code


class ANSI:
    RESET = _ANSICode("\033[0m")

    class Cursor:
        CLEAR_LINE = "\033[2K"

        HOME = "\r"

        @staticmethod
        def UP(n: int = 1) -> str:
            return f"\033[{n}A"

        @staticmethod
        def DOWN(n: int = 1) -> str:
            return f"\033[{n}B"

        @staticmethod
        def LEFT(n: int = 1) -> str:
            return f"\033[{n}D"

        @staticmethod
        def RIGHT(n: int = 1) -> str:
            return f"\033[{n}C"

    class Fore:
        BLACK = _ANSICode("\033[30m")
        RED = _ANSICode("\033[31m")
        GREEN = _ANSICode("\033[32m")
        YELLOW = _ANSICode("\033[33m")
        BLUE = _ANSICode("\033[34m")
        MAGENTA = _ANSICode("\033[35m")
        CYAN = _ANSICode("\033[36m")
        WHITE = _ANSICode("\033[37m")
        BRIGHT_BLACK = _ANSICode("\033[90m")
        BRIGHT_RED = _ANSICode("\033[91m")
        BRIGHT_GREEN = _ANSICode("\033[92m")
        BRIGHT_YELLOW = _ANSICode("\033[93m")
        BRIGHT_BLUE = _ANSICode("\033[94m")
        BRIGHT_MAGENTA = _ANSICode("\033[95m")
        BRIGHT_CYAN = _ANSICode("\033[96m")
        BRIGHT_WHITE = _ANSICode("\033[97m")

    class Back:
        BLACK = _ANSICode("\033[40m")
        RED = _ANSICode("\033[41m")
        GREEN = _ANSICode("\033[42m")
        YELLOW = _ANSICode("\033[43m")
        BLUE = _ANSICode("\033[44m")
        MAGENTA = _ANSICode("\033[45m")
        CYAN = _ANSICode("\033[46m")
        WHITE = _ANSICode("\033[47m")
        BRIGHT_BLACK = _ANSICode("\033[100m")
        BRIGHT_RED = _ANSICode("\033[101m")
        BRIGHT_GREEN = _ANSICode("\033[102m")
        BRIGHT_YELLOW = _ANSICode("\033[103m")
        BRIGHT_BLUE = _ANSICode("\033[104m")
        BRIGHT_MAGENTA = _ANSICode("\033[105m")
        BRIGHT_CYAN = _ANSICode("\033[106m")
        BRIGHT_WHITE = _ANSICode("\033[107m")

    class Style:
        BOLD = _ANSICode("\033[1m")
        DIM = _ANSICode("\033[2m")
        ITALIC = _ANSICode("\033[3m")
        UNDERLINE = _ANSICode("\033[4m")
        BLINK = _ANSICode("\033[5m")
        INVERT = _ANSICode("\033[7m")
        HIDDEN = _ANSICode("\033[8m")

    @staticmethod
    def len(text: str) -> int:
        """Return the length of the text, ignoring ANSI escape codes."""
        return len(re.sub(r"\033\[[0-9;]*m", "", text))


class TraceStack:
    def __init__(self):
        self._trace: str = ""
        self._depth: int = 0
        self._stack: list[str] = []
        self.has_warnings: bool = False
        self.has_errors: bool = False

    def clear(self):
        self._trace = ""
        self._depth = 0
        self._stack.clear()
        self.has_warnings = False
        self.has_errors = False

    @property
    def _indent(self) -> str:
        return "  " * min(self._depth, 20)

    @property
    def trace(self) -> str:
        return self._trace

    def push_keyword(self, keyword_line: str):
        self._stack.append(self._indent + keyword_line)
        self._depth += 1

    def pop_keyword(self):
        self._stack.pop()
        self._depth -= 1

    def append_trace(self, trace_line: str):
        self._trace += self._indent + trace_line + "\n"

    def flush(self, decrement_depth: bool = True):
        """Flush any pending keyword headers to the trace and clear the stack."""
        if decrement_depth:
            self._depth -= 1
        for trace_line in self._stack:
            self._trace += trace_line + "\n"
        self._stack.clear()


class TestStatistics:
    def __init__(self):
        self.top_level_suite_count: int | None = None
        self.top_level_test_count: int | None = None
        self.started_suites = 0
        self.started_tests = 0
        self.passed_tests = 0
        self.skipped_tests = 0
        self.failed_tests = 0
        self.completed_tests = 0
        self.warnings = 0
        self.errors = 0

    def start_suite(self, suite):
        self.started_suites += 1
        if self.top_level_suite_count is None:
            self.top_level_suite_count = len(suite.suites) or 1
        if self.top_level_test_count is None:
            self.top_level_test_count = suite.test_count

    def start_test(self):
        self.started_tests += 1

    def end_test(self, result):
        if result.not_run:
            return
        self.completed_tests += 1
        if result.status == "PASS":
            self.passed_tests += 1
        elif result.status == "FAIL":
            self.failed_tests += 1
        elif result.status == "SKIP":
            self.skipped_tests += 1

    def format_suite_progress(self) -> str:
        return f"{self.started_suites:2d}/{self.top_level_suite_count:2d}"

    def format_test_progress(self) -> str:
        return f"{self.started_tests:2d}/{self.top_level_test_count:2d}"

    def format_run_results(self) -> str:
        plural = "s" if self.top_level_test_count != 1 else ""
        results = (
            f"{self.top_level_test_count or 0} test{plural}, "
            f"{self.completed_tests} completed "
            f"({self.passed_tests} passed, "
            f"{self.skipped_tests} skipped, "
            f"{self.failed_tests} failed)."
        )
        if self.errors:
            plural = "s" if self.errors != 1 else ""
            results += f" {self.errors} test{plural} raised errors."
        if self.warnings:
            plural = "s" if self.warnings != 1 else ""
            results += f" {self.warnings} test{plural} raised warnings."
        return results


class TestTimings:
    def __init__(self):
        self.run_start_time: float | None = None
        self.current_test_start_time: float | None = None

    def _record_run_start(self):
        if self.run_start_time is None:
            self.run_start_time = time.time()

    def start_suite(self):
        self._record_run_start()

    def start_test(self):
        self._record_run_start()
        self.current_test_start_time = time.time()

    def end_test(self):
        self.current_test_start_time = None

    @staticmethod
    def format_time(seconds: float | int | None) -> str:
        if seconds is None:
            return "unknown"
        seconds = int(round(seconds))
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h:2d}h {m:2d}m {s:2d}s"
        elif m:
            return f"{m:2d}m {s:2d}s"
        else:
            return f"{s:2d}s"

    def get_elapsed_time(self) -> float:
        if self.run_start_time is None:
            return 0.0
        return time.time() - self.run_start_time

    def format_elapsed_time(self) -> str:
        return self.format_time(self.get_elapsed_time())

    def format_eta(self, stats: TestStatistics) -> str:
        if stats.completed_tests and stats.top_level_test_count:
            elapsed_time = self.get_elapsed_time()
            avg_test_time = elapsed_time / stats.completed_tests
            remaining_tests = stats.top_level_test_count - stats.completed_tests
            eta_time = avg_test_time * remaining_tests
            return self.format_time(eta_time)
        return "unknown"


class CLIProgress:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(
        self,
        verbosity: str = "NORMAL",
        colors: str = "AUTO",
        console_progress: str = "STDOUT",
        width: int = 120,
    ):
        # Parse verbosity argument.
        verbosity = verbosity.upper()
        self.verbosity = Verbosity.from_string(verbosity)
        # Parse colors argument.
        colors = colors.upper()
        if colors in {"ON", "ANSI"}:
            self.colors = True
        elif colors in {"OFF"}:
            self.colors = False
        else:  # Assume AUTO.
            if sys.stdout.isatty():
                if sys.platform == "win32":
                    import importlib.util

                    self.colors = importlib.util.find_spec("colorama") is not None
                else:
                    self.colors = True
            else:
                self.colors = False
        # Parse console_progress argument.
        console_progress = console_progress.upper()
        if console_progress == "STDOUT":
            self.progress_stream = sys.stdout
        elif console_progress == "STDERR":
            self.progress_stream = sys.stderr
        else:  # Assume NONE.
            self.progress_stream = None

        # Configure output based on verbosity.
        self.print_passed = self.verbosity >= Verbosity.DEBUG
        self.print_skipped = self.verbosity >= Verbosity.DEBUG
        self.print_warned = self.verbosity >= Verbosity.NORMAL
        self.print_errored = self.verbosity >= Verbosity.NORMAL
        self.print_failed = self.verbosity >= Verbosity.QUIET

        # Set properties.
        self.terminal_width = min(
            shutil.get_terminal_size(fallback=(width, 40)).columns, width
        )
        self.progress_lines = ["", "", ""]
        self.stats = TestStatistics()
        self.timings = TestTimings()
        self.test_trace_stack = TraceStack()
        self.suite_trace_stack = TraceStack()

        # On Windows, import colorama if we're coloring output.
        if self.colors and sys.platform == "win32":
            import colorama

            colorama.just_fix_windows_console()

        # Finally, prepare the console interface.
        self._draw_progress_box()

    # ------------------------------------------------------------------ helpers

    @property
    def in_test(self) -> bool:
        return self.timings.current_test_start_time is not None

    def _writeln(self, text=""):
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    def _past_tense(self, verb: str) -> str:
        is_upper = verb.isupper()
        is_title = verb.istitle()
        v = verb.lower()
        if v.endswith("e"):
            res = v + "d"
        elif v.endswith("y"):
            res = v[:-1] + "ied"
        elif v.endswith("p"):
            res = v + "ped"
        else:
            res = v + "ed"
        if is_upper:
            return res.upper()
        elif is_title:
            return res.title()
        return res

    def _draw_progress_box(self):
        if not self.progress_stream:
            return
        text_width = self.terminal_width - 4
        self.progress_stream.write("┌" + "─" * (self.terminal_width - 2) + "┐\n")
        for i in range(3):
            self.progress_stream.write(
                f"│ {self.progress_lines[i]:<{text_width}.{text_width}} │\n"
            )
        self.progress_stream.write("└" + "─" * (self.terminal_width - 2) + "┘")
        self.progress_stream.flush()

    def _clear_progress_box(self):
        if not self.progress_stream:
            return
        # Clear the current line and move the cursor up. Do this 5 times to
        # clear the entire box (3 lines of text + top and bottom borders).
        for _ in range(4):
            self.progress_stream.write(ANSI.Cursor.CLEAR_LINE + ANSI.Cursor.UP())
        # Clear the final line and reset the cursor to the start of the line.
        self.progress_stream.write(ANSI.Cursor.CLEAR_LINE + ANSI.Cursor.HOME)
        self.progress_stream.flush()

    def _write_progress_line(
        self, line_no: int, left_text: str = "", right_text: str = ""
    ):
        if not self.progress_stream:
            return
        # Format the left and right text into a single line. Right text takes
        # priority. Truncate left text with '...' if necessary.
        text_width = self.terminal_width - 4
        right_len = len(right_text)
        max_left = text_width - right_len - 1 if right_len > 0 else text_width
        max_left = max(0, max_left)
        if len(left_text) > max_left:
            if max_left >= 3:
                left_text = left_text[: max_left - 3] + "..."
            else:
                left_text = left_text[:max_left]
        padding = max(0, text_width - len(left_text) - right_len)
        text = f"{left_text}{' ' * padding}{right_text}"

        # Move cursor to the line inside the box and write the text.
        # For line 0, we want to move up 3 lines (to the first empty line in the box).
        # For line 1, we want to move up 2 lines.
        # For line 2, we want to move up 1 line.
        assert line_no >= 0 and line_no < 3, "line_no must be between 0 and 2"
        self.progress_lines[line_no] = text
        line_offset = 3 - line_no
        self.progress_stream.write(ANSI.Cursor.UP(line_offset))
        self.progress_stream.write(ANSI.Cursor.HOME + f"│ {text} │")
        # Move cursor back down to the bottom of the box.
        self.progress_stream.write(ANSI.Cursor.DOWN(line_offset))
        self.progress_stream.flush()

    def _print_trace(self, text: str):
        # First clear the progress box, so we don't have to worry about
        # interleaving with the trace output.
        self._clear_progress_box()
        # Then print the trace text as normal.
        self._writeln(text)
        # Finally redraw the progress box with the current test progress.
        self._draw_progress_box()

    # ------------------------------------------------------------------ suite

    def start_suite(self, suite, result):
        self.stats.start_suite(suite)
        self.timings.start_suite()
        self.suite_trace_stack.clear()

        self._write_progress_line(
            0, f"[SUITE {self.stats.format_suite_progress()}] {suite.full_name}"
        )

    def end_suite(self, suite, result):
        trace = self.suite_trace_stack.trace
        self.suite_trace_stack.clear()

        self._write_progress_line(0)

        status_text = ""
        if trace:
            if result.status == "PASS" and self.print_passed:
                status_text = "SUITE PASSED"
                if self.colors:
                    status_text = ANSI.Fore.GREEN(status_text)
            elif result.status == "SKIP" and self.print_skipped:
                status_text = "SUITE SKIPPED"
                if self.colors:
                    status_text = ANSI.Fore.YELLOW(status_text)
            elif result.status == "FAIL" and self.print_failed:
                status_text = "SUITE FAILED"
                if self.colors:
                    status_text = ANSI.Fore.RED(status_text)
        if status_text:
            status_line = f"{status_text}: {suite.full_name}"
            underline = "═" * ANSI.len(status_line)
            if not trace:
                trace = result.message + "\n"
            self._print_trace(f"{status_line}\n{underline}\n{trace}")

    # ------------------------------------------------------------------ test

    def start_test(self, test, result):
        self.stats.start_test()
        self.timings.start_test()
        self.test_trace_stack.clear()

        self._write_progress_line(
            1,
            f"[TEST {self.stats.format_test_progress()}] {test.name}",
            f"(elapsed {self.timings.format_elapsed_time()}, "
            f"ETA {self.timings.format_eta(self.stats)})",
        )

    def end_test(self, test, result):
        trace = self.test_trace_stack.trace
        self.stats.end_test(result)
        self.timings.end_test()
        self._write_progress_line(1)
        if not result.not_run:
            should_print = False
            status_text = "TEST " + self._past_tense(result.status)
            status_color = None
            if result.status == "PASS":
                should_print = self.print_passed
                status_color = ANSI.Fore.GREEN
            elif result.status == "SKIP":
                should_print = self.print_skipped
                status_color = ANSI.Fore.YELLOW
            elif result.status == "FAIL":
                should_print = self.print_failed
                status_color = ANSI.Fore.RED
            if self.test_trace_stack.has_errors:
                should_print |= self.print_errored
                status_text += " WITH ERRORS"
                status_color = ANSI.Fore.RED
            if self.test_trace_stack.has_warnings:
                should_print |= self.print_warned
                status_text += " WITH WARNINGS"
                status_color = ANSI.Fore.BRIGHT_YELLOW
            if should_print:
                if self.colors and status_color:
                    status_text = status_color(status_text)
                status_line = f"{status_text}: {test.full_name}"
                underline = "═" * ANSI.len(status_line)
                if not trace:
                    trace = result.message + "\n"
                trace = f"{status_line}\n{underline}\n{trace}"
                self._print_trace(trace)
        self.test_trace_stack.clear()

    # ------------------------------------------------------------------ keyword

    def start_keyword(self, keyword, result):
        stack = self.test_trace_stack if self.in_test else self.suite_trace_stack
        name = (
            getattr(result, "kwname", None)
            or getattr(result, "name", None)
            or "<unknown>"
        )
        lib = getattr(result, "libname", None)
        args = getattr(result, "args", None) or []
        argstr = ", ".join(repr(a) for a in args)
        kwstr = f"{lib}.{name}" if lib else name
        trace_line = f"▶ {kwstr}({argstr})"
        stack.push_keyword(trace_line)

        self._write_progress_line(2, f"[{name}]  {argstr}")

    def end_keyword(self, keyword, result):
        stack = self.test_trace_stack if self.in_test else self.suite_trace_stack
        if result.status == "NOT RUN":
            # Discard; the header was never flushed so it just disappears.
            stack.pop_keyword()
            self._write_progress_line(2)
            return

        # Keyword ran - flush any pending ancestor headers (and this one)
        # so the hierarchy appears in the trace.
        stack.flush()

        elapsed_ms = getattr(result, "elapsedtime", None)

        elapsed = (
            TestTimings.format_time(elapsed_ms / 1000.0)
            if elapsed_ms is not None
            else "?s"
        )

        keyword_trace = "  "
        if result.status == "PASS":
            status = "✓ PASS"
            if self.colors:
                status = ANSI.Fore.BRIGHT_GREEN(status)
            keyword_trace += f"{status}    {elapsed}"
        elif result.status == "SKIP":
            status = "→ SKIP"
            if self.colors:
                status = ANSI.Fore.YELLOW(status)
            keyword_trace += f"{status}    {elapsed}"
        elif result.status == "FAIL":
            status = "✗ FAIL"
            if self.colors:
                status = ANSI.Fore.BRIGHT_RED(status)
            keyword_trace += f"{status}    {elapsed}"
        else:
            keyword_trace += f"? {result.status}    {elapsed}"

        stack.append_trace(keyword_trace)

        self._write_progress_line(2)

    # ------------------------------------------------------------------ logging

    def log_message(self, message):
        level = getattr(message, "level", None) or "UNKNOWN"
        text = getattr(message, "message", None) or ""

        # Flush keyword headers so they appear above the log line.
        stack = self.test_trace_stack if self.in_test else self.suite_trace_stack
        stack.flush(decrement_depth=False)

        level_initial = level[0].upper()
        text_lines = text.splitlines()
        lines = []
        # First line gets level initial
        lines.append(f"{level_initial} {text_lines[0]}")
        # Remaining lines align without repeating the level
        for text_line in text_lines[1:]:
            lines.append(f"  {text_line}")

        if self.colors:
            if level == "ERROR":
                lines = [ANSI.Fore.BRIGHT_RED(line) for line in lines]
            elif level == "FAIL":
                lines = [ANSI.Fore.BRIGHT_RED(line) for line in lines]
            elif level == "WARN":
                lines = [ANSI.Fore.BRIGHT_YELLOW(line) for line in lines]
            elif level == "SKIP":
                lines = [ANSI.Fore.YELLOW(line) for line in lines]
            elif level == "INFO":
                lines = [ANSI.Fore.BRIGHT_BLACK(line) for line in lines]
            elif level == "DEBUG" or level == "TRACE":
                lines = [ANSI.Fore.WHITE(line) for line in lines]

        if level == "ERROR":
            self.stats.errors += 1
            stack.has_errors = True
        elif level == "WARN":
            self.stats.warnings += 1
            stack.has_warnings = True

        stack.append_trace("\n".join(lines))

    # ------------------------------------------------------------------ close

    def close(self):
        self._clear_progress_box()

        if self.verbosity >= Verbosity.QUIET:
            self._writeln("RUN COMPLETE: " + self.stats.format_run_results())

        if (
            self.timings.run_start_time is not None
            and self.verbosity >= Verbosity.NORMAL
        ):
            elapsed_str = self.timings.format_elapsed_time()
            self._writeln(f"Total elapsed: {elapsed_str}.")
