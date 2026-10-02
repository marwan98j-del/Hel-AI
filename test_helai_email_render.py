import re
import unittest
from datetime import date

import email_service
from email_service import (
    FSI,
    PDI,
    build_email,
    build_subject,
    email_language,
)


TODAY = date(2026, 10, 4)

PROFILE = {"full_name": "Demo User", "preferred_language": "Kurdish Sorani"}

# Real titles from the audit; the first has no document flags.
NO_DOCS = {
    "title": "Chevening Scholarship Iraq 2027-2028",
    "organization": "UK Foreign, Commonwealth & Development Office",
    "source": "Opportunity Desk",
    "type": "Scholarships",
    "location": "United Kingdom",
    "deadline": "2026-10-19",
    "summary_en": "Fully funded one-year master's study in the UK.",
    "summary_ku": "خوێندنی ماستەری یەک ساڵە بە تەواوی پارەدراو لە بەریتانیا.",
    "source_url": "https://www.chevening.org/scholarships/",
}
WITH_DOCS = dict(
    NO_DOCS,
    title="KRG Study Abroad Scholarship Framework",
    type="Grants",
    location="International",
    requires_ielts=True,
    requires_cv=True,
)
MATCH = {
    "match_score": 62,
    "eligible": True,
    "readiness": 100,
    "reasons": ["You meet the age requirement", "Matching interests: Education"],
    "eligibility_gaps": [],
    "readiness_gaps": [],
}
HALF_READY = dict(MATCH, readiness=50, readiness_gaps=["Missing document: IELTS / English certificate"])


def outside_isolates(text):
    return re.sub(f"{FSI}.*?{PDI}", "", text)


class SubjectTests(unittest.TestCase):
    def test_rtl_subjects_isolate_latin_and_use_eastern_digits(self):
        for lang, phrase in (("ckb", "بۆ تۆ"), ("ar", "لك")):
            with self.subTest(lang=lang):
                subject = build_subject(NO_DOCS, MATCH, lang)
                self.assertTrue(subject.startswith(f"{FSI}HelAI{PDI}"))
                self.assertIn(f"{FSI}{NO_DOCS['title']}{PDI}", subject)
                self.assertIn("٪٦٢", subject)
                self.assertIn(phrase, subject)
                self.assertNotRegex(outside_isolates(subject), r"[0-9%]")

    def test_english_subject_is_plain(self):
        self.assertEqual(
            build_subject(NO_DOCS, MATCH, "en"),
            "HelAI: 62% match — Chevening Scholarship Iraq 2027-2028",
        )


