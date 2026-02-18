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


class CLIProgress:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, verbosity="NORMAL", colors="AUTO"):
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
        self.current_test_keyword_depth = 0

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
            sys.stdout.write("\033[2K\033[1A")
        # Clear the final line and reset the cursor to the start of the line.
        sys.stdout.write("\033[2K\r")

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
        sys.stdout.write(f"\033[{line_offset}A")
        sys.stdout.write(f"\r│ {text:<{self.terminal_width - 4}.{self.terminal_width - 4}} │")
        # Move cursor back down to the bottom of the box.
        sys.stdout.write(f"\033[{line_offset}B")

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
        return "  " * min(self.current_test_keyword_depth, 20)

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
        self.current_test_keyword_depth = 0
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
        self.current_test_keyword_depth = 0
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
            self._print_trace(f"{fail_line}\n{underline}\n{trace}")

    # ------------------------------------------------------------------ keyword

    def start_keyword(self, keyword, result):
        name = getattr(result, "kwname", None) or getattr(result, "name", None) or "<unknown>"
        lib = getattr(result, "libname", None)
        args = getattr(result, "args", None) or []
        argstr = ", ".join(repr(a) for a in args)
        kwstr = f"{lib}.{name}" if lib else name
        prefix = self._indent()
        keyword_trace = f"{prefix}▶ {kwstr}({argstr})"
        self.current_test_trace += keyword_trace + "\n"
        self.current_test_keyword_depth += 1

        self._write_status_line(2, f"[{kwstr}]  {argstr}")

    def end_keyword(self, keyword, result):
        self.current_test_keyword_depth -= 1
        if result.status == "NOT RUN":
            self._write_status_line(2, "")
            return

        elapsed_ms = getattr(result, "elapsedtime", None)

        elapsed = self._format_time(elapsed_ms / 1000.0) if elapsed_ms is not None else "?s"

        keyword_trace = self._indent() + "  "
        if result.status == "PASS":
            keyword_trace += f"✓ PASS    {elapsed}"
        elif result.status == "SKIP":
            keyword_trace += f"→ SKIP    {elapsed}"
        elif result.status == "FAIL":
            keyword_trace += f"✗ FAIL    {elapsed}"
        else:
            keyword_trace += f"? {result.status}    {elapsed}"

        self.current_test_trace += keyword_trace + "\n"

        self._write_status_line(2, "")

    # ------------------------------------------------------------------ logging

    def log_message(self, message):
        level = getattr(message, "level", None) or "UNKNOWN"
        text = getattr(message, "message", None) or ""

        indent = self._indent()
        level_initial = level[0].upper()
        text_lines = text.splitlines()
        formatted_lines = []
        # First line gets level initial
        formatted_lines.append(f"{indent}{level_initial} {text_lines[0]}")
        # Remaining lines align without repeating the level
        for text_line in text_lines[1:]:
            formatted_lines.append(f"{indent}  {text_line}")

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
