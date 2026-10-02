import ast
import re
import unittest
from pathlib import Path

from helai_ui import GLOBAL_CSS


APP_SOURCE = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
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


def sidebar_block():
    tree = ast.parse(APP_SOURCE)
    for node in tree.body:
        if not isinstance(node, ast.With):
            continue
        context = node.items[0].context_expr
        if ast.unparse(context) == "st.sidebar":
            return node
    raise AssertionError("app.py has no top-level `with st.sidebar:` block")


class HelAIIconTypographyTests(unittest.TestCase):
    def test_no_broad_streamlit_class_font_rule(self):
        for selector, body in css_rules(GLOBAL_CSS):
            if "font-family" not in body:
                continue
            self.assertNotIn('[class*="st-"]', selector)
            self.assertNotIn('[class*="css-"]', selector)
            self.assertNotRegex(selector, r"(^|,)\s*(\*|span)\s*(,|$)")

    def test_inter_font_is_scoped_with_zero_specificity(self):
        inter_rules = [
            selector
            for selector, body in css_rules(GLOBAL_CSS)
            if "font-family: Inter" in body
        ]
        self.assertTrue(inter_rules)
        for selector in inter_rules:
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
        self.assertGreater(guard, GLOBAL_CSS.index('.summary-panel[dir="rtl"]'))
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
        self.assertIn("color: white !important", rules[
            '.stButton > button[kind="primary"], .stFormSubmitButton > button'
        ])

    def test_label_colour_rule_is_scoped_to_buttons(self):
        label_rules = [
            selector
            for selector, body in css_rules(GLOBAL_CSS)
            if ":where(p, span)" in selector and "color: inherit" in body
        ]
        self.assertTrue(label_rules)
        for selector in label_rules:
            for part in re.split(r",(?![^(]*\))", selector):
                self.assertRegex(part.strip(), r"(\.stButton|\.stFormSubmitButton) > button")


class HelAISignOutTests(unittest.TestCase):
    def test_sign_out_is_last_direct_sidebar_element(self):
        last = sidebar_block().body[-1]
        self.assertIsInstance(last, ast.If)
        call = last.test
        self.assertIsInstance(call, ast.Call)
        self.assertEqual(ast.unparse(call.func), "st.button")
        self.assertEqual(ast.unparse(call.args[0]), "t('sidebar.sign_out')")
        keywords = {kw.arg: kw.value for kw in call.keywords}
        self.assertEqual(ast.literal_eval(keywords["key"]), "helai_sign_out")

    def test_sidebar_sections_render_in_order(self):
        sidebar_source = ast.unparse(sidebar_block())
        markers = (
            "language_switcher(",
            "sidebar-brand",
            "sidebar.account",
            "sidebar.workspace",
            "sidebar.sources",
            "sidebar.sign_out",
        )
        positions = [sidebar_source.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_sign_out_pinned_to_sidebar_bottom(self):
        rules = dict(css_rules(GLOBAL_CSS))
        self.assertIn("margin-top: auto", rules[".st-key-helai_sign_out"])
        pinned_parent = (
            '[data-testid="stSidebarUserContent"] '
            '[data-testid="stVerticalBlock"]:has(> .st-key-helai_sign_out)'
        )
        self.assertIn("min-height", rules[pinned_parent])

    def test_sign_out_has_visible_text_hover_and_focus_states(self):
        button = 'section[data-testid="stSidebar"] .st-key-helai_sign_out .stButton > button[kind]'
        rules = dict(css_rules(GLOBAL_CSS))
        self.assertIn("color: var(--text-secondary) !important", rules[button])
        self.assertIn("color: inherit !important", rules[f"{button} :where(p, span)"])
        hover = rules[f"{button}:hover"]
        self.assertIn("var(--surface-hover)", hover)
        self.assertIn("var(--danger)", hover)
        self.assertIn("var(--accent)", rules[f"{button}:focus-visible"])
        self.assertNotIn("logout_button", GLOBAL_CSS)


if __name__ == "__main__":
    unittest.main()
