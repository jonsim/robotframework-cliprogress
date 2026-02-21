import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

from CLIProgress.CLIProgress import (
    ANSI,
    CLIProgress,
    TestStatistics,
    TestTimings,
    TraceStack,
    Verbosity,
    _ANSICode,
)


class TestVerbosity(unittest.TestCase):
    def test_equality(self):
        self.assertEqual(Verbosity.QUIET, Verbosity.QUIET)

    def test_inequality(self):
        self.assertNotEqual(Verbosity.QUIET, Verbosity.NORMAL)

    def test_ordering_less_than(self):
        self.assertLess(Verbosity.QUIET, Verbosity.NORMAL)

    def test_ordering_less_than_debug(self):
        self.assertLess(Verbosity.NORMAL, Verbosity.DEBUG)

    def test_from_string_lowercase(self):
        self.assertEqual(Verbosity.from_string("quiet"), Verbosity.QUIET)

    def test_from_string_uppercase(self):
        self.assertEqual(Verbosity.from_string("NORMAL"), Verbosity.NORMAL)

    def test_from_string_mixed_case(self):
        self.assertEqual(Verbosity.from_string("DeBuG"), Verbosity.DEBUG)

    def test_from_string_invalid(self):
        self.assertEqual(Verbosity.from_string("invalid"), Verbosity.NORMAL)


class TestANSI(unittest.TestCase):
    def test_ansicode_call(self):
        code = _ANSICode("\033[31m")
        result = code("Hello")
        self.assertEqual(result, "\033[31mHello\033[0m")

    def test_ansi_len(self):
        text = "Hello \033[31mWorld\033[0m!"
        self.assertEqual(ANSI.len(text), 12)  # "Hello World!"


class TestTraceStack(unittest.TestCase):
    def test_initial_state_trace(self):
        stack = TraceStack()
        self.assertEqual(stack.trace, "")

    def test_initial_state_errors(self):
        stack = TraceStack()
        self.assertFalse(stack.has_errors)

    def test_initial_state_warnings(self):
        stack = TraceStack()
        self.assertFalse(stack.has_warnings)

    def test_push_keyword(self):
        stack = TraceStack()
        stack.push_keyword("Keyword A")
        self.assertEqual(stack._depth, 1)

    def test_pop_keyword(self):
        stack = TraceStack()
        stack.push_keyword("Keyword A")
        stack.pop_keyword()
        self.assertEqual(stack._depth, 0)

    def test_flush_keyword_depth(self):
        stack = TraceStack()
        stack.push_keyword("Keyword A")
        stack.flush()
        self.assertEqual(stack._depth, 0)

    def test_flush_keyword_trace_content(self):
        stack = TraceStack()
        stack.push_keyword("Keyword A")
        stack.flush()
        self.assertIn("Keyword A", stack.trace)


class TestTestStatistics(unittest.TestCase):
    def test_start_suite_counts(self):
        stats = TestStatistics()
        suite_mock = MagicMock()
        suite_mock.suites = [1, 2, 3]
        suite_mock.test_count = 10

        stats.start_suite(suite_mock)
        self.assertEqual(stats.top_level_suite_count, 3)
        self.assertEqual(stats.top_level_test_count, 10)

    def test_start_test_increment(self):
        stats = TestStatistics()
        stats.start_test()
        self.assertEqual(stats.started_tests, 1)

    def test_end_test_pass(self):
        stats = TestStatistics()
        result_mock = MagicMock()
        result_mock.not_run = False
        result_mock.status = "PASS"

        stats.end_test(result_mock)
        self.assertEqual(stats.completed_tests, 1)
        self.assertEqual(stats.passed_tests, 1)

    def test_end_test_fail(self):
        stats = TestStatistics()
        result_mock = MagicMock()
        result_mock.not_run = False
        result_mock.status = "FAIL"

        stats.end_test(result_mock)
        self.assertEqual(stats.completed_tests, 1)
        self.assertEqual(stats.failed_tests, 1)


