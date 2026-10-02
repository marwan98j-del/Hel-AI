import re
import unittest
from datetime import date
from pathlib import Path

import helai_i18n as i18n
from helai_i18n import (
    ACTIVE_KEY,
    CHOICE_KEY,
    DEFAULT_LANGUAGE,
    format_date,
    format_number,
    format_percent,
    resolve_language,
    select_language,
    t,
    t_value,
)
from helai_ui import ICON_GUARD_CSS, RTL_CSS, build_global_css, readiness_display, status_label
from test_helai_ui_icons import ICON_GUARD_SELECTORS, css_rules


HERE = Path(__file__).parent
UI_SOURCES = {
    name: (HERE / name).read_text(encoding="utf-8")
    for name in ("app.py", "helai_ui.py")
}
ARABIC_SCRIPT = re.compile(r"[؀-ۿ]")


class TranslationTableTests(unittest.TestCase):
    def test_every_key_exists_in_all_three_languages(self):
        english_keys = set(i18n.EN)
        for lang in ("ckb", "ar"):
            with self.subTest(lang=lang):
                self.assertEqual(set(i18n.TRANSLATIONS[lang]), english_keys)

    def test_no_empty_translations(self):
        for lang, table in i18n.TRANSLATIONS.items():
            for key, value in table.items():
                with self.subTest(lang=lang, key=key):
                    self.assertTrue(value.strip())

    def test_placeholders_match_english(self):
        def fields(text):
            return set(re.findall(r"{(\w+)}", text))

        for lang in ("ckb", "ar"):
            for key, english in i18n.EN.items():
                with self.subTest(lang=lang, key=key):
                    self.assertEqual(fields(i18n.TRANSLATIONS[lang][key]), fields(english))

    def test_every_literal_key_used_by_the_ui_exists(self):
        pattern = r"""\b(?:t|esc)\(\s*["']([a-z_]+\.[^"']+)["']"""
        for name, source in UI_SOURCES.items():
            for key in re.findall(pattern, source):
                with self.subTest(file=name, key=key):
                    self.assertIn(key, i18n.EN)

    def test_ui_text_is_translated_into_arabic_script(self):
        # Sample of visible strings; Latin-only values (Microsoft Office) are exempt.
        for key in ("auth.welcome", "sidebar.sign_out", "card.eligible", "type.Grants"):
            for lang in ("ckb", "ar"):
                with self.subTest(lang=lang, key=key):
                    self.assertRegex(t(key, lang=lang), ARABIC_SCRIPT)

    def test_natural_sorani_wording(self):
        sorani = " ".join(i18n.CKB.values())
        self.assertNotIn("زێدە بکە", sorani)
        self.assertIn("زیاد بکە", sorani)
        # Readiness and the high-school level must not share a word.
        self.assertNotEqual(i18n.CKB["field.readiness"], i18n.CKB["education.High School"])

    def test_brand_and_source_names_stay_latin(self):
        for lang in ("ckb", "ar"):
            with self.subTest(lang=lang):
                self.assertIn("HelAI", t("auth.welcome", lang=lang))
        self.assertIn("latin(source_name)", UI_SOURCES["helai_ui.py"])
        self.assertIn("latin(label)", UI_SOURCES["app.py"])


class LookupTests(unittest.TestCase):
    def test_missing_key_in_language_falls_back_to_english(self):
        original = i18n.CKB.pop("auth.welcome")
        try:
            self.assertEqual(t("auth.welcome", lang="ckb"), "Welcome to HelAI")
        finally:
            i18n.CKB["auth.welcome"] = original

    def test_unknown_key_and_language_never_crash(self):
        self.assertEqual(t("does.not_exist", lang="ar"), "does.not_exist")
        self.assertEqual(t("auth.welcome", lang="fr"), t("auth.welcome", lang=DEFAULT_LANGUAGE))

    def test_bad_format_arguments_never_crash(self):
        self.assertEqual(t("profile.age_used", lang="en"), "Age used for matching: {age}")
        self.assertEqual(t("profile.age_used", lang="en", wrong=1), "Age used for matching: {age}")
        self.assertEqual(t("profile.age_used", lang="en", age=19), "Age used for matching: 19")

    def test_option_values_translate_but_unknown_values_pass_through(self):
        self.assertEqual(t_value("city", "Erbil", "ckb"), "هەولێر")
        self.assertEqual(t_value("type", "Grants", "ar"), "منح تمويلية")
        self.assertEqual(t_value("city", "Kurdistan Region", "ckb"), "Kurdistan Region")
        self.assertEqual(t_value("type", None, "ckb"), "")

    def test_status_labels(self):
        self.assertEqual(status_label("Open", "ckb"), "کراوە")
        self.assertEqual(status_label("Closed", "ar"), "مغلقة")
        self.assertEqual(status_label("Unknown", "en"), "Unknown")


