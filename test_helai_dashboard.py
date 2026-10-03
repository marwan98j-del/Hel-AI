import unittest
from datetime import date, datetime
from html import escape

from helai_i18n import count_phrase, translate_booster_label
from helai_ui import (
    FEED_PAGE_SIZE,
    IRAQ_TIME,
    feed_limit,
    feed_page,
    filter_results,
    greeting_key,
    profile_completion,
    result_sort_key,
    show_more,
    ticket_html,
)


TODAY = date(2026, 10, 4)

OPEN = {
    "title": "Chevening Scholarship Iraq 2027-2028",
    "organization": "UK FCDO",
    "source": "Opportunity Desk",
    "type": "Scholarships",
    "status": "Open",
    "deadline": "2026-10-12",
    "summary_en": "Fully funded one-year master's study in the UK.",
    "summary_ku": "خوێندنی ماستەری یەک ساڵە بە تەواوی پارەدراو.",
    "source_url": "https://www.chevening.org/",
}
LATER = dict(OPEN, title="KRG Study Abroad Scholarship Framework", deadline="2027-03-01", summary_en="Study abroad.")
CLOSED = dict(OPEN, title="Data Science Corps (DSC)", source="Grants.gov", status="Closed")
ELIGIBLE = {"score": 62, "eligible": True, "readiness": 50, "reasons": ["You meet the age requirement"],
            "eligibility_gaps": [], "readiness_gaps": ["Missing document: CV"]}
NOT_ELIGIBLE = dict(ELIGIBLE, eligible=False)


class TicketTests(unittest.TestCase):
    def test_open_row_has_score_facts_lists_and_link(self):
        html = ticket_html(dict(OPEN, requires_cv=True), ELIGIBLE, "ckb", TODAY)
        self.assertIn('class="opp"', html)
        self.assertIn('class="opp-score-value">٪٦٢<', html)
        self.assertIn("<dd>٪٥٠</dd>", html)  # readiness as plain text
        self.assertIn('<dd class="mint">', html)  # eligible
        self.assertIn('class="list-title mint"', html)
        self.assertIn('class="list-title coral"', html)
        self.assertIn('class="opp-link"', html)
        self.assertIn(OPEN["summary_ku"], html)
        self.assertIn(">Opportunity Desk<", html)
        self.assertIn("٨ ڕۆژ ماوە", html)
        self.assertIn('class="label amber"', html)  # closing within 14 days

    def test_no_ticket_border_perforation_stub_or_meter(self):
        html = ticket_html(dict(OPEN, requires_cv=True), ELIGIBLE, "en", TODAY)
        for gone in ("ticket", "perf", "stub", "meter", "btn-saffron", "pill"):
            self.assertNotIn(gone, html)

    def test_no_document_flags_shows_text(self):
        html = ticket_html(OPEN, ELIGIBLE, "en", TODAY)
        self.assertIn("<dd>No document requirements found</dd>", html)

    def test_every_piece_of_information_is_kept(self):
        opportunity = dict(OPEN, location="United Kingdom", is_ai_imported=True)
        html = ticket_html(opportunity, NOT_ELIGIBLE, "en", TODAY)
        for text in (
            "Opportunity Desk", "Scholarship", "Open", "12 OCT 2026", "8 days left",
            OPEN["title"], OPEN["organization"], "United Kingdom", escape(OPEN["summary_en"]),
            "AI imported", "Match", "62%", "Eligibility", "Not eligible", "Readiness",
            "Why it fits", "You meet the age requirement", "Still missing", "Missing document: CV",
            "View opportunity", OPEN["source_url"],
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)
        self.assertIn('<dd class="coral">Not eligible</dd>', html)

    def test_closed_row_is_compact_with_disabled_notify(self):
        html = ticket_html(CLOSED, ELIGIBLE, "ar", TODAY)
        self.assertIn("opp compact", html)
        self.assertIn("status-closed", html)
        self.assertIn('aria-disabled="true"', html)
        self.assertIn("نبّهني في الدورة القادمة", html)
        self.assertNotIn("opp-link", html)

    def test_untrusted_text_is_escaped(self):
        html = ticket_html(dict(OPEN, title="<img src=x>"), ELIGIBLE, "en", TODAY)
        self.assertNotIn("<img", html)