class TestTestTimings(unittest.TestCase):
    def test_format_time_none(self):
        self.assertEqual(TestTimings.format_time(None), "unknown")

    def test_format_time_seconds_only(self):
        self.assertEqual(TestTimings.format_time(45), "45s")

    def test_format_time_minutes_seconds(self):
        self.assertEqual(TestTimings.format_time(125), " 2m  5s")

    def test_format_time_hours_minutes_seconds(self):
        self.assertEqual(TestTimings.format_time(3665), " 1h  1m  5s")

    @patch("time.time", return_value=100.0)
    def test_elapsed_time(self, mock_time):
        timings = TestTimings()
        timings.start_suite()
        mock_time.return_value = 110.0
        self.assertEqual(timings.get_elapsed_time(), 10.0)


class TestCLIProgressHelper(unittest.TestCase):
    def setUp(self):
        self.cli = CLIProgress(verbosity="NORMAL", console_progress="NONE")

    def test_past_tense_upper_pass(self):
        self.assertEqual(self.cli._past_tense("PASS"), "PASSED")

    def test_past_tense_upper_fail(self):
        self.assertEqual(self.cli._past_tense("FAIL"), "FAILED")

    def test_past_tense_upper_skip(self):
        self.assertEqual(self.cli._past_tense("SKIP"), "SKIPPED")

    def test_past_tense_lower(self):
        self.assertEqual(self.cli._past_tense("pass"), "passed")

    def test_past_tense_title_try(self):
        self.assertEqual(self.cli._past_tense("Try"), "Tried")

    def test_past_tense_title_stop(self):
        self.assertEqual(self.cli._past_tense("Stop"), "Stopped")

    def test_verbosity_settings_debug(self):
        cli = CLIProgress(verbosity="DEBUG", console_progress="NONE")
        self.assertTrue(cli.print_passed)
        self.assertTrue(cli.print_skipped)
        self.assertTrue(cli.print_failed)

    def test_verbosity_settings_quiet(self):
        cli_quiet = CLIProgress(verbosity="QUIET", console_progress="NONE")
        self.assertFalse(cli_quiet.print_passed)
        self.assertTrue(cli_quiet.print_failed)


class TestStatisticsFormatReturns(unittest.TestCase):
    def test_format_run_results_all_zero(self):
        stats = TestStatistics()
        stats.top_level_test_count = 0
        stats.completed_tests = 0
        stats.passed_tests = 0
        stats.skipped_tests = 0
        stats.failed_tests = 0

        expected = "0 tests, 0 completed (0 passed, 0 skipped, 0 failed)."
        self.assertEqual(stats.format_run_results(), expected)

    def test_format_run_results_one_test(self):
        stats = TestStatistics()
        stats.top_level_test_count = 1
        stats.completed_tests = 1
        stats.passed_tests = 1
        stats.skipped_tests = 0
        stats.failed_tests = 0

        expected = "1 test, 1 completed (1 passed, 0 skipped, 0 failed)."
        self.assertEqual(stats.format_run_results(), expected)

    def test_format_run_results_with_errors_and_warnings(self):
        stats = TestStatistics()
        stats.top_level_test_count = 2
        stats.completed_tests = 2
        stats.passed_tests = 1
        stats.skipped_tests = 0
        stats.failed_tests = 1
        stats.errors = 2
        stats.warnings = 1

        expected = (
            "2 tests, 2 completed (1 passed, 0 skipped, 1 failed). "
            "2 tests raised errors. 1 test raised warnings."
        )
        self.assertEqual(stats.format_run_results(), expected)


class TestTimingsFormatETA(unittest.TestCase):
    @patch("time.time", return_value=120.0)
    def test_format_eta_calculates(self, mock_time):
        timings = TestTimings()
        timings.run_start_time = 100.0  # elapsed = 20s

        stats = TestStatistics()
        stats.completed_tests = 5
        stats.top_level_test_count = 15

        # 5 tests took 20s -> 4s per test. 10 remaining -> 40s
        self.assertEqual(timings.format_eta(stats), "40s")

    def test_format_eta_unknown(self):
        timings = TestTimings()
        stats = TestStatistics()
        stats.completed_tests = 0
        self.assertEqual(timings.format_eta(stats), "unknown")