class DefaultLanguageTests(unittest.TestCase):
    def test_default_is_kurdish_sorani(self):
        self.assertEqual(DEFAULT_LANGUAGE, "ckb")
        self.assertEqual(resolve_language(), "ckb")
        self.assertEqual(t("sidebar.sign_out"), i18n.CKB["sidebar.sign_out"])

    def test_resolution_order(self):
        self.assertEqual(resolve_language("ar", "English"), "ar")
        self.assertEqual(resolve_language(None, "English"), "en")
        self.assertEqual(resolve_language(None, "Arabic"), "ar")
        self.assertEqual(resolve_language(None, "Kurdish Sorani"), "ckb")
        self.assertEqual(resolve_language(None, "Kurdish Kurmanji"), "ckb")
        self.assertEqual(resolve_language("xx", None), "ckb")

    def test_select_language_uses_url_once_and_never_writes_the_profile(self):
        profile = {"preferred_language": "English"}
        state = {}
        self.assertEqual(select_language(state, None, profile), "en")
        self.assertNotIn(CHOICE_KEY, state)
        self.assertEqual(state[ACTIVE_KEY], "en")
        self.assertEqual(select_language(state, "ar", profile), "ar")
        self.assertEqual(state[CHOICE_KEY], "ar")
        self.assertEqual(profile, {"preferred_language": "English"})


class NumberAndDateTests(unittest.TestCase):
    def test_eastern_arabic_digits(self):
        self.assertEqual(format_number(2026, "ckb"), "٢٠٢٦")
        self.assertEqual(format_number(7.0, "ar"), "٧")
        self.assertEqual(format_number(2026, "en"), "2026")

    def test_percentages(self):
        self.assertEqual(format_percent(92, "ckb"), "٪٩٢")
        self.assertEqual(format_percent(100, "ar"), "٪١٠٠")
        self.assertEqual(format_percent(92, "en"), "92%")

    def test_dates(self):
        self.assertEqual(format_date("2026-10-31", "ckb"), "٣١ تشرینی یەکەم ٢٠٢٦")
        self.assertEqual(format_date(date(2026, 1, 5), "ar"), "٥ كانون الثاني ٢٠٢٦")
        self.assertEqual(format_date("2026-10-31", "en"), "31 OCT 2026")

    def test_missing_and_invalid_dates(self):
        self.assertEqual(format_date(None, "ckb"), "دیاری نەکراوە")
        self.assertEqual(format_date("rolling", "ar"), "rolling")

    def test_readiness_display_is_localized(self):
        self.assertEqual(
            readiness_display({"requires_cv": True}, {"readiness": 50}, "ckb"),
            ("٪٥٠", "warning"),
        )
        label, _ = readiness_display({}, {"readiness": 100}, "ar")
        self.assertEqual(label, "لم يُعثر على مستندات مطلوبة")


class RtlStylesheetTests(unittest.TestCase):
    def test_icon_guard_stays_last_in_rtl_styles(self):
        for lang in ("ckb", "ar", "en"):
            with self.subTest(lang=lang):
                css = build_global_css(lang)
                selector, body = css_rules(css)[-1]
                for icon_selector in ICON_GUARD_SELECTORS:
                    self.assertIn(icon_selector, selector)
                self.assertIn("direction: ltr !important", body)
                self.assertTrue(css.endswith(ICON_GUARD_CSS))

    def test_rtl_only_for_kurdish_and_arabic(self):
        self.assertIn(RTL_CSS, build_global_css("ckb"))
        self.assertIn(RTL_CSS, build_global_css("ar"))
        self.assertNotIn(RTL_CSS, build_global_css("en"))

    def test_rtl_font_rules_are_not_broad_and_use_vazirmatn(self):
        font_rules = [
            (selector, body)
            for selector, body in css_rules(RTL_CSS)
            if "font-family" in body
        ]
        self.assertTrue(font_rules)
        for selector, body in font_rules:
            self.assertIn("Vazirmatn", body)
            self.assertNotIn('[class*="st-"]', selector)
            self.assertNotRegex(selector, r"(^|,)\s*(\*|span)\s*(,|$)")

    def test_rtl_styles_remove_letter_spacing(self):
        rules = dict(css_rules(RTL_CSS))
        resets = [body for selector, body in rules.items() if ".stApp *" in selector]
        self.assertTrue(resets)
        self.assertIn("letter-spacing: normal !important", resets[0])
        for body in rules.values():
            self.assertNotRegex(body, r"letter-spacing:\s*-?\.?\d")

    def test_rtl_direction_covers_main_sidebar_and_menus(self):
        selectors = " ".join(
            selector for selector, body in css_rules(RTL_CSS) if "direction: rtl" in body
        )
        for target in ('[data-testid="stMain"]', 'section[data-testid="stSidebar"]', '[data-baseweb="popover"]'):
            self.assertIn(target, selectors)


if __name__ == "__main__":
    unittest.main()