class FilterTests(unittest.TestCase):
    RESULTS = [(OPEN, ELIGIBLE), (LATER, NOT_ELIGIBLE), (CLOSED, ELIGIBLE)]

    def titles(self, mode, query=""):
        return [o["title"] for o, _ in filter_results(self.RESULTS, mode, query, TODAY)]

    def test_modes(self):
        self.assertEqual(len(self.titles("all")), 3)
        self.assertEqual(self.titles("eligible"), [OPEN["title"]])
        self.assertEqual(self.titles("closing"), [OPEN["title"]])
        self.assertEqual(self.titles("funded"), [OPEN["title"], CLOSED["title"]])

    def test_search(self):
        self.assertEqual(self.titles("all", "krg"), [LATER["title"]])
        self.assertEqual(self.titles("all", "grants.gov"), [CLOSED["title"]])


class CopyTests(unittest.TestCase):
    def test_hero_count_matches_spec_sentence(self):
        template, phrase = count_phrase(3, "ckb")
        self.assertEqual(template.replace("{count}", phrase), "سێ هەل ئێستا لەگەڵ تۆدا دەگونجێن.")
        template, phrase = count_phrase(2, "ar")
        self.assertEqual(template.replace("{count}", phrase), "فرصتان تناسبانك الآن.")
        self.assertEqual(count_phrase(0, "en")[1], "")

    def test_booster_labels_translate_and_unknown_pass_through(self):
        self.assertEqual(translate_booster_label("Prepare a professional CV", "ckb"), "ژیاننامەیەکی (CV) پیشەیی ئامادە بکە")
        self.assertEqual(translate_booster_label("Reach a 85.0% academic average", "ar"), "حقّق معدلًا أكاديميًا بنسبة ٪٨٥")
        self.assertEqual(translate_booster_label("Something new", "ckb"), "Something new")

    def test_greeting_uses_time_of_day(self):
        self.assertEqual(greeting_key(datetime(2026, 10, 4, 9, tzinfo=IRAQ_TIME)), "header.greeting_morning")
        self.assertEqual(greeting_key(datetime(2026, 10, 4, 14, tzinfo=IRAQ_TIME)), "header.greeting_afternoon")
        self.assertEqual(greeting_key(datetime(2026, 10, 4, 21, tzinfo=IRAQ_TIME)), "header.greeting_evening")

    def test_profile_completion(self):
        self.assertEqual(profile_completion({}), 0)
        self.assertEqual(profile_completion({"full_name": "A", "city": "Erbil", "education": "PhD"}), 25)


if __name__ == "__main__":
    unittest.main()