class BodyTests(unittest.TestCase):
    def render(self, opportunity, lang, match=MATCH):
        return build_email(PROFILE, opportunity, match, lang, today=TODAY)

    def test_kurdish_body(self):
        body = self.render(NO_DOCS, "ckb")
        self.assertIn('dir="rtl"', body)
        self.assertIn("٪٦٢", body)
        self.assertIn("سکۆڵەرشیپ", body)  # Scholarships
        self.assertIn("بەریتانیا", body)  # United Kingdom
        self.assertIn("١٥ ڕۆژ ماوە", body)
        self.assertIn("١٩ تشرینی یەکەم ٢٠٢٦", body)
        self.assertIn(NO_DOCS["summary_ku"], body)
        self.assertIn("بینینی هەلەکە", body)

    def test_arabic_body(self):
        body = self.render(WITH_DOCS, "ar", HALF_READY)
        self.assertIn("٪٦٢", body)
        self.assertIn("٪٥٠", body)
        self.assertIn("منح تمويلية", body)  # Grants
        self.assertIn("دولي", body)  # International
        self.assertIn("الأيام المتبقية: ١٥", body)
        self.assertIn("الملخص العربي غير متوفر بعد", body)
        self.assertIn("عرض الفرصة", body)

    def test_english_body(self):
        body = self.render(NO_DOCS, "en")
        self.assertIn('dir="ltr"', body)
        self.assertIn("62%", body)
        self.assertIn("15 days left", body)
        self.assertIn("19 OCT 2026", body)
        self.assertIn("View opportunity", body)
        self.assertIn("You&#x27;re eligible", body)

    def test_readiness_follows_the_ui_rule(self):
        expected = {
            "ckb": "هیچ بەڵگەنامەیەکی پێویست نەدۆزرایەوە",
            "ar": "لم يُعثر على مستندات مطلوبة",
            "en": "No document requirements found",
        }
        for lang, text in expected.items():
            with self.subTest(lang=lang):
                body = self.render(NO_DOCS, lang)
                self.assertIn(text, body)
                self.assertNotIn(">100%<", body)
                self.assertNotIn(">٪١٠٠<", body)
        self.assertIn("50%", self.render(WITH_DOCS, "en", HALF_READY))

    def test_latin_names_stay_latin(self):
        for lang in ("ckb", "ar"):
            with self.subTest(lang=lang):
                body = self.render(NO_DOCS, lang)
                self.assertIn(">HelAI<", body)
                self.assertIn(">Opportunity Desk<", body)
                self.assertIn(NO_DOCS["organization"].replace("&", "&amp;"), body)
                self.assertIn(NO_DOCS["title"], body)

    def test_why_it_fits_and_still_missing_lists(self):
        body = self.render(WITH_DOCS, "en", HALF_READY)
        self.assertIn("Why it fits", body)
        self.assertIn("You meet the age requirement", body)
        self.assertIn("Still missing", body)
        self.assertIn("Missing document: IELTS / English certificate", body)
        self.assertIn("Nothing missing that HelAI tracks.", self.render(NO_DOCS, "en"))

    def test_no_deadline_and_closing_day(self):
        self.assertIn("No deadline stated", self.render(dict(NO_DOCS, deadline=None), "en"))
        self.assertIn("هیچ دوا وادەیەک دیاری نەکراوە", self.render(dict(NO_DOCS, deadline=""), "ckb"))
        self.assertIn("Closes today", self.render(dict(NO_DOCS, deadline="2026-10-04"), "en"))

    def test_footer_links_to_profile_alerts(self):
        body = self.render(NO_DOCS, "ar")
        url = f"{email_service.HELAI_APP_URL}/?lang=ar#cloud-profile"
        self.assertIn(f'href="{url}"', body)
        self.assertIn("إدارة التنبيهات", body)
        self.assertIn("إيقاف تنبيهات البريد", body)

    def test_email_safe_markup_and_palette(self):
        for lang in ("ckb", "en", "ar"):
            with self.subTest(lang=lang):
                body = self.render(NO_DOCS, lang)
                self.assertNotRegex(body, r"<(style|link|script)\b")
                self.assertNotIn("letter-spacing", body)
                self.assertNotIn("@import", body)
                for color in ("#0E1014", "#171A21", "#252A33", "#F3F1EC", "#F4B740", "#16130B", "#5FD8A4"):
                    self.assertIn(color, body)
        self.assertIn("Tahoma, Arial", self.render(NO_DOCS, "ckb"))

    def test_untrusted_text_is_escaped(self):
        body = self.render(dict(NO_DOCS, title="<script>x</script>"), "en")
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)


class LanguageTests(unittest.TestCase):
    def test_profile_language_mapping(self):
        self.assertEqual(email_language({"preferred_language": "Kurdish Sorani"}), "ckb")
        self.assertEqual(email_language({"preferred_language": "Arabic"}), "ar")
        self.assertEqual(email_language({"preferred_language": "English"}), "en")
        self.assertEqual(email_language({"preferred_language": "Kurdish Kurmanji"}), "en")
        # Empty or unknown preferences default to Kurdish Sorani, like the app.
        self.assertEqual(email_language({}), "ckb")
        self.assertEqual(email_language({"preferred_language": None}), "ckb")
        self.assertEqual(email_language({"preferred_language": "  "}), "ckb")
        self.assertEqual(email_language({"preferred_language": "French"}), "ckb")
        self.assertEqual(email_language({"preferred_language": "کوردی سۆرانی"}), "ckb")


if __name__ == "__main__":
    unittest.main()