class TestCLIProgressInitialization(unittest.TestCase):
    @patch("sys.stdout.isatty", return_value=True)
    def test_colors_auto_tty(self, mock_isatty):
        cli = CLIProgress(colors="AUTO", console_progress="NONE")
        self.assertTrue(cli.colors)

    @patch("sys.stdout.isatty", return_value=False)
    def test_colors_auto_no_tty(self, mock_isatty):
        cli = CLIProgress(colors="AUTO", console_progress="NONE")
        self.assertFalse(cli.colors)

    def test_colors_on(self):
        cli = CLIProgress(colors="ON", console_progress="NONE")
        self.assertTrue(cli.colors)

    def test_colors_off(self):
        cli = CLIProgress(colors="OFF", console_progress="NONE")
        self.assertFalse(cli.colors)

    @patch("sys.stdout", new_callable=StringIO)
    def test_console_progress_stdout(self, mock_stdout):
        cli = CLIProgress(console_progress="STDOUT")
        import sys

        self.assertEqual(cli.progress_stream, sys.stdout)

    @patch("sys.stderr", new_callable=StringIO)
    def test_console_progress_stderr(self, mock_stderr):
        cli = CLIProgress(console_progress="STDERR")
        import sys

        self.assertEqual(cli.progress_stream, sys.stderr)


class TestCLIProgressLayoutAndProgressBox(unittest.TestCase):
    def setUp(self):
        from io import StringIO

        self.stream = StringIO()
        self.cli = CLIProgress(console_progress="NONE", width=80)
        self.cli.progress_stream = self.stream

    def test_draw_progress_box(self):
        self.cli._draw_progress_box()
        output = self.stream.getvalue()
        self.assertIn("┌" + "─" * (self.cli.terminal_width - 2) + "┐", output)
        self.assertIn("└" + "─" * (self.cli.terminal_width - 2) + "┘", output)

    def test_write_progress_line_truncation(self):
        left = "A" * 100
        right = "B" * 10
        self.cli._write_progress_line(0, left, right)
        line = self.cli.progress_lines[0]
        self.assertTrue(line.endswith("BBBBBBBBBB"))
        expected_left_len = self.cli.terminal_width - 4 - 10 - 1
        self.assertTrue(line.startswith("A" * (expected_left_len - 3) + "..."))

    def test_clear_progress_box(self):
        self.cli._clear_progress_box()
        self.assertIn(ANSI.Cursor.CLEAR_LINE, self.stream.getvalue())


class TestCLIProgressLifecycle(unittest.TestCase):
    def setUp(self):
        from io import StringIO

        patcher = patch("sys.stdout", new_callable=StringIO)
        self.mock_stdout = patcher.start()

        self.cli = CLIProgress(console_progress="NONE", verbosity="DEBUG")

    def tearDown(self):
        patch.stopall()

    def test_suite_lifecycle(self):
        suite_mock = MagicMock()
        suite_mock.suites = [1]
        suite_mock.test_count = 1
        suite_mock.full_name = "My_Suite"

        result_mock = MagicMock()
        result_mock.status = "PASS"

        self.cli.start_suite(suite_mock, result_mock)
        self.assertEqual(self.cli.stats.started_suites, 1)

        self.cli.end_suite(suite_mock, result_mock)
        self.assertEqual(self.cli.suite_trace_stack._depth, 0)

    def test_test_lifecycle(self):
        suite_mock = MagicMock()
        suite_mock.suites = [1]
        suite_mock.test_count = 1
        suite_mock.full_name = "My_Suite"

        self.cli.start_suite(suite_mock, MagicMock())

        test_mock = MagicMock()
        test_mock.name = "My Test"
        test_mock.full_name = "My_Suite.My Test"

        result_mock = MagicMock()
        result_mock.status = "PASS"
        result_mock.not_run = False
        result_mock.message = "All good"

        self.cli.start_test(test_mock, result_mock)
        self.assertTrue(self.cli.in_test)

        self.cli.end_test(test_mock, result_mock)
        self.assertFalse(self.cli.in_test)
        self.assertEqual(self.cli.stats.passed_tests, 1)

    def test_test_lifecycle_fail_with_errors(self):
        suite_mock = MagicMock()
        suite_mock.suites = [1]
        suite_mock.test_count = 1
        self.cli.start_suite(suite_mock, MagicMock())
        test_mock = MagicMock()
        test_mock.name = "My Test"
        result_mock = MagicMock()
        result_mock.status = "FAIL"
        result_mock.not_run = False
        result_mock.message = "Failure"

        self.cli.start_test(test_mock, result_mock)

        msg = MagicMock()
        msg.level = "ERROR"
        msg.message = "An error occurred"
        self.cli.log_message(msg)

        self.cli.end_test(test_mock, result_mock)
        self.assertEqual(self.cli.stats.failed_tests, 1)