class MatchMessageTranslationTests(unittest.TestCase):
    """Every sentence matcher.py produces translates for ckb and ar."""

    def matcher_messages(self):
        from matcher import calculate_match
        from test_helai_rules import individual_profile

        profile = individual_profile()
        opportunities = [
            dict(OPEN, education="Master's Degree", minimum_age=25, minimum_grade=95,
                 minimum_work_experience_years=3, languages=["German"],
                 residency_requirement="Kurdistan Region", requires_portfolio=True,
                 eligible_applicant_types=["individual"], location="Erbil"),
            dict(OPEN, education="Bachelor's Degree", education_rule="exact", maximum_age=18,
                 residency_requirement="Sulaymaniyah", location="Kurdistan Region",
                 type="Grants", interests=["Education"], skills=["Research"],
                 requires_passport=True, requires_ielts=True, requires_cv=True,
                 eligible_applicant_types=["individual"]),
            dict(OPEN, education="Bachelor's Degree", minimum_age=18, minimum_grade=80,
                 minimum_work_experience_years=1, languages=["English"], residency_requirement="Iraq",
                 location="Iraq", eligible_applicant_types=["individual"]),
            dict(OPEN, location="International", education="Any", eligible_applicant_types=["organization/institution"]),
            dict(OPEN, location="", source="Grants.gov", eligible_applicant_types=[]),
            dict(OPEN, location="Nairobi, Kenya", eligible_applicant_types=["individual"]),
            dict(OPEN, education="High School", education_rule="exact", eligible_applicant_types=["individual"]),
            dict(OPEN, title="How to Write a Winning Essay", record_kind="unknown"),
            dict(OPEN, status="Closed"),
            dict(OPEN, status="forecasted"),
            dict(OPEN, status="pending"),
        ]
        messages = set()
        for opportunity in opportunities:
            result = calculate_match(profile, opportunity, reference_date=TODAY)
            messages.update(result["reasons"] + result["eligibility_gaps"] + result["readiness_gaps"])
        return messages

    def test_all_produced_messages_translate(self):
        from helai_i18n import translate_match_message

        messages = self.matcher_messages()
        self.assertGreaterEqual(len(messages), 30)
        for lang in ("ckb", "ar"):
            for message in messages:
                with self.subTest(lang=lang, message=message):
                    translated = translate_match_message(message, lang)
                    self.assertNotEqual(translated, message)
                    self.assertRegex(translated, r"[؀-ۿ]")
                    self.assertNotRegex(translated, r"[0-9]")  # digits are Eastern Arabic

    def test_english_and_unknown_pass_through(self):
        from helai_i18n import translate_match_message

        self.assertEqual(translate_match_message("You meet the age requirement", "en"), "You meet the age requirement")
        self.assertEqual(translate_match_message("A brand new sentence", "ckb"), "A brand new sentence")

    def test_ticket_shows_translated_lists(self):
        html = ticket_html(OPEN, dict(ELIGIBLE, reasons=["You meet the age requirement"]), "ckb", TODAY)
        self.assertIn("مەرجی تەمەن جێبەجێ دەکەیت", html)
        self.assertNotIn("You meet the age requirement", html)


class DeadlinesRailTests(unittest.TestCase):
    def test_only_eligible_open_matches(self):
        from helai_ui import deadlines_html

        html = deadlines_html([(OPEN, ELIGIBLE), (LATER, NOT_ELIGIBLE), (CLOSED, ELIGIBLE)], "en", TODAY)
        self.assertIn(OPEN["title"], html)
        self.assertNotIn(LATER["title"], html)
        self.assertNotIn(CLOSED["title"], html)


class SoraniTermTests(unittest.TestCase):
    def test_stored_summaries_show_hel_not_derfet(self):
        from email_service import build_email

        summary = "ئەم دەرفەتە بۆ قوتابیانە. دەرفەتەکان و دەرفەتێکی تر."
        opportunity = dict(OPEN, summary_ku=summary)
        for html in (
            ticket_html(opportunity, ELIGIBLE, "ckb", TODAY),
            build_email({"full_name": "Demo"}, opportunity, {"match_score": 62, "eligible": True}, "ckb", today=TODAY),
        ):
            self.assertNotIn("دەرفەت", html)
            self.assertIn("ئەم هەلە بۆ قوتابیانە. هەلەکان و هەلێکی تر.", html)


