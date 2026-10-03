import contextlib
import io
import re
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

import helai_pipeline
import helai_ui
import notification_service
import telegram_link
import telegram_link_now
import telegram_service
from helai_i18n import EN, TRANSLATIONS, t, translate_match_message


TODAY = date(2026, 10, 2)
FAKE_TOKEN = "123456:FAKE-test-token"


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.call = {"table": table, "action": "select", "payload": None, "filters": []}

    def select(self, _fields="*"):
        return self

    def insert(self, payload):
        self.call.update(action="insert", payload=payload)
        return self

    def update(self, payload):
        self.call.update(action="update", payload=payload)
        return self

    def upsert(self, payload, **_kwargs):
        self.call.update(action="upsert", payload=payload)
        return self

    def delete(self):
        self.call["action"] = "delete"
        return self

    def eq(self, column, value):
        self.call["filters"].append(("eq", column, value))
        return self

    def is_(self, column, value):
        self.call["filters"].append(("is", column, value))
        return self

    def limit(self, _count):
        return self

    def execute(self):
        self.client.calls.append(self.call)
        key = (self.call["table"], self.call["action"])
        data = self.client.results.get(key, [])
        if callable(data):
            data = data(self.call)
        return SimpleNamespace(data=data)


class FakeClient:
    def __init__(self, results=None):
        self.results = results or {}
        self.calls = []

    def table(self, name):
        return FakeQuery(self, name)

    def actions(self, table, action):
        return [call for call in self.calls if call["table"] == table and call["action"] == action]


def opportunity(**overrides):
    record = {
        "id": "o1",
        "title": "Global Leaders Fellowship",
        "organization": "Open Society <Foundations> & Co",
        "type": "Fellowships",
        "deadline": "2026-10-12",
        "status": "Open",
        "source_url": "https://example.com/fellowship",
    }
    record.update(overrides)
    return record


def match(**overrides):
    record = {
        "id": "m1",
        "match_score": 90,
        "eligible": True,
        "reasons": [
            "You meet the age requirement",
            "No specific education level is required",
            "Minimum age is 18",
            "A fourth reason that should be cut",
        ],
        "eligibility_gaps": [],
        "readiness_gaps": ["Missing document: Valid passport"],
    }
    record.update(overrides)
    return record


def http_response(status, body):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body
    response.text = str(body)
    return response


# =========================================================
# MESSAGE RENDERING
# =========================================================

class MessageRenderingTests(unittest.TestCase):
    def render(self, lang, **match_overrides):
        return telegram_service.build_message(
            {"full_name": "Test"},
            opportunity(),
            match(**match_overrides),
            lang,
            today=TODAY,
        )

    def test_english_message_has_the_email_content(self):
        text = self.render("en")
        self.assertIn("<b>Global Leaders Fellowship</b>", text)
        self.assertIn("Open Society &lt;Foundations&gt; &amp; Co", text)
        self.assertIn("<b>90%</b>", text)
        self.assertIn(t("email.eligible", lang="en"), text)
        self.assertIn(t("card.why_it_fits", lang="en"), text)
        self.assertIn(t("email.still_missing", lang="en"), text)
        self.assertIn("12 OCT 2026", text)
        self.assertIn("10 days left", text)
        self.assertIn(t("telegram.footer", lang="en"), text)

    def test_kurdish_and_arabic_use_their_text_and_eastern_digits(self):
        for lang in ("ckb", "ar"):
            with self.subTest(lang=lang):
                text = self.render(lang)
                self.assertIn(t("email.new_match", lang=lang), text)
                self.assertIn(t("email.eligible", lang=lang), text)
                self.assertIn(t("card.why_it_fits", lang=lang), text)
                self.assertIn(translate_match_message("You meet the age requirement", lang), text)
                self.assertIn("٪٩٠", text)
                self.assertIn(t("email.days_left", lang=lang, days="١٠"), text)
                self.assertIn("٢٠٢٦", text)
                # Every number is Eastern Arabic: no Western digits anywhere.
                self.assertNotRegex(text, r"[0-9]")

    def test_only_basic_telegram_html(self):
        for lang in ("en", "ckb", "ar"):
            with self.subTest(lang=lang):
                text = self.render(lang)
                tags = set(re.findall(r"</?([a-z]+)", text))
                self.assertLessEqual(tags, {"b", "i"})
                self.assertNotIn("<table", text)

    def test_lists_are_short(self):
        text = self.render("en")
        self.assertEqual(text.count("• "), 3 + 1)
        self.assertNotIn("A fourth reason", text)

    def test_empty_lists_and_missing_deadline_say_so(self):
        text = telegram_service.build_message(
            {},
            opportunity(deadline=None),
            match(reasons=[], readiness_gaps=[]),
            "en",
            today=TODAY,
        )
        self.assertIn(t("email.nothing_missing", lang="en"), text)
        self.assertIn(t("email.no_deadline", lang="en"), text)

    def test_link_button_only_for_web_urls(self):
        with (
            patch.object(telegram_service, "TELEGRAM_BOT_TOKEN", FAKE_TOKEN),
            patch("telegram_service.requests.post", return_value=http_response(200, {"ok": True, "result": {}})) as post,
        ):
            telegram_service.send_message(1, "x", "View", "https://example.com/a")
            telegram_service.send_message(1, "x", "View", "javascript:alert(1)")
        with_button = post.call_args_list[0].kwargs["json"]
        without_button = post.call_args_list[1].kwargs["json"]
        self.assertEqual(
            with_button["reply_markup"]["inline_keyboard"][0][0],
            {"text": "View", "url": "https://example.com/a"},
        )
        self.assertEqual(with_button["parse_mode"], "HTML")
        self.assertNotIn("reply_markup", without_button)