class TestCLIProgressKeywords(unittest.TestCase):
    def setUp(self):
        self.cli = CLIProgress(console_progress="NONE", verbosity="DEBUG")

        suite_mock = MagicMock()
        suite_mock.suites = [1]
        suite_mock.test_count = 1
        self.cli.start_suite(suite_mock, MagicMock())

        self.test_mock = MagicMock()
        self.test_mock.name = "My Test"
        self.result_mock = MagicMock()
        self.result_mock.status = "PASS"
        self.result_mock.not_run = False

        self.cli.start_test(self.test_mock, self.result_mock)

    def test_keyword_lifecycle(self):
        kw_mock = MagicMock()
        kw_res_mock = MagicMock()
        kw_res_mock.name = "My Keyword"
        kw_res_mock.libname = "BuiltIn"
        kw_res_mock.args = ["arg1"]
        kw_res_mock.status = "PASS"
        kw_res_mock.elapsedtime = 1500

        self.cli.start_keyword(kw_mock, kw_res_mock)
        self.assertEqual(self.cli.test_trace_stack._depth, 1)

        self.cli.end_keyword(kw_mock, kw_res_mock)
        self.assertEqual(self.cli.test_trace_stack._depth, 0)
        self.assertIn("2s", self.cli.test_trace_stack.trace)

    def test_keyword_lifecycle_not_run(self):
        kw_mock = MagicMock()
        kw_res_mock = MagicMock()
        kw_res_mock.status = "NOT RUN"

        self.cli.start_keyword(kw_mock, kw_res_mock)
        self.cli.end_keyword(kw_mock, kw_res_mock)
        self.assertEqual(self.cli.test_trace_stack._depth, 0)


class TestCLIProgressLogging(unittest.TestCase):
    def setUp(self):
        self.cli = CLIProgress(console_progress="NONE", verbosity="DEBUG", colors="OFF")
        suite_mock = MagicMock()
        suite_mock.suites = [1]
        suite_mock.test_count = 1
        self.cli.start_suite(suite_mock, MagicMock())
        test_mock = MagicMock()
        test_mock.name = "My Test"
        self.cli.start_test(test_mock, MagicMock())

    def test_log_message_warn(self):
        msg = MagicMock()
        msg.level = "WARN"
        msg.message = "A warning\nLine 2"
        self.cli.log_message(msg)

        self.assertEqual(self.cli.stats.warnings, 1)
        self.assertTrue(self.cli.test_trace_stack.has_warnings)
        self.assertIn("W A warning", self.cli.test_trace_stack.trace)
        self.assertIn("Line 2", self.cli.test_trace_stack.trace)

    def test_log_message_error(self):
        msg = MagicMock()
        msg.level = "ERROR"
        msg.message = "An error"
        self.cli.log_message(msg)

        self.assertEqual(self.cli.stats.errors, 1)
        self.assertTrue(self.cli.test_trace_stack.has_errors)
        self.assertIn("E An error", self.cli.test_trace_stack.trace)

    def test_log_message_info(self):
        msg = MagicMock()
        msg.level = "INFO"
        msg.message = "Info msg"
        self.cli.log_message(msg)

        self.assertIn("I Info msg", self.cli.test_trace_stack.trace)


class TestCLIProgressClose(unittest.TestCase):
    def test_close_prints_summary(self):
        from io import StringIO

        cli = CLIProgress(console_progress="NONE", verbosity="NORMAL")
        cli.stats.top_level_test_count = 1
        cli.stats.completed_tests = 1

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            cli.close()
            output = mock_stdout.getvalue()
            self.assertIn("RUN COMPLETE", output)