class SignInPreviewTests(unittest.TestCase):
    def test_preview_is_a_labelled_fictional_example_in_every_language(self):
        from helai_ui import sign_in_intro_html

        expected = {
            "en": ("Example Scholarship 2027", "Example Foundation", "87%", "Example"),
            "ckb": ("سکۆڵەرشیپی نموونە ٢٠٢٧", "دامەزراوەی نموونە", "٪٨٧", "نموونە"),
            "ar": ("منحة دراسية تجريبية ٢٠٢٧", "مؤسسة تجريبية", "٪٨٧", "مثال"),
        }
        for lang, (title, org, score, label) in expected.items():
            with self.subTest(lang=lang):
                html = sign_in_intro_html(lang, today=TODAY)
                for text in (title, org, score):
                    self.assertIn(text, html)
                self.assertIn(f'auth-preview-label">{label}<', html)
                self.assertIn("٣ تشرینی دووەم ٢٠٢٦" if lang == "ckb" else "", html)  # today + 30 days

    def test_preview_never_uses_real_opportunity_data(self):
        import inspect
        from helai_ui import sign_in_intro_html

        self.assertEqual(list(inspect.signature(sign_in_intro_html).parameters), ["lang", "today"])
        html = sign_in_intro_html("en", today=TODAY)
        for real in ("Chevening", "Opportunity Desk", "Grants.gov"):
            self.assertNotIn(real, html)


class MobileStatGridTests(unittest.TestCase):
    def test_phones_keep_two_by_two_stat_grid(self):
        import re
        from helai_ui import BASE_CSS

        phone_block = BASE_CSS[BASE_CSS.index("@media (max-width: 480px)"):]
        phone_block = phone_block[: phone_block.index("\n}\n")]
        self.assertNotRegex(phone_block, r"\.stat-strip\s*\{[^}]*grid-template-columns")
        tablet_block = BASE_CSS[BASE_CSS.index("@media (max-width: 1100px)"):]
        self.assertRegex(tablet_block, r"\.stat-strip \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\); \}")


class FeedPagingTests(unittest.TestCase):
    def test_first_page_then_ten_more_each_time(self):
        items = list(range(25))
        self.assertEqual(feed_page(items, FEED_PAGE_SIZE), (items[:10], 15, 10))
        self.assertEqual(feed_page(items, 20), (items[:20], 5, 5))
        self.assertEqual(feed_page(items, 30), (items, 0, 0))
        self.assertEqual(feed_page([], FEED_PAGE_SIZE), ([], 0, 0))

    def test_show_more_grows_the_same_view(self):
        state = {}
        view = ("all", "")
        self.assertEqual(feed_limit(state, view), 10)
        show_more(state)
        show_more(state)
        self.assertEqual(feed_limit(state, view), 30)

    def test_new_filter_or_search_starts_at_one_page(self):
        state = {}
        feed_limit(state, ("all", ""))
        show_more(state)
        self.assertEqual(feed_limit(state, ("eligible", "")), 10)
        show_more(state)
        self.assertEqual(feed_limit(state, ("eligible", "chevening")), 10)

    def test_paging_keeps_sort_order_and_filter(self):
        results = []
        for index in range(23):
            opportunity = dict(OPEN, title=f"Opportunity {index}", deadline=f"2026-11-{index + 1:02d}")
            result = dict(ELIGIBLE, score=40 + index, eligible=index % 2 == 0)
            results.append((opportunity, result))
        results.sort(key=lambda item: result_sort_key(item, TODAY), reverse=True)

        eligible = filter_results(results, "eligible", "", TODAY)
        shown, remaining, next_page = feed_page(eligible, 10)
        self.assertEqual(shown, eligible[:10])
        self.assertTrue(all(result["eligible"] for _opportunity, result in shown))
        self.assertEqual((remaining, next_page), (len(eligible) - 10, 2))

    def test_show_more_label_in_every_language(self):
        from helai_i18n import t

        self.assertEqual(t("feed.show_more", lang="en", count="10", remaining="92"), "Show 10 more · 92 remaining")
        for lang in ("ckb", "ar"):
            label = t("feed.show_more", lang=lang, count="١٠", remaining="٩٢")
            self.assertIn("١٠", label)
            self.assertIn("٩٢", label)
