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
class ANSI:
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
        BLACK = "\033[30m"
        RED = "\033[31m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        BLUE = "\033[34m"
        MAGENTA = "\033[35m"
        CYAN = "\033[36m"
        WHITE = "\033[37m"
        BRIGHT_BLACK = "\033[90m"
        BRIGHT_RED = "\033[91m"
        BRIGHT_GREEN = "\033[92m"
        BRIGHT_YELLOW = "\033[93m"
        BRIGHT_BLUE = "\033[94m"
        BRIGHT_MAGENTA = "\033[95m"
        BRIGHT_CYAN = "\033[96m"
        BRIGHT_WHITE = "\033[97m"
        RESET = "\033[0m"

    class Back:
        BLACK = "\033[40m"
        RED = "\033[41m"
        GREEN = "\033[42m"
        YELLOW = "\033[43m"
        BLUE = "\033[44m"
        MAGENTA = "\033[45m"
        CYAN = "\033[46m"
        WHITE = "\033[47m"
        BRIGHT_BLACK = "\033[100m"
        BRIGHT_RED = "\033[101m"
        BRIGHT_GREEN = "\033[102m"
        BRIGHT_YELLOW = "\033[103m"
        BRIGHT_BLUE = "\033[104m"
        BRIGHT_MAGENTA = "\033[105m"
        BRIGHT_CYAN = "\033[106m"
        BRIGHT_WHITE = "\033[107m"
        RESET = "\033[0m"

    class Style:
        BOLD = "\033[1m"
        DIM = "\033[2m"
        ITALIC = "\033[3m"
        UNDERLINE = "\033[4m"
        BLINK = "\033[5m"
        INVERT = "\033[7m"
        HIDDEN = "\033[8m"
        RESET = "\033[0m"


class TraceStack:
    def __init__(self):
        self._trace: str = ""
        self._depth: int = 0
        self._stack: list[str] = []

    def clear(self):
        self._trace = ""
        self._depth = 0
        self._stack.clear()

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
        return (
            f"{self.top_level_test_count or 0} test{plural}, "
            f"{self.completed_tests} completed "
            f"({self.passed_tests} passed, "
            f"{self.skipped_tests} skipped, "
            f"{self.failed_tests} failed)."
        )


class CLIProgress:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(
        self,
        verbosity: str = "NORMAL",
        colors: str = "AUTO",
        console_status: str = "STDOUT",
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
        # Parse console_status argument.
        console_status = console_status.upper()
        if console_status == "STDOUT":
            self.status_stream = sys.stdout
        elif console_status == "STDERR":
            self.status_stream = sys.stderr
        else:  # Assume NONE.
            self.status_stream = None

        # Set properties.
        self.terminal_width = min(
            shutil.get_terminal_size(fallback=(width, 40)).columns, width
        )
        self.status_lines = ["", "", ""]
        self.run_start_time: float | None = None
        self.current_test_start_time: float | None = None
        self.stats = TestStatistics()
        self.test_trace_stack = TraceStack()
        self.suite_trace_stack = TraceStack()

        # On Windows, import colorama if we're coloring output.
        if self.colors and sys.platform == "win32":
            import colorama

            colorama.just_fix_windows_console()

        # Finally, prepare the console interface.
        self._draw_status_box()

    # ------------------------------------------------------------------ helpers

    @property
    def in_test(self) -> bool:
        return self.current_test_start_time is not None

    def _writeln(self, text=""):
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    def _draw_status_box(self):
        if not self.status_stream:
            return
        text_width = self.terminal_width - 4
        self.status_stream.write("┌" + "─" * (self.terminal_width - 2) + "┐\n")
        for i in range(3):
            self.status_stream.write(
                f"│ {self.status_lines[i]:<{text_width}.{text_width}} │\n"
            )
        self.status_stream.write("└" + "─" * (self.terminal_width - 2) + "┘")
        self.status_stream.flush()

    def _clear_status_box(self):
        if not self.status_stream:
            return
        # Clear the current line and move the cursor up. Do this 5 times to
        # clear the entire box (3 lines of text + top and bottom borders).
        for _ in range(4):
            self.status_stream.write(ANSI.Cursor.CLEAR_LINE + ANSI.Cursor.UP())
        # Clear the final line and reset the cursor to the start of the line.
        self.status_stream.write(ANSI.Cursor.CLEAR_LINE + ANSI.Cursor.HOME)
        self.status_stream.flush()

    def _write_status_line(self, line_no: int, text: str):
        if not self.status_stream:
            return
        # Move cursor to the line inside the box and write the text.
        # For line 0, we want to move up 3 lines (to the first empty line in the box).
        # For line 1, we want to move up 2 lines.
        # For line 2, we want to move up 1 line.
        assert line_no >= 0 and line_no < 3, "line_no must be between 0 and 2"
        self.status_lines[line_no] = text
        line_offset = 3 - line_no
        self.status_stream.write(ANSI.Cursor.UP(line_offset))
        tw = self.terminal_width - 4
        self.status_stream.write(ANSI.Cursor.HOME + f"│ {text:<{tw}.{tw}} │")
        # Move cursor back down to the bottom of the box.
        self.status_stream.write(ANSI.Cursor.DOWN(line_offset))
        self.status_stream.flush()

    def _print_trace(self, text: str):
        # First clear the status box, so we don't have to worry about
        # interleaving with the trace output.
        self._clear_status_box()
        # Then print the trace text as normal.
        self._writeln(text)
        # Finally redraw the status box with the current test status.
        self._draw_status_box()

    def _record_run_start(self):
        if self.run_start_time is None:
            self.run_start_time = time.time()

    def _format_time(self, seconds):
        seconds = int(round(seconds))
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h:2d}h {m:2d}m {s:2d}s"
        elif m:
            return f"{m:2d}m {s:2d}s"
        else:
            return f"{s:2d}s"

    # ------------------------------------------------------------------ suite

    def start_suite(self, suite, result):
        self._record_run_start()
        self.stats.start_suite(suite)
        self.suite_trace_stack.clear()

        self._write_status_line(
            0, f"[SUITE {self.stats.format_suite_progress()}] {suite.full_name}"
        )

    def end_suite(self, suite, result):
        trace = self.suite_trace_stack.trace
        self.suite_trace_stack.clear()

        self._write_status_line(0, "")

        if result.status == "FAIL" and trace:
            fail_line = f"SUITE FAILED: {suite.full_name}"
            underline = "═" * len(fail_line)
            if self.colors:
                fail_line = (
                    f"{ANSI.Fore.RED}SUITE FAILED{ANSI.Fore.RESET}: {suite.full_name}"
                )
            self._print_trace(f"{fail_line}\n{underline}\n{trace}")

    # ------------------------------------------------------------------ test

    def start_test(self, test, result):
        self._record_run_start()
        self.stats.start_test()
        self.test_trace_stack.clear()
        self.current_test_start_time = time.time()

        elapsed_time = time.time() - self.run_start_time
        if self.stats.completed_tests:
            avg_test_time = elapsed_time / self.stats.completed_tests
            remaining_tests = (
                self.stats.top_level_test_count - self.stats.completed_tests
            )
            eta_time = avg_test_time * remaining_tests
        else:
            eta_time = None
        eta_str = self._format_time(eta_time) if eta_time else "unknown"
        self._write_status_line(
            1,
            f"[TEST {self.stats.format_test_progress()}] {test.name}"
            f"    (elapsed {self._format_time(elapsed_time)}, ETA {eta_str})",
        )

    def end_test(self, test, result):
        # start = self.current_test_start_time
        trace = self.test_trace_stack.trace
        self.test_trace_stack.clear()
        self.current_test_start_time = None
        if result.not_run:
            self._write_status_line(1, "")
            return

        self.stats.end_test(result)

        # end = time.time()
        # elapsed = end - start  # retained for potential future use

        self._write_status_line(1, "")

        if result.status == "FAIL":
            fail_line = f"TEST FAILED: {test.full_name}"
            underline = "═" * len(fail_line)
            if self.colors:
                fail_line = (
                    f"{ANSI.Fore.RED}TEST FAILED{ANSI.Fore.RESET}: {test.full_name}"
                )
            if not trace:
                trace = result.message + "\n"
            self._print_trace(f"{fail_line}\n{underline}\n{trace}")

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

        self._write_status_line(2, f"[{name}]  {argstr}")

    def end_keyword(self, keyword, result):
        stack = self.test_trace_stack if self.in_test else self.suite_trace_stack
        if result.status == "NOT RUN":
            # Discard; the header was never flushed so it just disappears.
            stack.pop_keyword()
            self._write_status_line(2, "")
            return

        # Keyword ran - flush any pending ancestor headers (and this one)
        # so the hierarchy appears in the trace.
        stack.flush()

        elapsed_ms = getattr(result, "elapsedtime", None)

        elapsed = (
            self._format_time(elapsed_ms / 1000.0) if elapsed_ms is not None else "?s"
        )

        keyword_trace = "  "
        if result.status == "PASS":
            status = "✓ PASS"
            if self.colors:
                status = f"{ANSI.Fore.BRIGHT_GREEN}{status}{ANSI.Fore.RESET}"
            keyword_trace += f"{status}    {elapsed}"
        elif result.status == "SKIP":
            status = "→ SKIP"
            if self.colors:
                status = f"{ANSI.Fore.BRIGHT_YELLOW}{status}{ANSI.Fore.RESET}"
            keyword_trace += f"{status}    {elapsed}"
        elif result.status == "FAIL":
            status = "✗ FAIL"
            if self.colors:
                status = f"{ANSI.Fore.BRIGHT_RED}{status}{ANSI.Fore.RESET}"
            keyword_trace += f"{status}    {elapsed}"
        else:
            keyword_trace += f"? {result.status}    {elapsed}"

        stack.append_trace(keyword_trace)

        self._write_status_line(2, "")

    # ------------------------------------------------------------------ logging

    def log_message(self, message):
        level = getattr(message, "level", None) or "UNKNOWN"
        text = getattr(message, "message", None) or ""

        # Flush keyword headers so they appear above the log line.
        stack = self.test_trace_stack if self.in_test else self.suite_trace_stack
        stack.flush(decrement_depth=False)

        level_initial = level[0].upper()
        text_lines = text.splitlines()
        formatted_lines = []
        # First line gets level initial
        formatted_lines.append(f"{level_initial} {text_lines[0]}")
        # Remaining lines align without repeating the level
        for text_line in text_lines[1:]:
            formatted_lines.append(f"  {text_line}")

        if self.colors:
            if level == "FAIL":
                formatted_lines = [
                    f"{ANSI.Fore.BRIGHT_RED}{line}{ANSI.Fore.RESET}"
                    for line in formatted_lines
                ]
            elif level == "WARN":
                formatted_lines = [
                    f"{ANSI.Fore.BRIGHT_YELLOW}{line}{ANSI.Fore.RESET}"
                    for line in formatted_lines
                ]
            elif level == "INFO":
                formatted_lines = [
                    f"{ANSI.Fore.BRIGHT_BLACK}{line}{ANSI.Fore.RESET}"
                    for line in formatted_lines
                ]
            elif level == "DEBUG" or level == "TRACE":
                formatted_lines = [
                    f"{ANSI.Fore.WHITE}{line}{ANSI.Fore.RESET}"
                    for line in formatted_lines
                ]

        stack.append_trace("\n".join(formatted_lines))

    # ------------------------------------------------------------------ close

    def close(self):
        self._clear_status_box()

        if self.verbosity >= Verbosity.NORMAL:
            self._writeln("RUN COMPLETE: " + self.stats.format_run_results())

        if self.run_start_time is not None and self.verbosity >= Verbosity.NORMAL:
            elapsed_str = self._format_time(time.time() - self.run_start_time)
            self._writeln(f"Total elapsed: {elapsed_str}.")