# =========================================================
# LINK CODES
# =========================================================

class LinkCodeTests(unittest.TestCase):
    def test_codes_are_long_unambiguous_and_unique(self):
        codes = {telegram_link.generate_code() for _ in range(500)}
        self.assertEqual(len(codes), 500)
        for code in codes:
            self.assertRegex(code, r"^[A-Z2-9]{12}$")  # matches the SQL check
            self.assertTrue(telegram_link.is_valid_code_format(code))
            self.assertFalse(set(code) & set("01IO"))

    def test_bot_link(self):
        self.assertEqual(
            telegram_link.bot_link("ABCDEFGH2345"),
            "https://t.me/HelAIOpportunityBot?start=ABCDEFGH2345",
        )

    def test_parse_start(self):
        self.assertEqual(telegram_link.parse_start("/start ABCDEFGH2345"), (True, "ABCDEFGH2345"))
        self.assertEqual(telegram_link.parse_start("/start abcdefgh2345"), (True, "ABCDEFGH2345"))
        self.assertEqual(telegram_link.parse_start("/start@HelAIOpportunityBot X"), (True, "X"))
        self.assertEqual(telegram_link.parse_start("/start"), (True, None))
        self.assertEqual(telegram_link.parse_start("hello"), (False, None))
        self.assertEqual(telegram_link.parse_start(None), (False, None))
        self.assertFalse(telegram_link.is_valid_code_format("SHORT"))
        self.assertFalse(telegram_link.is_valid_code_format("ABCDEFGH234O"))

    def test_expiry_is_judged_by_when_start_was_pressed(self):
        created = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        row = {"expires_at": (created + timedelta(minutes=30)).isoformat(), "used_at": None}
        pressed_in_time = int((created + timedelta(minutes=29)).timestamp())
        pressed_late = int((created + timedelta(minutes=31)).timestamp())
        self.assertTrue(telegram_link.code_is_usable(row, pressed_in_time))
        self.assertFalse(telegram_link.code_is_usable(row, pressed_late))

    def test_used_or_missing_codes_are_never_usable(self):
        future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        now = int(datetime.now(timezone.utc).timestamp())
        self.assertFalse(telegram_link.code_is_usable({"expires_at": future, "used_at": future}, now))
        self.assertFalse(telegram_link.code_is_usable(None, now))
        self.assertFalse(telegram_link.code_is_usable({"expires_at": None}, now))

    def test_app_replaces_its_code_well_before_it_expires(self):
        created = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(telegram_link.code_is_fresh(created.isoformat(), created + timedelta(minutes=19)))
        self.assertFalse(telegram_link.code_is_fresh(created.isoformat(), created + timedelta(minutes=20)))
        self.assertFalse(telegram_link.code_is_fresh(None))
        # A code taken from the button still has ten minutes to be used.
        self.assertGreaterEqual(telegram_link.LINK_CODE_MINUTES - telegram_link.CODE_REUSE_MINUTES, 10)

    def test_app_creates_code_without_choosing_expiry(self):
        client = FakeClient()
        code = telegram_link.create_link_code(client, "u1")
        insert = client.actions("telegram_link_codes", "insert")[0]
        self.assertEqual(insert["payload"], {"code": code, "user_id": "u1"})


