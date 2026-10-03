import ast
import re
import unittest
from pathlib import Path

from helai_ui import BASE_CSS, GLOBAL_CSS, RTL_CSS, SUN_ICON, _SUN_SVG, build_global_css


HERE = Path(__file__).parent
APP_SOURCE = (HERE / "app.py").read_text(encoding="utf-8")
CONFIG = (HERE / ".streamlit" / "config.toml").read_text(encoding="utf-8")
ICON_GUARD_SELECTORS = (
    '[data-testid="stIconMaterial"]',
    '[class*="material-symbols"]',
    '[class*="material-icons"]',
)


def css_rules(css):
    """Return (selector, body) pairs for every flat rule in the stylesheet."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [
        (selector.strip(), body)
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
    ]


def desktop_rules(css):
    """Like dict(css_rules(css)), but a selector repeated in a media query
    keeps its first (desktop) body."""
    rules = {}
    for selector, body in css_rules(css):
        rules.setdefault(selector, body)
    return rules


def nav_block():
    tree = ast.parse(APP_SOURCE)
    for node in tree.body:
        if not isinstance(node, ast.With):
            continue
        if ast.unparse(node.items[0].context_expr) == "st.container(key='helai_nav')":
            return node
    raise AssertionError("app.py has no top-level `with st.container(key=\"helai_nav\"):` block")


class HelAIIconTypographyTests(unittest.TestCase):
    def test_no_broad_streamlit_class_font_rule(self):
        for selector, body in css_rules(GLOBAL_CSS):
            if "font-family" not in body:
                continue
            self.assertNotIn('[class*="st-"]', selector)
            self.assertNotIn('[class*="css-"]', selector)
            self.assertNotRegex(selector, r"(^|,)\s*(\*|span)\s*(,|$)")

    def test_base_font_is_scoped_with_zero_specificity(self):
        base_font_rules = [
            selector
            for selector, body in css_rules(GLOBAL_CSS)
            if "font-family: Inter" in body
        ]
        self.assertTrue(base_font_rules)
        for selector in base_font_rules:
            self.assertTrue(selector.startswith(":where("), selector)
            self.assertIn(".stApp", selector)

    def test_icon_guard_is_last_and_restores_ligatures(self):
        rules = css_rules(GLOBAL_CSS)
        selector, body = rules[-1]
        for icon_selector in ICON_GUARD_SELECTORS:
            self.assertIn(icon_selector, selector)
        self.assertIn('font-family: "Material Symbols Rounded" !important', body)
        self.assertIn("letter-spacing: normal !important", body)
        self.assertIn("text-transform: none !important", body)
        self.assertIn("direction: ltr !important", body)
        self.assertIn('font-feature-settings: "liga" 1 !important', body)

    def test_icon_guard_comes_after_rtl_typography(self):
        guard = GLOBAL_CSS.index('[data-testid="stIconMaterial"]')
        rtl_css = build_global_css("ckb")
        rtl_guard = rtl_css.index('[data-testid="stIconMaterial"]')
        self.assertGreater(rtl_guard, rtl_css.index("font-family: Vazirmatn"))
        self.assertGreater(guard, GLOBAL_CSS.index("font-family: Inter"))

    def test_reduced_motion_and_focus_states_kept(self):
        self.assertIn("prefers-reduced-motion: reduce", GLOBAL_CSS)
        self.assertIn(":focus-visible", GLOBAL_CSS)


class HelAIPrimaryButtonTests(unittest.TestCase):
    def test_primary_button_label_inherits_button_colour(self):
        rules = dict(css_rules(GLOBAL_CSS))
        selector = (
            '.stButton > button[kind="primary"] :where(p, span),\n'
            '.stFormSubmitButton > button :where(p, span)'
        )
        self.assertIn(selector, rules)
        self.assertIn("color: inherit !important", rules[selector])
        # Light outline: the saffron fill belongs to the navigation pill.
        body = rules['.stButton > button[kind="primary"], .stFormSubmitButton > button']
        self.assertIn("border: 1px solid var(--text-primary) !important", body)
        self.assertIn("background: transparent !important", body)
        self.assertIn("color: var(--text-primary) !important", body)

    def test_label_colour_rule_is_scoped_to_buttons(self):
        label_rules = [
            selector
            for selector, body in css_rules(GLOBAL_CSS)
            if ":where(p, span)" in selector and "color: inherit" in body
        ]
        self.assertTrue(label_rules)
        for selector in label_rules:
            for part in re.split(r",(?![^(]*\))", selector):
                self.assertRegex(
                    part.strip(),
                    r'(\.stButton|\.stFormSubmitButton) > button|\[data-testid="stButtonGroup"\] button',
                )


class HelAITopNavigationTests(unittest.TestCase):
    def test_app_has_no_sidebar(self):
        self.assertNotIn("st.sidebar", APP_SOURCE)
        self.assertNotIn("initial_sidebar_state", APP_SOURCE)

    def test_navigation_comes_before_the_page(self):
        self.assertLess(APP_SOURCE.index('st.container(key="helai_nav")'), APP_SOURCE.index("render_header("))
        self.assertLess(APP_SOURCE.index("render_header("), APP_SOURCE.index("render_hero("))

    def test_navigation_renders_in_order(self):
        source = ast.unparse(nav_block())
        markers = (
            "nav_brand_html()",
            "nav_links_html(lang)",
            "language_switcher('helai_lang_switch_header')",
            "nav_cta_html(",
            "t('sidebar.sign_out')",
        )
        positions = [source.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_sign_out_lives_in_the_navigation(self):
        buttons = [
            node
            for node in ast.walk(nav_block())
            if isinstance(node, ast.Call) and ast.unparse(node.func) == "st.button"
        ]
        self.assertEqual(len(buttons), 1)
        call = buttons[0]
        self.assertEqual(ast.unparse(call.args[0]), "t('sidebar.sign_out')")
        keywords = {kw.arg: kw.value for kw in call.keywords}
        self.assertEqual(ast.literal_eval(keywords["key"]), "helai_sign_out")
        self.assertEqual(APP_SOURCE.count("helai_sign_out"), 1)

    def test_sign_out_has_visible_text_hover_and_focus_states(self):
        button = ".st-key-helai_sign_out .stButton > button[kind]"
        rules = dict(css_rules(GLOBAL_CSS))
        self.assertIn("color: var(--text-muted) !important", rules[button])
        self.assertIn("min-height: 44px", rules[button])
        self.assertIn("color: inherit !important", rules[f"{button} :where(p, span)"])
        self.assertIn("var(--text-primary)", rules[f"{button}:hover"])
        self.assertIn("var(--focus-ring)", rules[f"{button}:focus-visible"])
        self.assertNotIn("logout_button", GLOBAL_CSS)

    def test_navigation_stays_on_one_line_until_phones(self):
        rules = desktop_rules(BASE_CSS)
        self.assertIn("flex-wrap: nowrap", rules['.st-key-helai_nav [data-testid="stHorizontalBlock"]'])
        phone = BASE_CSS[BASE_CSS.index("@media (max-width: 767.98px)"):]
        self.assertIn("flex-wrap: wrap !important", phone[: phone.index("\n}\n")])


class HelAIDesignTokenTests(unittest.TestCase):
    ROOT = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", BASE_CSS[: BASE_CSS.index("html {")]))

    def test_palette(self):
        expected = {
            "--bg-main": "#0E1014",
            "--surface-1": "#171A21",
            "--surface-2": "#1A1E26",
            "--surface-inset": "#12151A",
            "--border-strong": "#252A33",
            "--border-subtle": "#1F232B",
            "--text-primary": "#F3F1EC",
            "--text-secondary": "#B3B7C1",
            "--text-muted": "#A3A8B3",
            "--accent": "#F4B740",
            "--accent-text": "#16130B",
            "--amber": "#F4C76A",
            "--mint": "#5FD8A4",
            "--coral": "#F2896B",
        }
        for token, value in expected.items():
            with self.subTest(token=token):
                self.assertEqual(self.ROOT[token], value)

    def test_spacing_radius_and_width(self):
        self.assertEqual(self.ROOT["--u"], "6px")
        self.assertEqual(self.ROOT["--radius-control"], "24px")
        self.assertEqual(self.ROOT["--radius-pill"], "9999px")
        self.assertEqual(self.ROOT["--gap-section"], "120px")
        self.assertIn("max-width: 1280px", desktop_rules(BASE_CSS)[".block-container"])
        for width, gap in (("1100px", "96px"), ("767.98px", "60px")):
            block = BASE_CSS[BASE_CSS.index(f"@media (max-width: {width})"):]
            self.assertIn(f"--gap-section: {gap}", block[: block.index("\n}\n")])

    def test_saffron_fills_only_the_one_pill(self):
        allowed = (".nav-cta", "body:has(.auth-page-marker) .stFormSubmitButton")
        for selector, body in css_rules(BASE_CSS):
            if re.search(r"background:\s*var\(--accent(-hover)?\)", body):
                with self.subTest(selector=selector):
                    self.assertTrue(any(name in selector for name in allowed), selector)
                    self.assertIn("var(--accent-text)", body)

    def test_saffron_marks_match_numbers_labels_links_and_logo(self):
        rules = desktop_rules(BASE_CSS)
        for selector in (".opp-score-value", ".stat-value.accent", ".label.accent", ".opp-link", ".rail-link", "a"):
            with self.subTest(selector=selector):
                self.assertIn("var(--accent)", rules[selector])
        self.assertIn("#F4B740", _SUN_SVG)
        self.assertIn("brand-mark", SUN_ICON)

    def test_amber_only_for_closing_soon(self):
        for selector, body in css_rules(BASE_CSS):
            if "var(--amber)" in body:
                with self.subTest(selector=selector):
                    self.assertIn(".amber", selector)

    def test_nothing_is_boxed(self):
        for selector, body in css_rules(BASE_CSS):
            with self.subTest(selector=selector):
                self.assertNotRegex(body, r"box-shadow:(?!\s*none)")
                if re.search(r"\.(opp|rail-card|stat-strip|stat-cell|card|profile-callout|empty-state|sources)\b", selector):
                    self.assertNotRegex(body, r"(^|;)\s*(border|background)(-\w+)?:")

    def test_latin_type_scale(self):
        rules = desktop_rules(BASE_CSS)
        self.assertEqual(self.ROOT["--track-display"], "-0.04em")
        self.assertEqual(self.ROOT["--track-title"], "-1.68px")
        self.assertIn("letter-spacing: var(--track-display)", rules[".stApp .hero-headline"])
        for selector in (".section-title", ".opp-title"):
            self.assertIn("letter-spacing: var(--track-title)", rules[selector])
        self.assertIn("font-size: 42px", rules[".opp-title"])
        self.assertIn("font-size: 18px; font-weight: 200", rules[".stApp p"])
        label = rules[".label"]
        for part in ("font-size: 14px", "font-weight: 600", "letter-spacing: var(--track-label)", "text-transform: uppercase"):
            self.assertIn(part, label)
        self.assertEqual(self.ROOT["--track-label"], "0.35px")

    def test_hierarchy_comes_from_scale_not_weight(self):
        for selector, body in css_rules(BASE_CSS):
            for weight in re.findall(r"font-weight:\s*(\d+)", body):
                with self.subTest(selector=selector):
                    self.assertLessEqual(int(weight), 600)
        self.assertIn("font-weight: 400 !important", dict(css_rules(BASE_CSS))[".stApp :is(h1, h2, h3, h4, h5, h6)"])

    def test_kurdish_and_arabic_never_get_tracking(self):
        root = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", RTL_CSS[: RTL_CSS.index("}")]))
        for token in ("--track-display", "--track-title", "--track-label"):
            self.assertEqual(root[token], "normal")
        self.assertNotRegex(RTL_CSS, r"letter-spacing:\s*-")
        # Literal (non-token) tracking in the base sheet is only ever on Latin
        # brand text or reset by the RTL sheet's blanket rule.
        self.assertIn(".stApp, .stApp *, [data-baseweb=\"popover\"] * { letter-spacing: normal !important; }", RTL_CSS)

    def test_streamlit_theme_matches(self):
        theme = CONFIG[CONFIG.index("[theme]"): CONFIG.index("[client]")]
        for line in (
            'backgroundColor = "#0E1014"',
            'secondaryBackgroundColor = "#171A21"',
            'textColor = "#F3F1EC"',
            'linkColor = "#F4B740"',
            'primaryColor = "#F4B740"',
            'codeBackgroundColor = "#12151A"',
            'borderColor = "#252A33"',
            'baseRadius = "24px"',
            'buttonRadius = "24px"',
        ):
            self.assertIn(line, theme)
        self.assertIn("Inter", theme)
        self.assertNotIn("[theme.sidebar]", CONFIG)


if __name__ == "__main__":
    unittest.main()
