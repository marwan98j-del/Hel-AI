import re
import threading
import unittest
from pathlib import Path

import ai_import_limits as limits
from helai_i18n import format_number, t


HERE = Path(__file__).resolve().parent
NOW = 1_800_000_000.0


class LengthLimitTests(unittest.TestCase):
    def test_text_at_the_limit_is_allowed(self):
        self.assertIsNone(limits.import_block({}, "x" * limits.MAX_CHARS, NOW))

    def test_longer_text_is_blocked_with_the_limit(self):
        self.assertEqual(
            limits.import_block({}, "x" * (limits.MAX_CHARS + 1), NOW),
            ("import.too_long", {"limit": limits.MAX_CHARS}),
        )

    def test_long_text_does_not_use_up_a_run(self):
        state = {}
        limits.import_block(state, "x" * (limits.MAX_CHARS + 1), NOW)
        self.assertEqual(limits.recent_runs(state, NOW), [])


class HourlyLimitTests(unittest.TestCase):
    def use_runs(self, state, count, start=NOW, step=60):
        for index in range(count):
            limits.record_run(state, start + index * step)

    def test_runs_up_to_the_hourly_limit_are_allowed(self):
        state = {}
        for index in range(limits.RUNS_PER_HOUR):
            moment = NOW + index * 60
            self.assertIsNone(limits.import_block(state, "text", moment))
            limits.record_run(state, moment)

    def test_next_run_in_the_same_hour_is_blocked(self):
        state = {}
        self.use_runs(state, limits.RUNS_PER_HOUR)
        last = NOW + (limits.RUNS_PER_HOUR - 1) * 60
        key, values = limits.import_block(state, "text", last + 30)
        self.assertEqual(key, "import.rate_limited")
        self.assertEqual(values["count"], limits.RUNS_PER_HOUR)
        # The oldest run frees its slot an hour after it started.
        expected_wait = (NOW + limits.WINDOW_SECONDS) - (last + 30)
        self.assertEqual(values["minutes"], -(-int(expected_wait) // 60))

    def test_wait_is_never_shown_as_zero_minutes(self):
        state = {}
        self.use_runs(state, limits.RUNS_PER_HOUR, step=0)
        _key, values = limits.import_block(state, "text", NOW + limits.WINDOW_SECONDS - 1)
        self.assertEqual(values["minutes"], 1)

    def test_runs_older_than_an_hour_free_their_slots(self):
        state = {}
        self.use_runs(state, limits.RUNS_PER_HOUR, step=0)
        self.assertIsNone(limits.import_block(state, "text", NOW + limits.WINDOW_SECONDS))
        limits.record_run(state, NOW + limits.WINDOW_SECONDS)
        self.assertEqual(len(state[limits.RUNS_KEY]), 1)

    def test_sessions_are_counted_separately(self):
        first, second = {}, {}
        self.use_runs(first, limits.RUNS_PER_HOUR)
        self.assertIsNotNone(limits.import_block(first, "text", NOW + 600))
        self.assertIsNone(limits.import_block(second, "text", NOW + 600))


class PerAccountLimitTests(unittest.TestCase):
    """The app counts runs per account, so a reload or new session can't reset them."""

    def setUp(self):
        limits.reset_accounts()

    def tearDown(self):
        limits.reset_accounts()

    def test_limit_survives_a_new_session_for_the_same_account(self):
        for index in range(limits.RUNS_PER_HOUR):
            self.assertIsNone(limits.start_import("user-1", "text", NOW + index))
        # A reload starts a new Streamlit session but the same account id.
        key, _values = limits.start_import("user-1", "text", NOW + 100)
        self.assertEqual(key, "import.rate_limited")

    def test_accounts_are_counted_separately(self):
        for index in range(limits.RUNS_PER_HOUR):
            limits.start_import("user-1", "text", NOW + index)
        self.assertIsNone(limits.start_import("user-2", "text", NOW + 100))

    def test_blocked_attempts_do_not_extend_the_wait(self):
        for index in range(limits.RUNS_PER_HOUR):
            limits.start_import("user-1", "text", NOW + index)
        for attempt in range(10):
            limits.start_import("user-1", "text", NOW + 100 + attempt)
        self.assertIsNone(limits.start_import("user-1", "text", NOW + limits.WINDOW_SECONDS))

    def test_too_long_text_is_not_counted(self):
        limits.start_import("user-1", "x" * (limits.MAX_CHARS + 1), NOW)
        for index in range(limits.RUNS_PER_HOUR):
            self.assertIsNone(limits.start_import("user-1", "text", NOW + index + 1))

    def test_parallel_tabs_cannot_pass_the_limit(self):
        allowed = []
        start = threading.Barrier(20)

        def click():
            start.wait()
            if limits.start_import("user-1", "text", NOW) is None:
                allowed.append(1)

        threads = [threading.Thread(target=click) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(allowed), limits.RUNS_PER_HOUR)


class LimitMessageTests(unittest.TestCase):
    def test_messages_in_every_language(self):
        for lang in ("en", "ckb", "ar"):
            with self.subTest(lang=lang):
                too_long = t("import.too_long", lang=lang, limit=format_number(12000, lang))
                rate = t("import.rate_limited", lang=lang, count=format_number(5, lang), minutes=format_number(42, lang))
                self.assertNotIn("{", too_long + rate)
                if lang == "en":
                    self.assertIn("12000", too_long)
                    self.assertIn("42 minutes", rate)
                else:
                    self.assertIn("١٢٠٠٠", too_long)
                    self.assertIn("٤٢", rate)
                    self.assertNotRegex(too_long + rate, r"[0-9]")


class AppWiringTests(unittest.TestCase):
    """The app must check the limits before every OpenAI call and never print raw errors."""

    APP = (HERE / "app.py").read_text(encoding="utf-8")

    def test_limits_are_checked_per_account_before_extraction(self):
        check = self.APP.index("start_import(current_user_id(), announcement_text)")
        extract = self.APP.index("extract_opportunity(\n")
        self.assertLess(check, extract)
        # Session-only counting would reset on every reload.
        self.assertNotIn("import_block(st.session_state", self.APP)
        self.assertNotIn("record_run(st.session_state", self.APP)

    def test_no_raw_errors_reach_visitors(self):
        self.assertNotRegex(self.APP, r"t\([^)]*\b(error|message)=")
        self.assertNotRegex(self.APP, r"st\.(error|warning|success|info)\([^)]*\[\"message\"\]")

    def test_streamlit_hides_error_details(self):
        config = (HERE / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        self.assertRegex(config, re.compile(r'^showErrorDetails = "none"$', re.M))


if __name__ == "__main__":
    unittest.main()