class LinkingFlowTests(unittest.TestCase):
    NOW = "2026-10-02T12:10:00+00:00"

    def message(self, text, chat_type="private", minutes_after=5):
        pressed = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes_after)
        return {
            "chat": {"id": 555, "type": chat_type},
            "from": {"language_code": "en"},
            "date": int(pressed.timestamp()),
            "text": text,
        }

    def client(self, used_at=None, claimed=True, linked_chat=None):
        return FakeClient({
            ("telegram_link_codes", "select"): [{
                "code": "ABCDEFGH2345",
                "user_id": "u1",
                "expires_at": "2026-10-02T12:30:00+00:00",
                "used_at": used_at,
            }],
            ("telegram_link_codes", "update"): [{"code": "ABCDEFGH2345"}] if claimed else [],
            ("telegram_connections", "select"): [{"chat_id": linked_chat}] if linked_chat else [],
            ("profiles", "select"): [{"id": "u1", "preferred_language": "Arabic"}],
        })

    def run_start(self, client, message, test_mode=False, test_chat=""):
        with (
            patch.object(telegram_service, "TEST_MODE", test_mode),
            patch.object(telegram_service, "TEST_CHAT_ID", test_chat),
            patch("telegram_service.send_message", return_value={"success": True}) as send,
            patch("telegram_service.get_one", return_value={"id": "u1", "preferred_language": "Arabic"}),
        ):
            outcome = telegram_service.handle_start(client, message, self.NOW)
        return outcome, send

    def test_valid_code_links_once_and_replies_in_profile_language(self):
        client = self.client()
        outcome, send = self.run_start(client, self.message("/start ABCDEFGH2345"))
        self.assertEqual(outcome, "linked")
        claim = client.actions("telegram_link_codes", "update")[0]
        self.assertEqual(claim["payload"], {"used_at": self.NOW})
        self.assertIn(("is", "used_at", "null"), claim["filters"])
        connection = client.actions("telegram_connections", "upsert")[0]["payload"]
        self.assertEqual((connection["user_id"], connection["chat_id"]), ("u1", 555))
        self.assertEqual(client.actions("profiles", "update")[0]["payload"], {"notify_telegram": True})
        self.assertIn(t("telegram.linked", lang="ar"), send.call_args.args[1])

    def test_expired_code_is_rejected(self):
        client = self.client()
        outcome, send = self.run_start(client, self.message("/start ABCDEFGH2345", minutes_after=31))
        self.assertEqual(outcome, "invalid")
        self.assertFalse(client.actions("telegram_connections", "upsert"))
        self.assertFalse(client.actions("telegram_link_codes", "update"))
        self.assertIn(t("telegram.link_invalid", lang="en"), send.call_args.args[1])

    def test_used_code_is_rejected(self):
        client = self.client(used_at="2026-10-02T12:01:00+00:00")
        outcome, _send = self.run_start(client, self.message("/start ABCDEFGH2345"))
        self.assertEqual(outcome, "invalid")
        self.assertFalse(client.actions("telegram_connections", "upsert"))

    def test_code_claimed_by_a_parallel_run_is_rejected(self):
        client = self.client(claimed=False)
        outcome, _send = self.run_start(client, self.message("/start ABCDEFGH2345"))
        self.assertEqual(outcome, "invalid")
        self.assertFalse(client.actions("telegram_connections", "upsert"))

    def test_start_read_by_both_the_app_and_the_collector_links_quietly_once(self):
        # The other process claimed the code between our read and our claim.
        client = self.client(claimed=False, linked_chat=555)
        outcome, send = self.run_start(client, self.message("/start ABCDEFGH2345"))
        self.assertEqual(outcome, "duplicate")
        send.assert_not_called()
        self.assertFalse(client.actions("telegram_connections", "upsert"))

    def test_used_code_from_another_chat_is_still_rejected(self):
        client = self.client(used_at="2026-10-02T12:01:00+00:00", linked_chat=999)
        outcome, send = self.run_start(client, self.message("/start ABCDEFGH2345"))
        self.assertEqual(outcome, "invalid")
        self.assertIn(t("telegram.link_invalid", lang="en"), send.call_args.args[1])

    def test_malformed_code_never_reaches_the_database(self):
        client = self.client()
        outcome, _send = self.run_start(client, self.message("/start nope"))
        self.assertEqual(outcome, "invalid")
        self.assertFalse(client.calls)

    def test_group_chats_and_other_text_are_ignored(self):
        client = self.client()
        self.assertEqual(self.run_start(client, self.message("/start ABCDEFGH2345", chat_type="group"))[0], "ignored")
        self.assertEqual(self.run_start(client, self.message("hello"))[0], "ignored")
        self.assertFalse(client.calls)

    def test_test_mode_replies_only_to_the_test_chat(self):
        _outcome, send = self.run_start(self.client(), self.message("/start ABCDEFGH2345"), test_mode=True, test_chat="999")
        send.assert_not_called()
        _outcome, send = self.run_start(self.client(), self.message("/start ABCDEFGH2345"), test_mode=True, test_chat="555")
        send.assert_called_once()

    def test_updates_are_acknowledged_after_processing(self):
        updates = [
            {"update_id": 41, "message": self.message("/start")},
            {"update_id": 42, "message": self.message("hi")},
        ]
        with (
            patch.object(telegram_service, "TELEGRAM_BOT_TOKEN", FAKE_TOKEN),
            patch.object(telegram_service, "TEST_MODE", True),
            patch.object(telegram_service, "TEST_CHAT_ID", ""),
            patch("telegram_service.get_updates", side_effect=[{"success": True, "data": updates}, {"success": True, "data": []}]) as get_updates,
        ):
            counts = telegram_service.process_link_codes(client=FakeClient(), now=self.NOW)
        self.assertEqual(counts["hint"], 1)
        self.assertEqual(counts["ignored"], 1)
        self.assertEqual(get_updates.call_args_list[1].kwargs, {"offset": 43, "limit": 1})


