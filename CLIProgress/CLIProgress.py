# Copyright (c) 2026 Jonathan Simmonds
#
# Prints Robot test progress to stdout as execution happens.
#
# Usage:
#   robot --listener CLIProgress.py path/to/tests
#
# It's recommended to also call with:
# --console=quiet to avoid Robot's default console markers getting interleaved.
# --maxerrorlines=10000 to avoid truncating all but the longest error messages.
#
import enum
import functools
import shutil
import sys
import time

@functools.total_ordering
class Verbosity(enum.Enum):
    QUIET  = 0
    NORMAL = 1
    DEBUG  = 2

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


class CLIProgress:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self,
                 verbosity: str = "NORMAL",
                 colors: str = "AUTO",
                 width: int = 78):
        # Parse arguments.
        verbosity = verbosity.upper()
        colors = colors.upper()
        self.verbosity = Verbosity.from_string(verbosity)
        if colors in {"ON", "ANSI"}:
            self.colors = True
        elif colors in {"OFF"}:
            self.colors = False
        else: # Assume AUTO.
            if sys.stdout.isatty():
                if sys.platform == "win32":
                    import importlib.util
                    self.colors = importlib.util.find_spec("colorama") is not None
                else:
                    self.colors = True
            else:
                self.colors = False

        # Set properties.
        self.terminal_width = shutil.get_terminal_size().columns
        self.status_lines = ['', '', '']
        self.run_start = None
        self.suite_total_tests = None
        self.started_tests = 0
        self.passed_tests = 0
        self.skipped_tests = 0
        self.failed_tests = 0
        self.completed_tests = 0
        self.current_test_start_time = None
        self.current_test_trace = ''
        self.keyword_depth = 0
        self.keyword_stack = []

        # On Windows, import colorama if we're coloring output.
        if self.colors and sys.platform == "win32":
            import colorama
            colorama.just_fix_windows_console()

        # Finally, prepare the console interface.
        self._draw_status_box()

    # ------------------------------------------------------------------ helpers

    def _writeln(self, text=""):
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    def _overwriteln(self, text: str = ""):
        # Pad to terminal width to clear previous line
        sys.stdout.write(f"{text:<{self.terminal_width}}\r")
        sys.stdout.flush()

    def _draw_status_box(self):
        text_width = self.terminal_width - 4
        sys.stdout.write('┌' + '─' * (self.terminal_width - 2) + '┐\n')
        for i in range(3):
            sys.stdout.write(f'│ {self.status_lines[i]:<{text_width}.{text_width}} │\n')
        sys.stdout.write('└' + '─' * (self.terminal_width - 2) + '┘')
        sys.stdout.flush()

    def _clear_status_box(self):
        # Clear the current line and move the cursor up. Do this 5 times to
        # clear the entire box (3 lines of text + top and bottom borders).
        for _ in range(4):
            sys.stdout.write(ANSI.Cursor.CLEAR_LINE + ANSI.Cursor.UP())
        # Clear the final line and reset the cursor to the start of the line.
        sys.stdout.write(ANSI.Cursor.CLEAR_LINE + ANSI.Cursor.HOME)

    def _write_status_line(self, line_no: int, text: str):
        # Move cursor to the line inside the box and write the text.
        # For line 0, we want to move up 3 lines (to the first empty line in the box).
        # For line 1, we want to move up 2 lines.
        # For line 2, we want to move up 1 line.
        # self._writeln(text)
        # return
        assert line_no >= 0 and line_no < 3, "line_no must be between 0 and 2"
        self.status_lines[line_no] = text
        line_offset = 3 - line_no
        sys.stdout.write(ANSI.Cursor.UP(line_offset))
        sys.stdout.write(ANSI.Cursor.HOME + f"│ {text:<{self.terminal_width - 4}.{self.terminal_width - 4}} │")
        # Move cursor back down to the bottom of the box.
        sys.stdout.write(ANSI.Cursor.DOWN(line_offset))

    def _print_trace(self, text: str):
        # First clear the status box, so we don't have to worry about
        # interleaving with the trace output.
        self._clear_status_box()
        # Then print the trace text as normal.
        self._writeln(text)
        # Finally redraw the status box with the current test status.
        self._draw_status_box()

    def _record_run_start(self):
        if self.run_start is None:
            self.run_start = time.time()

    def _format_time(self, seconds):
        seconds = int(round(seconds))
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h:
            return "%2dh %2dm %2ds" % (h, m, s)
        elif m:
            return "%2dm %2ds" % (m, s)
        else:
            return "%2ds" % (s)

    def _indent(self):
        return "  " * min(self.keyword_depth, 20)

    def _flush_keyword_stack(self):
        """Flush any pending keyword headers to the trace and clear the stack."""
        for trace_line in self.keyword_stack:
            self.current_test_trace += trace_line + "\n"
        self.keyword_stack.clear()

    # ------------------------------------------------------------------ suite

    def start_suite(self, suite, result):
        self._record_run_start()

        name = getattr(result, "name", None) or getattr(suite, "name", None) or "<suite>"
        if self.suite_total_tests is None:
            self.suite_total_tests = int(getattr(suite, "test_count", 0))

        self._write_status_line(0, f"[SUITE] {name}")

    def end_suite(self, suite, result):
        self._write_status_line(0, "")

    # ------------------------------------------------------------------ test

    def start_test(self, test, result):
        self._record_run_start()
        self.started_tests += 1
        self.current_test_trace = ''
        self.keyword_depth = 0
        self.keyword_stack = []
        self.current_test_start_time = time.time()

        elapsed_time = time.time() - self.run_start
        if self.completed_tests:
            avg_test_time = elapsed_time / self.completed_tests
            remaining_tests = self.suite_total_tests - self.completed_tests
            eta_time = avg_test_time * remaining_tests
        else:
            eta_time = None
        self._write_status_line(1, "[TEST %2d/%2d] %s    (elapsed %s, ETA %s)" % (
            self.started_tests,
            self.suite_total_tests,
            test.name,
            self._format_time(elapsed_time),
            self._format_time(eta_time) if eta_time else "unknown",
        ))

    def end_test(self, test, result):
        start = self.current_test_start_time
        trace = self.current_test_trace
        self.keyword_depth = 0
        self.keyword_stack = []
        self.current_test_start_time = None
        self.current_test_trace = ""
        if result.not_run:
            self._write_status_line(1, "")
            return
        self.completed_tests += 1

        end = time.time()
        elapsed = end - start

        if result.status == "PASS":
            self.passed_tests += 1
        elif result.status == "FAIL":
            self.failed_tests += 1
        elif result.status == "SKIP":
            self.skipped_tests += 1

        self._write_status_line(1, "")

        if result.status == "FAIL":
            fail_line = f"TEST FAILED: {test.name}"
            underline = "═" * len(fail_line)
            if self.colors:
                fail_line = f"{ANSI.Fore.RED}TEST FAILED{ANSI.Fore.RESET}: {test.name}"
            self._print_trace(f"{fail_line}\n{underline}\n{trace}")

    # ------------------------------------------------------------------ keyword

    def start_keyword(self, keyword, result):
        name = getattr(result, "kwname", None) or getattr(result, "name", None) or "<unknown>"
        lib = getattr(result, "libname", None)
        args = getattr(result, "args", None) or []
        argstr = ", ".join(repr(a) for a in args)
        kwstr = f"{lib}.{name}" if lib else name
        prefix = self._indent()
        trace_line = f"{prefix}▶ {kwstr}({argstr})"
        self.keyword_stack.append(trace_line)
        self.keyword_depth += 1

        self._write_status_line(2, f"[{kwstr}]  {argstr}")

    def end_keyword(self, keyword, result):
        self.keyword_depth -= 1
        if result.status == "NOT RUN":
            # Discard; the header was never flushed so it just disappears.
            self.keyword_stack.pop()
            self._write_status_line(2, "")
            return

        # Keyword ran — flush any pending ancestor headers (and this one)
        # so the hierarchy appears in the trace.
        self._flush_keyword_stack()

        elapsed_ms = getattr(result, "elapsedtime", None)

        elapsed = self._format_time(elapsed_ms / 1000.0) if elapsed_ms is not None else "?s"

        keyword_trace = self._indent() + "  "
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

        self.current_test_trace += keyword_trace + "\n"

        self._write_status_line(2, "")

    # ------------------------------------------------------------------ logging

    def log_message(self, message):
        level = getattr(message, "level", None) or "UNKNOWN"
        text = getattr(message, "message", None) or ""

        # Flush keyword headers so they appear above the log line.
        self._flush_keyword_stack()

        indent = self._indent()
        level_initial = level[0].upper()
        text_lines = text.splitlines()
        formatted_lines = []
        # First line gets level initial
        formatted_lines.append(f"{indent}{level_initial} {text_lines[0]}")
        # Remaining lines align without repeating the level
        for text_line in text_lines[1:]:
            formatted_lines.append(f"{indent}  {text_line}")

        if self.colors:
            if level == "FAIL":
                formatted_lines = [f"{ANSI.Fore.BRIGHT_RED}{line}{ANSI.Fore.RESET}" for line in formatted_lines]
            elif level == "WARN":
                formatted_lines = [f"{ANSI.Fore.BRIGHT_YELLOW}{line}{ANSI.Fore.RESET}" for line in formatted_lines]
            elif level == "INFO":
                formatted_lines = [f"{ANSI.Fore.BRIGHT_BLACK}{line}{ANSI.Fore.RESET}" for line in formatted_lines]
            elif level == "DEBUG" or level == "TRACE":
                formatted_lines = [f"{ANSI.Fore.WHITE}{line}{ANSI.Fore.RESET}" for line in formatted_lines]

        self.current_test_trace += "\n".join(formatted_lines) + "\n"

    # ------------------------------------------------------------------ close

    def close(self):
        total = (
            self.suite_total_tests
            if isinstance(self.suite_total_tests, int)
            and self.suite_total_tests > 0
            else self.started_tests
        )

        self._clear_status_box()

        if self.verbosity >= Verbosity.NORMAL:
            self._writeln(
                "RUN COMPLETE: %d test%s, %d completed (%d passed, %d skipped, %d failed)."
                % (total, "" if total == 1 else "s", self.completed_tests,
                   self.passed_tests, self.skipped_tests, self.failed_tests)
            )

        if self.run_start is not None and self.verbosity >= Verbosity.NORMAL:
            self._writeln(
                "Total elapsed: %s."
                % self._format_time(time.time() - self.run_start)
            )