# =========================================================
# INSTANT LINKING FROM THE APP
# =========================================================

class FakeProcess:
    def __init__(self):
        self.finished = False

    def poll(self):
        return 0 if self.finished else None


class LinkCheckRunnerTests(unittest.TestCase):
    def runner(self):
        self.now = 100.0
        self.started = []

        def popen(command, **kwargs):
            self.started.append((command, kwargs))
            return FakeProcess()

        return telegram_link.LinkCheckRunner(clock=lambda: self.now, popen=popen)

    def test_runs_the_link_now_script_with_this_python(self):
        runner = self.runner()
        self.assertTrue(runner.request())
        command, kwargs = self.started[0]
        self.assertEqual(command, [sys.executable, str(telegram_link.LINK_NOW_SCRIPT)])
        self.assertTrue(telegram_link.LINK_NOW_SCRIPT.exists())
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)

    def test_one_check_at_a_time(self):
        runner = self.runner()
        runner.request()
        self.now += 60
        self.assertFalse(runner.request())
        self.assertEqual(len(self.started), 1)

    def test_finished_check_waits_out_the_interval(self):
        runner = self.runner()
        runner.request()
        runner.process.finished = True
        self.now += telegram_link.LINK_CHECK_SECONDS - 1
        self.assertFalse(runner.request())
        self.now += 1
        self.assertTrue(runner.request())
        self.assertEqual(len(self.started), 2)

    def test_a_check_that_cannot_start_is_not_retried_at_once(self):
        runner = self.runner()
        runner.popen = MagicMock(side_effect=OSError("no python"))
        with self.assertRaises(OSError):
            runner.request()
        self.assertFalse(runner.request())
        runner.popen.assert_called_once()


class LinkNowScriptTests(unittest.TestCase):
    def run_main(self, counts):
        stderr = io.StringIO()

        def fake_process():
            print("HELAI TELEGRAM LINKING banner")
            return counts

        with (
            patch("telegram_link_now.process_link_codes", side_effect=fake_process),
            contextlib.redirect_stderr(stderr),
            contextlib.redirect_stdout(io.StringIO()) as stdout,
        ):
            code = telegram_link_now.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_quiet_when_there_is_nothing_to_link(self):
        self.assertEqual(self.run_main({"linked": 0, "errors": 0}), (0, "", ""))

    def test_reports_links_and_errors_to_the_server_log(self):
        _code, _stdout, stderr = self.run_main({"linked": 2, "errors": 0})
        self.assertIn("linked 2", stderr)
        _code, _stdout, stderr = self.run_main({"linked": 0, "errors": 0, "error": "Telegram API error 409"})
        self.assertIn("banner", stderr)

    def test_reads_the_bot_and_links_a_waiting_user(self):
        update = {
            "update_id": 7,
            "message": {
                "chat": {"id": 555, "type": "private"},
                "from": {"language_code": "en"},
                "date": int(datetime.now(timezone.utc).timestamp()),
                "text": "/start ABCDEFGH2345",
            },
        }
        future = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
        client = FakeClient({
            ("telegram_link_codes", "select"): [{"code": "ABCDEFGH2345", "user_id": "u1", "expires_at": future, "used_at": None}],
            ("telegram_link_codes", "update"): [{"code": "ABCDEFGH2345"}],
        })
        with (
            patch.object(telegram_service, "TELEGRAM_BOT_TOKEN", FAKE_TOKEN),
            patch("telegram_service.get_updates", side_effect=[{"success": True, "data": [update]}, {"success": True, "data": []}]),
            patch("telegram_service.get_supabase", return_value=client),
            patch("telegram_service.get_one", return_value=None),
            patch("telegram_service.send_message", return_value={"success": True}),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            telegram_link_now.main()
        connection = client.actions("telegram_connections", "upsert")[0]["payload"]
        self.assertEqual((connection["user_id"], connection["chat_id"]), ("u1", 555))


class ConnectSectionTests(unittest.TestCase):
    CONNECTED = {"connected_at": "2026-10-03T09:00:00+00:00"}

    def test_status_then_instruction_then_button_in_every_language(self):
        for lang in ("ckb", "en", "ar"):
            for connection in (None, self.CONNECTED):
                with self.subTest(lang=lang, connected=bool(connection)):
                    steps = helai_ui.telegram_steps(connection, lang)
                    self.assertEqual([part for part, _text in steps], ["status", "instruction", "button"])
                    self.assertTrue(all(text.strip() for _part, text in steps))

    def test_not_connected_says_what_to_do_with_one_button(self):
        steps = dict(helai_ui.telegram_steps(None, "en"))
        self.assertEqual(steps["status"], t("telegram.not_connected", lang="en"))
        self.assertIn("Start", steps["instruction"])
        self.assertEqual(steps["button"], t("telegram.connect_button", lang="en"))

    def test_connected_state_is_clear(self):
        for lang, date_text in (("en", "3 OCT 2026"), ("ar", "٢٠٢٦")):
            with self.subTest(lang=lang):
                steps = dict(helai_ui.telegram_steps(self.CONNECTED, lang))
                self.assertIn(date_text, steps["status"])
                self.assertEqual(steps["instruction"], t("telegram.connected_copy", lang=lang))
                self.assertEqual(steps["button"], t("telegram.disconnect_button", lang=lang))

    def test_no_code_text_or_hours_wait_in_any_language(self):
        for key in ("telegram.code_help", "telegram.pending_help", "telegram.open_bot"):
            self.assertNotIn(key, EN)
        for lang in ("en", "ckb", "ar"):
            text = " ".join(
                value for key, value in TRANSLATIONS[lang].items() if key.startswith("telegram.")
            )
            with self.subTest(lang=lang):
                self.assertNotIn("{code}", text)
                self.assertNotIn("{minutes}", text)
        self.assertNotIn("hours", t("telegram.instruction", lang="en"))

    def test_bot_tells_the_user_to_go_back_to_the_app(self):
        for lang in ("en", "ckb", "ar"):
            with self.subTest(lang=lang):
                self.assertIn("HelAI", t("telegram.linked", lang=lang))


# =========================================================
# DUPLICATE PROTECTION PER CHANNEL
# =========================================================

class ChannelQueueTests(unittest.TestCase):
    MATCH = {"id": "m1", "user_id": "u1", "opportunity_id": "o1", "match_score": 90}

    def queue(self, profile, existing=(), connected=True):
        client = FakeClient({
            ("notifications", "insert"): lambda call: [dict(call["payload"], id="n-" + call["payload"]["channel"])],
        })
        with (
            patch.object(notification_service, "collector_supabase", client),
            patch("notification_service.load_profile", return_value=dict(profile)),
            patch("notification_service.load_opportunity", return_value=opportunity()),
            patch("notification_service.effective_status", return_value="Open"),
            patch("notification_service.notification_exists", side_effect=lambda _match, channel: channel in existing),
            patch("notification_service.telegram_connected", return_value=connected) as connected_check,
        ):
            result = notification_service.create_notification(dict(self.MATCH))
        inserted = [call["payload"]["channel"] for call in client.actions("notifications", "insert")]
        return result, inserted, connected_check

    def test_email_only_users_are_unchanged(self):
        result, inserted, connected_check = self.queue({"id": "u1", "email": "a@example.com", "email_notifications": True})
        self.assertTrue(result["created"])
        self.assertEqual(inserted, ["email"])
        connected_check.assert_not_called()

    def test_both_channels_queue_one_row_each(self):
        result, inserted, _ = self.queue({"id": "u1", "email": "a@example.com", "notify_telegram": True})
        self.assertEqual(inserted, ["email", "telegram"])
        self.assertEqual(result["channels"], ["email", "telegram"])

    def test_existing_email_row_does_not_block_telegram(self):
        _result, inserted, _ = self.queue(
            {"id": "u1", "email": "a@example.com", "notify_telegram": True},
            existing={"email"},
        )
        self.assertEqual(inserted, ["telegram"])

    def test_existing_rows_on_every_channel_create_nothing(self):
        result, inserted, _ = self.queue(
            {"id": "u1", "email": "a@example.com", "notify_telegram": True},
            existing={"email", "telegram"},
        )
        self.assertFalse(result["created"])
        self.assertEqual(result["reason"], "Notification already exists.")
        self.assertEqual(inserted, [])

    def test_telegram_needs_a_connection(self):
        _result, inserted, _ = self.queue(
            {"id": "u1", "email": "a@example.com", "notify_telegram": True},
            connected=False,
        )
        self.assertEqual(inserted, ["email"])

    def test_telegram_only_user(self):
        _result, inserted, _ = self.queue(
            {"id": "u1", "email": "a@example.com", "email_notifications": False, "notify_telegram": True},
        )
        self.assertEqual(inserted, ["telegram"])

    def test_original_email_skip_reason_kept(self):
        result, inserted, _ = self.queue({"id": "u1", "email": "a@example.com", "email_notifications": False})
        self.assertFalse(result["created"])
        self.assertEqual(result["reason"], "Email notifications disabled.")
        self.assertEqual(inserted, [])

    def test_existence_check_is_per_channel(self):
        client = FakeClient()
        with patch.object(notification_service, "collector_supabase", client):
            notification_service.notification_exists("m1", "telegram")
        self.assertIn(("eq", "channel", "telegram"), client.calls[0]["filters"])


# =========================================================
# BOT API ERRORS
# =========================================================

class ApiErrorTests(unittest.TestCase):
    def call(self, *responses):
        with (
            patch.object(telegram_service, "TELEGRAM_BOT_TOKEN", FAKE_TOKEN),
            patch("telegram_service.requests.post", side_effect=list(responses)) as post,
            patch("telegram_service.time.sleep") as sleep,
        ):
            result = telegram_service.call_api("sendMessage", {"chat_id": 1})
        return result, post, sleep

    def test_blocked_by_user(self):
        result, _, _ = self.call(http_response(403, {"ok": False, "description": "Forbidden: bot was blocked by the user"}))
        self.assertFalse(result["success"])
        self.assertEqual(result["kind"], telegram_service.KIND_BLOCKED)

    def test_bad_chat_id(self):
        result, _, _ = self.call(http_response(400, {"ok": False, "description": "Bad Request: chat not found"}))
        self.assertEqual(result["kind"], telegram_service.KIND_BAD_CHAT)

    def test_other_bad_request_is_a_normal_failure(self):
        result, _, _ = self.call(http_response(400, {"ok": False, "description": "Bad Request: can't parse entities"}))
        self.assertEqual(result["kind"], telegram_service.KIND_ERROR)

    def test_short_rate_limit_waits_once_then_succeeds(self):
        result, post, sleep = self.call(
            http_response(429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 3}}),
            http_response(200, {"ok": True, "result": {"message_id": 1}}),
        )
        self.assertTrue(result["success"])
        sleep.assert_called_once_with(3)
        self.assertEqual(post.call_count, 2)

    def test_long_rate_limit_fails_without_waiting(self):
        result, post, sleep = self.call(
            http_response(429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 600}}),
        )
        self.assertEqual(result["kind"], telegram_service.KIND_RATE_LIMITED)
        self.assertEqual(result["retry_after"], 600)
        sleep.assert_not_called()
        self.assertEqual(post.call_count, 1)

    def test_server_error_is_transient(self):
        result, _, _ = self.call(http_response(502, {}))
        self.assertEqual(result["kind"], telegram_service.KIND_TRANSIENT)

    def test_network_errors_never_leak_the_token(self):
        error = requests.ConnectionError(
            f"Max retries exceeded with url: /bot{FAKE_TOKEN}/sendMessage"
        )
        result, _, _ = self.call(error)
        self.assertEqual(result["kind"], telegram_service.KIND_TRANSIENT)
        self.assertNotIn(FAKE_TOKEN, result["error"])
        self.assertIn("<token>", result["error"])

    def test_missing_token_never_calls_the_api(self):
        with (
            patch.object(telegram_service, "TELEGRAM_BOT_TOKEN", None),
            patch("telegram_service.requests.post") as post,
        ):
            result = telegram_service.call_api("sendMessage", {})
        self.assertEqual(result["kind"], telegram_service.KIND_CONFIG)
        post.assert_not_called()


# =========================================================
# DELIVERY
# =========================================================

class DeliveryTests(unittest.TestCase):
    def notification(self, **overrides):
        record = {
            "id": "n1", "user_id": "u1", "opportunity_id": "o1", "match_id": "m1",
            "channel": "telegram", "status": "pending", "attempts": 0,
        }
        record.update(overrides)
        return record

    def deliver(self, *, send_result=None, test_mode=False, test_chat="", profile=None, chat_id=777, rows=None):
        rows = rows if rows is not None else [self.notification()]
        client = FakeClient({("notifications", "select"): rows})
        related = {
            "profiles": profile or {"id": "u1", "notify_telegram": True, "preferred_language": "English"},
            "opportunities": opportunity(deadline="2099-01-01"),
            "matches": match(),
        }
        with (
            patch.object(telegram_service, "TELEGRAM_BOT_TOKEN", FAKE_TOKEN),
            patch.object(telegram_service, "TEST_MODE", test_mode),
            patch.object(telegram_service, "TEST_CHAT_ID", test_chat),
            patch("telegram_service.get_supabase", return_value=client),
            patch("telegram_service.get_one", side_effect=lambda _c, table, _id: related[table]),
            patch("telegram_service.load_chat_id", return_value=chat_id),
            patch("telegram_service.send_message", return_value=send_result or {"success": True}) as send,
            patch("telegram_service.mark_sent") as mark_sent,
            patch("telegram_service.mark_failed") as mark_failed,
            patch("telegram_service.remove_connection") as remove,
        ):
            result = telegram_service.send_pending_telegram()
        return result, client, send, mark_sent, mark_failed, remove

    def test_reads_only_telegram_rows(self):
        _result, client, *_ = self.deliver(rows=[])
        self.assertIn(("eq", "channel", "telegram"), client.calls[0]["filters"])

    def test_sends_to_the_users_chat_with_a_button(self):
        result, _client, send, mark_sent, _failed, _remove = self.deliver()
        self.assertEqual(result["sent"], 1)
        self.assertEqual(send.call_args.args[0], 777)
        self.assertEqual(send.call_args.kwargs["button_url"], "https://example.com/fellowship")
        mark_sent.assert_called_once()

    def test_test_mode_without_chat_id_never_sends(self):
        result, _client, send, mark_sent, mark_failed, _remove = self.deliver(test_mode=True)
        self.assertEqual(result["skipped"], 1)
        send.assert_not_called()
        mark_sent.assert_not_called()
        mark_failed.assert_not_called()

    def test_test_mode_routes_only_to_the_test_chat(self):
        _result, _client, send, *_ = self.deliver(test_mode=True, test_chat="42")
        self.assertEqual(send.call_args.args[0], "42")

    def test_disabled_or_unlinked_users_are_skipped(self):
        result, _client, send, *_ = self.deliver(profile={"id": "u1", "notify_telegram": False})
        self.assertEqual(result["skipped"], 1)
        send.assert_not_called()
        result, _client, send, *_ = self.deliver(chat_id=None)
        self.assertEqual(result["skipped"], 1)
        send.assert_not_called()

    def test_blocked_bot_fails_permanently_and_disconnects(self):
        blocked = {"success": False, "kind": telegram_service.KIND_BLOCKED, "error": "Telegram API error 403: blocked"}
        result, _client, _send, mark_sent, mark_failed, remove = self.deliver(send_result=blocked)
        self.assertEqual(result["failed"], 1)
        mark_sent.assert_not_called()
        self.assertTrue(mark_failed.call_args.kwargs["final"])
        remove.assert_called_once()

    def test_blocked_test_chat_never_touches_the_user(self):
        blocked = {"success": False, "kind": telegram_service.KIND_BLOCKED, "error": "Telegram API error 403: blocked"}
        _result, _client, _send, _sent, mark_failed, remove = self.deliver(send_result=blocked, test_mode=True, test_chat="42")
        self.assertFalse(mark_failed.call_args.kwargs["final"])
        remove.assert_not_called()

    def test_temporary_failure_retries_like_email(self):
        flaky = {"success": False, "kind": telegram_service.KIND_TRANSIENT, "error": "timeout"}
        _result, _client, _send, _sent, mark_failed, remove = self.deliver(send_result=flaky)
        self.assertFalse(mark_failed.call_args.kwargs["final"])
        remove.assert_not_called()

    def test_exhausted_rows_are_not_retried(self):
        result, _client, send, *_ = self.deliver(rows=[self.notification(status="failed", attempts=3)])
        self.assertEqual(result["ready"], 0)
        send.assert_not_called()


class FinalFailureTests(unittest.TestCase):
    def test_final_failure_uses_up_attempts(self):
        client = FakeClient()
        import email_service

        email_service.mark_failed(client, {"id": "n1", "attempts": 0}, "blocked", final=True)
        email_service.mark_failed(client, {"id": "n2", "attempts": 0}, "timeout")
        updates = client.actions("notifications", "update")
        self.assertEqual(updates[0]["payload"]["attempts"], email_service.MAX_ATTEMPTS)
        self.assertEqual(updates[1]["payload"]["attempts"], 1)


class PipelineSafetyTests(unittest.TestCase):
    def test_telegram_failure_never_stops_the_run(self):
        def broken():
            raise RuntimeError(f"boom {FAKE_TOKEN}")

        with patch.object(telegram_service, "TELEGRAM_BOT_TOKEN", FAKE_TOKEN):
            result = helai_pipeline.run_telegram_step(broken)
        self.assertNotIn(FAKE_TOKEN, result["error"])


if __name__ == "__main__":
    unittest.main()
