"""Reusable presentation helpers for the HelAI Streamlit interface."""

from __future__ import annotations

import base64
import html
import re
from datetime import date, datetime, timedelta, timezone

import streamlit as st

from helai_i18n import (
    ACTIVE_KEY,
    CHOICE_KEY,
    LANGUAGE_LABELS,
    LANGUAGES,
    active_language,
    count_phrase,
    format_date,
    format_number,
    format_percent,
    is_rtl,
    localize_digits,
    normalize_language,
    normalize_sorani_terms,
    t,
    t_value,
    translate_booster_label,
    translate_match_message,
)
from opportunity_rules import effective_status, has_document_requirements


BASE_CSS = r"""
<style>
/* Dark ground, warm white type. Nothing has a card, panel, border or
   shadow: whitespace separates everything. Saffron marks the one filled
   pill, the big match numbers, the logo, small section labels and inline
   links; amber marks closing-soon deadlines. Mint and coral stay as text
   colour where they carry meaning. Inputs and outline buttons keep a
   hairline, since a control needs a visible edge to be found. */
:root {
    --bg-main: #0E1014;
    --surface-1: #171A21;
    --surface-2: #1A1E26;
    --surface-inset: #12151A;
    --border-strong: #252A33;
    --border-subtle: #1F232B;
    --text-primary: #F3F1EC;
    --text-secondary: #B3B7C1;
    --text-muted: #A3A8B3;
    --accent: #F4B740;
    --accent-hover: #F7C45E;
    --accent-text: #16130B;
    --accent-soft: rgba(244, 183, 64, 0.12);
    --amber: #F4C76A;
    --mint: #5FD8A4;
    --coral: #F2896B;
    --focus-ring: #F4B740;
    --u: 6px;
    --gap-section: 120px;
    --radius-control: 24px;
    --radius-pill: 9999px;
    --font-ui: Inter, "Segoe UI", system-ui, sans-serif;
    --track-display: -0.04em;
    --track-title: -1.68px;
    --track-label: 0.35px;
}

html { scroll-behavior: smooth; scroll-padding-top: 24px; }
html, body, .stApp { background: var(--bg-main) !important; color: var(--text-primary); }

/* Zero-specificity typography: Streamlit's own component classes (including
   the Material Symbols icon spans) always win over this default. */
:where(.stApp, .stApp button, .stApp input, .stApp textarea, .stApp select) {
    font-family: Inter, "Segoe UI", system-ui, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }
a, button, summary, [role="button"], [role="tab"], label { touch-action: manipulation; }
a { color: var(--accent); text-underline-offset: 4px; }
a:hover { color: var(--text-primary); }
:where(a, button, input, textarea, select, summary, [role="button"], [role="tab"], [tabindex]):focus-visible {
    outline: 2px solid var(--focus-ring) !important;
    outline-offset: 3px !important;
}

/* No Streamlit chrome above the page: the top navigation is the page's own. */
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { max-width: 1280px; padding: calc(var(--u) * 5) calc(var(--u) * 6) calc(var(--u) * 16); overflow-x: clip; }
footer { visibility: hidden; }

.stApp p { color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.6; }
.stApp :is(h1, h2, h3, h4, h5, h6) { color: var(--text-primary); font-weight: 400 !important; }
.stApp strong, .stApp b { color: var(--text-primary); font-weight: 600; }
.label {
    color: var(--text-muted);
    font-size: 14px;
    font-weight: 600;
    letter-spacing: var(--track-label);
    line-height: 1.4;
    text-transform: uppercase;
}
.label.accent { color: var(--accent); }
.label.amber { color: var(--amber); }

/* Layout wrappers never draw a box. */
[data-testid="stForm"],
.stApp [data-testid="stVerticalBlock"] {
    border: 0 !important;
    border-radius: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
}
[data-testid="stForm"] { padding: 0 !important; }

/* Top navigation: logo, section links, language, the one saffron pill. */
.st-key-helai_nav { margin-bottom: calc(var(--u) * 10); }
/* Every item takes its own width; only the links stretch, so longer Kurdish
   and Arabic labels never push Sign out off the bar. */
.st-key-helai_nav [data-testid="stHorizontalBlock"] { align-items: center; flex-wrap: nowrap; gap: calc(var(--u) * 3); }
.st-key-helai_nav [data-testid="stColumn"] { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
.st-key-helai_nav [data-testid="stColumn"]:nth-child(2) { flex: 1 1 auto !important; }
.brand { display: flex; align-items: center; gap: calc(var(--u) * 2); color: var(--text-primary); font-size: 22px; font-weight: 400; letter-spacing: -0.5px; white-space: nowrap; text-decoration: none !important; }
.brand-mark { flex: 0 0 auto; display: block; }
.nav-links { display: flex; flex-wrap: wrap; justify-content: flex-end; column-gap: calc(var(--u) * 4); row-gap: 0; }
.nav-link {
    display: inline-flex; align-items: center; min-height: 44px;
    color: var(--text-muted) !important; font-size: 14px; font-weight: 400;
    text-decoration: none !important; white-space: nowrap; transition: color .16s ease;
}
.nav-link:hover { color: var(--text-primary) !important; }
.nav-cta {
    display: inline-flex; align-items: center; justify-content: center; min-height: 44px;
    padding: 0 calc(var(--u) * 4); border-radius: var(--radius-pill);
    background: var(--accent); color: var(--accent-text) !important;
    font-size: 15px; font-weight: 600; text-decoration: none !important; white-space: nowrap;
    transition: background .16s ease;
}
.nav-cta:hover { background: var(--accent-hover); color: var(--accent-text) !important; }
.st-key-helai_sign_out .stButton > button[kind] {
    min-height: 44px;
    padding-inline: calc(var(--u) * 2) !important;
    border: 0 !important;
    background: transparent !important;
    color: var(--text-muted) !important;
    box-shadow: none !important;
    font-size: 15px !important;
    font-weight: 400 !important;
    white-space: nowrap;
}
.st-key-helai_sign_out .stButton > button[kind] :where(p, span) {
    color: inherit !important;
    font-size: inherit !important;
    font-weight: inherit !important;
}
.st-key-helai_sign_out .stButton > button[kind]:hover { background: transparent !important; color: var(--text-primary) !important; }
.st-key-helai_sign_out .stButton > button[kind]:focus-visible { outline: 2px solid var(--focus-ring) !important; outline-offset: 2px !important; }

/* Authentication: headline left, form right, nothing boxed. */
body:has(.auth-page-marker) .block-container { padding-top: calc(var(--u) * 12); }
.auth-wordmark { margin-bottom: calc(var(--u) * 14); }
.auth-headline {
    max-width: 760px; margin: 0 0 calc(var(--u) * 4);
    color: var(--text-primary); font-size: clamp(52px, 5.4vw, 78px);
    font-weight: 400; line-height: 1; letter-spacing: var(--track-display);
}
.auth-headline .muted-line { color: var(--text-muted); }
.auth-sub { max-width: 560px; color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.6; }
.auth-preview { max-width: 640px; margin-top: calc(var(--u) * 12); }
.auth-preview-label { margin-bottom: calc(var(--u) * 3); }
.auth-panel-title { margin: calc(var(--u) * 6) 0 var(--u); color: var(--text-primary); font-size: 42px; font-weight: 400; line-height: 1.1; letter-spacing: var(--track-title); }
.auth-panel-copy { margin-bottom: calc(var(--u) * 5); color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.6; }
/* The sign-in page has no navigation bar, so its submit is the one pill. */
body:has(.auth-page-marker) .stFormSubmitButton > button {
    border-color: var(--accent) !important;
    border-radius: var(--radius-pill) !important;
    background: var(--accent) !important;
    color: var(--accent-text) !important;
}
body:has(.auth-page-marker) .stFormSubmitButton > button:hover { border-color: var(--accent-hover) !important; background: var(--accent-hover) !important; color: var(--accent-text) !important; }

/* Segmented controls (language, sign in / sign up) read as text tabs;
   filter pills are pills. */
[data-testid="stButtonGroup"] button {
    min-height: 44px;
    border: 0 !important;
    border-radius: var(--radius-pill) !important;
    background: transparent !important;
    color: var(--text-muted) !important;
    box-shadow: none !important;
    font-weight: 400 !important;
}
[data-testid="stButtonGroup"] button :where(p, span) { color: inherit !important; font-size: 15px !important; font-weight: inherit !important; }
[data-testid="stButtonGroup"] button:hover { color: var(--text-primary) !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"] { color: var(--text-primary) !important; font-weight: 600 !important; }
.st-key-helai_filter [data-testid="stButtonGroup"] button { padding-inline: calc(var(--u) * 3) !important; }
.st-key-helai_filter [data-testid="stButtonGroup"] button[aria-checked="true"] { background: var(--text-primary) !important; color: var(--bg-main) !important; }
.st-key-helai_filter [data-testid="stButtonGroup"] > div { flex-wrap: wrap !important; row-gap: var(--u); }

/* Greeting row */
.greeting { margin: 0; color: var(--text-primary); font-size: 28px; font-weight: 400; line-height: 1.25; letter-spacing: -0.5px; }
.greeting-sub { margin-top: var(--u); color: var(--text-muted); font-size: 14px; line-height: 1.5; }
.greeting-sub .sep { padding-inline: var(--u); }

/* Hero: one huge sentence, a quiet subline, four plain numbers. */
.hero { margin: calc(var(--u) * 14) 0 0; }
.stApp .hero-headline {
    max-width: 1100px; margin: 0;
    color: var(--text-muted); font-size: clamp(52px, 7.4vw, 104px);
    font-weight: 400; line-height: 1; letter-spacing: var(--track-display);
}
.hero-headline .count { color: var(--text-primary); }
.hero-sub { max-width: 760px; margin-top: calc(var(--u) * 5); color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.6; }
.stat-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: calc(var(--u) * 6); margin: calc(var(--u) * 12) 0 0; }
.stat-cell { min-width: 0; }
.stat-value { color: var(--text-primary); font-size: 64px; font-weight: 400; line-height: 1; letter-spacing: -0.03em; }
.stat-value.accent { color: var(--accent); }
.stat-label { margin-top: calc(var(--u) * 2); }

/* Sections, forms and inputs */
.section { margin: var(--gap-section) 0 calc(var(--u) * 6); scroll-margin-top: 24px; }
.section-eyebrow { margin-bottom: calc(var(--u) * 2); }
.section-title { margin: 0 0 calc(var(--u) * 2); color: var(--text-primary); font-size: 48px; line-height: 1.08; font-weight: 400; letter-spacing: var(--track-title); }
.section-copy { max-width: 720px; color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.6; }
.workspace-heading { display: flex; align-items: center; gap: calc(var(--u) * 2); margin-bottom: var(--u); color: var(--text-primary); font-size: 24px; font-weight: 400; }
.spark { color: var(--text-muted); }
.workspace-copy { margin-bottom: calc(var(--u) * 4); color: var(--text-secondary); font-size: 18px; font-weight: 200; }
.profile-group { margin: calc(var(--u) * 8) 0 calc(var(--u) * 3); }
.profile-group-title { color: var(--text-primary); font-size: 24px; font-weight: 400; line-height: 1.25; }
.profile-group-copy { margin-top: var(--u); color: var(--text-muted); font-size: 16px; font-weight: 200; line-height: 1.55; }
.profile-callout { display: flex; gap: calc(var(--u) * 2); max-width: 760px; margin-bottom: calc(var(--u) * 4); color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.6; }
.profile-callout strong { font-weight: 400; }
.card { margin-top: calc(var(--u) * 6); }
.card-number, .ai-tag { color: var(--text-muted); font-size: 14px; font-weight: 600; letter-spacing: var(--track-label); text-transform: uppercase; }
.card-title { margin: calc(var(--u) * 2) 0 var(--u); color: var(--text-primary); font-size: 42px; font-weight: 400; line-height: 1.1; letter-spacing: var(--track-title); }
.card-org { color: var(--text-secondary); font-size: 18px; font-weight: 200; }

label[data-testid="stWidgetLabel"] p {
    color: var(--text-muted) !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    letter-spacing: var(--track-label);
    text-transform: uppercase;
}
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div,
[data-baseweb="base-input"],
[data-baseweb="select"] > div {
    min-height: 48px;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-control) !important;
    background: transparent !important;
    box-shadow: none !important;
    transition: border-color .16s ease;
}
[data-testid="stTextInputRootElement"],
[data-testid="stTextAreaRootElement"],
[data-testid="stNumberInputContainer"],
[data-testid="stDateInputField"] {
    border-color: var(--border-strong) !important;
    border-radius: var(--radius-control) !important;
    background: transparent !important;
    overflow: hidden;
}
[data-testid="stNumberInputContainer"] button { background: transparent !important; }
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stTextAreaRootElement"]:focus-within,
[data-testid="stNumberInputContainer"]:focus-within { border-color: var(--text-primary) !important; }
input, textarea { color: var(--text-primary) !important; font-size: 16px !important; font-weight: 400 !important; }
input { padding-inline: calc(var(--u) * 3) !important; }
textarea { min-height: 180px; padding: calc(var(--u) * 3) !important; }
input::placeholder, textarea::placeholder { color: var(--text-muted) !important; opacity: 1; }
/* Streamlit fills chips and checkboxes with the saffron accent: chips become
   outlines, and ticks stay dark on the fill. */
[data-testid="stMultiSelectTagsContainer"] [data-tag] {
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-pill) !important;
    background: transparent !important;
    color: var(--text-primary) !important;
}
[data-testid="stMultiSelectTagsContainer"] [data-tag] button { color: var(--text-muted) !important; }
[data-testid="stCheckbox"] svg polyline { stroke: var(--accent-text) !important; }
[data-testid="stCheckbox"] { min-height: 44px; padding: var(--u) 0; }
[data-testid="stCheckbox"] p { color: var(--text-secondary); font-size: 16px; font-weight: 400; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--text-muted) !important; font-size: 14px !important; font-weight: 400 !important; }

:where(button, input, textarea, select):disabled,
[aria-disabled="true"] { cursor: not-allowed !important; opacity: .5 !important; transform: none !important; box-shadow: none !important; }

/* Buttons: light outline pills. The saffron fill belongs to one pill only. */
.stButton > button, .stFormSubmitButton > button, .stLinkButton > a {
    min-height: 48px;
    padding-inline: calc(var(--u) * 4) !important;
    border-radius: var(--radius-control) !important;
    box-shadow: none !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    transition: background .16s ease, border-color .16s ease, color .16s ease !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button {
    border: 1px solid var(--text-primary) !important;
    background: transparent !important;
    color: var(--text-primary) !important;
}
/* Label <p> and icon follow the button colour instead of `.stApp p`. */
.stButton > button[kind="primary"] :where(p, span),
.stFormSubmitButton > button :where(p, span) {
    color: inherit !important;
}
.stButton > button[kind="primary"] p,
.stFormSubmitButton > button p { font-size: 15px; font-weight: 600; }
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover { background: var(--text-primary) !important; color: var(--bg-main) !important; }
.stButton > button[kind="secondary"], .stLinkButton > a {
    border: 1px solid var(--border-strong) !important;
    background: transparent !important;
    color: var(--text-primary) !important;
}
.stButton > button[kind="secondary"] p, .stLinkButton > a p { color: var(--text-primary); font-size: 15px; font-weight: 600; }
.stButton > button[kind="secondary"]:hover, .stLinkButton > a:hover { border-color: var(--text-primary) !important; }

/* Opportunity rows: match score on one side, everything else as text. */
.feed { display: grid; gap: calc(var(--u) * 16); margin-top: calc(var(--u) * 8); }
.opp { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: calc(var(--u) * 8); align-items: start; }
.opp-score-value {
    margin-top: var(--u);
    color: var(--accent); font-size: clamp(64px, 6.4vw, 92px);
    font-weight: 400; line-height: .95; letter-spacing: var(--track-display);
}
.opp-labels { display: flex; flex-wrap: wrap; column-gap: calc(var(--u) * 4); row-gap: var(--u); }
.opp-title {
    margin: calc(var(--u) * 3) 0 0;
    color: var(--text-primary); font-size: 42px; font-weight: 400;
    line-height: 1.1; letter-spacing: var(--track-title); overflow-wrap: anywhere;
}
.opp-meta { margin-top: calc(var(--u) * 2); color: var(--text-muted); font-size: 16px; font-weight: 400; }
.opp-summary { max-width: 760px; margin-top: calc(var(--u) * 4); color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.6; }
.opp-summary-note { margin-bottom: var(--u); color: var(--text-muted); font-size: 14px; font-weight: 400; }
.opp-facts { display: flex; flex-wrap: wrap; column-gap: calc(var(--u) * 10); row-gap: calc(var(--u) * 3); margin: calc(var(--u) * 6) 0 0; }
.stApp .opp-facts, .stApp .opp-facts > div, .stApp .opp-facts dt { margin-inline: 0; padding: 0; }
.stApp .opp-facts dd { margin: var(--u) 0 0; color: var(--text-primary); font-size: 18px; font-weight: 400; }
.opp-lists { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: calc(var(--u) * 8); max-width: 900px; margin-top: calc(var(--u) * 6); }
.list-title { margin-bottom: calc(var(--u) * 2); font-size: 14px; font-weight: 600; letter-spacing: var(--track-label); text-transform: uppercase; }
.mint { color: var(--mint) !important; }
.coral { color: var(--coral) !important; }
.amber { color: var(--amber) !important; }
.muted { color: var(--text-secondary) !important; }
.stApp .opp-list { margin: 0; padding: 0; list-style: none; }
.stApp .opp-list li { margin: 0 0 var(--u); padding: 0; color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.5; overflow-wrap: anywhere; }
.opp-empty { color: var(--text-muted); font-size: 18px; font-weight: 200; }
.opp-link {
    display: inline-flex; align-items: center; min-height: 44px; margin-top: calc(var(--u) * 5);
    color: var(--accent) !important; font-size: 16px; font-weight: 600; text-decoration: none !important;
}
.opp-link:hover { text-decoration: underline !important; }
.opp-notify { display: inline-flex; align-items: center; min-height: 44px; margin-top: calc(var(--u) * 2); color: var(--text-muted); font-size: 16px; }
.opp.compact { opacity: .62; }
.opp.compact .opp-title { font-size: 28px; letter-spacing: -0.5px; }
.opp.compact .opp-score-value { font-size: 28px; color: var(--text-muted); letter-spacing: normal; }
.opp.preview { grid-template-columns: 150px minmax(0, 1fr); gap: calc(var(--u) * 5); }
.opp.preview .opp-score-value { font-size: 64px; }
.opp.preview .opp-title { font-size: 28px; letter-spacing: -0.5px; }

/* Right rail and Booster */
.rail-card { margin-bottom: calc(var(--u) * 12); }
.rail-card.alerts { margin-top: var(--gap-section); }
.rail-title { display: flex; align-items: baseline; justify-content: space-between; gap: calc(var(--u) * 2); margin-bottom: calc(var(--u) * 3); color: var(--text-primary); font-size: 28px; font-weight: 400; line-height: 1.2; letter-spacing: -0.5px; }
.boost-row { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: calc(var(--u) * 3); align-items: baseline; padding: calc(var(--u) * 3) 0; }
.boost-badge { color: var(--text-primary); font-size: 42px; font-weight: 400; line-height: 1; letter-spacing: var(--track-title); }
.boost-action { color: var(--text-primary); font-size: 20px; font-weight: 400; line-height: 1.35; }
.boost-effect { margin-top: var(--u); color: var(--text-muted); font-size: 16px; font-weight: 200; }
.onoff { font-size: 14px; font-weight: 600; letter-spacing: var(--track-label); text-transform: uppercase; }
.onoff.on { color: var(--text-primary); }
.onoff.off { color: var(--text-muted); }
.rail-copy { color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.6; }
.rail-link { display: inline-flex; align-items: center; min-height: 44px; color: var(--accent) !important; font-size: 16px; font-weight: 600; text-decoration: none !important; }
.rail-link:hover { text-decoration: underline !important; }
.dl-row { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: calc(var(--u) * 3); align-items: start; padding: calc(var(--u) * 3) 0; }
.dl-days { color: var(--text-primary); font-size: 42px; font-weight: 400; line-height: 1; letter-spacing: var(--track-title); }
.dl-days.amber { color: var(--amber); }
.dl-unit { margin-top: 4px; color: var(--text-muted); font-size: 14px; }
.dl-title { color: var(--text-primary); font-size: 16px; font-weight: 400; line-height: 1.4; overflow-wrap: anywhere; }
.dl-date { margin-top: 4px; color: var(--text-muted); font-size: 14px; }

/* Sources, at the foot of the page */
.sources { margin-top: var(--gap-section); }
.source-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: calc(var(--u) * 4) calc(var(--u) * 6); margin-top: calc(var(--u) * 3); }
.source-name { color: var(--text-primary); font-size: 16px; font-weight: 400; }
.source-meta { margin-top: 4px; color: var(--text-muted); font-size: 14px; line-height: 1.45; }
.source-meta.coral { color: var(--coral); }
.sources-total { margin-top: calc(var(--u) * 4); color: var(--text-muted); font-size: 14px; }

/* Native metrics, alerts, expanders, menus */
div[data-testid="stMetric"] { padding: 0; border: 0; background: transparent; }
div[data-testid="stMetricLabel"] p { color: var(--text-muted) !important; font-size: 14px !important; font-weight: 600 !important; letter-spacing: var(--track-label); text-transform: uppercase; }
div[data-testid="stMetricValue"] { color: var(--text-primary) !important; font-size: 28px !important; font-weight: 400 !important; }
details { border: 0 !important; background: transparent !important; }
details summary { min-height: 44px; padding-inline: 0 !important; color: var(--text-muted); font-weight: 400 !important; cursor: pointer; }
[data-testid="stAlertContainer"] { padding: 0 !important; border: 0 !important; background: transparent !important; }
[data-testid="stAlert"] { border: 0 !important; background: transparent !important; box-shadow: none !important; }
[data-testid="stAlert"] p { margin: 0; color: var(--text-primary) !important; font-size: 18px; font-weight: 400; line-height: 1.5; }
[data-testid="stAlertContentError"] p { color: var(--coral) !important; }
[data-baseweb="popover"], [role="listbox"], [role="tooltip"] { border-color: var(--border-subtle) !important; background: var(--surface-2) !important; color: var(--text-primary) !important; }
[role="option"] { min-height: 44px; }
[role="option"]:hover, [role="option"][aria-selected="true"] { background: var(--accent-soft) !important; }
hr { margin: calc(var(--u) * 10) 0; border: 0; height: 0; }

.empty-state { max-width: 720px; margin: calc(var(--u) * 6) 0; }
.empty-state-title { color: var(--text-primary); font-size: 28px; font-weight: 400; line-height: 1.25; letter-spacing: -0.5px; }
.empty-state-copy { margin-top: calc(var(--u) * 2); color: var(--text-secondary); font-size: 18px; font-weight: 200; line-height: 1.6; }
.footer { display: flex; justify-content: space-between; gap: calc(var(--u) * 3); margin-top: calc(var(--u) * 16); color: var(--text-muted); font-size: 14px; font-weight: 600; letter-spacing: var(--track-label); }

/* Tablet: section links leave the bar; numbers go two by two. */
@media (max-width: 1100px) {
    :root { --gap-section: 96px; }
    .block-container { padding-inline: calc(var(--u) * 4); }
    .st-key-helai_nav [data-testid="stColumn"]:nth-child(2) { display: none; }
    .stat-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .opp { grid-template-columns: 150px minmax(0, 1fr); gap: calc(var(--u) * 5); }
}
/* Phones: one column, score above each row, the bar wraps to two lines. */
@media (max-width: 767.98px) {
    :root { --gap-section: 60px; }
    .block-container { padding: calc(var(--u) * 3) 16px calc(var(--u) * 12); }
    input, textarea, select { font-size: 16px !important; }
    .st-key-helai_nav { margin-bottom: calc(var(--u) * 6); }
    .st-key-helai_nav [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; row-gap: var(--u); column-gap: calc(var(--u) * 2); }
    .st-key-helai_nav [data-testid="stColumn"] { width: auto !important; min-width: 0 !important; flex: 0 0 auto !important; }
    .st-key-helai_nav [data-testid="stColumn"]:nth-child(1) { flex: 1 1 auto !important; }
    .st-key-helai_nav [data-testid="stColumn"]:nth-child(3) { order: 5; flex: 1 1 100% !important; }
    .nav-cta { padding: 0 calc(var(--u) * 3); font-size: 14px; }
    body:has(.auth-page-marker) .block-container { padding-top: calc(var(--u) * 4); }
    .auth-wordmark { margin-bottom: calc(var(--u) * 6); }
    .auth-headline { font-size: 48px; letter-spacing: var(--track-title); }
    .hero { margin-top: calc(var(--u) * 8); }
    .hero-headline { font-size: 48px; line-height: 1.05; letter-spacing: var(--track-title); }
    .stat-strip { gap: calc(var(--u) * 5) calc(var(--u) * 3); margin-top: calc(var(--u) * 8); }
    .stat-value { font-size: 48px; }
    .section-title, .opp-title, .card-title, .auth-panel-title { font-size: 34px; letter-spacing: -1.2px; }
    .feed { gap: calc(var(--u) * 12); }
    .opp, .opp.preview { grid-template-columns: 1fr; gap: calc(var(--u) * 2); }
    .opp-score-value { font-size: 64px; }
    .opp-lists { grid-template-columns: 1fr; gap: calc(var(--u) * 4); }
    .footer { flex-direction: column; }
    .greeting { font-size: 24px; }
}
@media (max-width: 480px) {
    /* Stat strip stays 2x2 from the 1100px rule. */
    .stat-value { font-size: 42px; letter-spacing: var(--track-title); }
    .opp-facts { column-gap: calc(var(--u) * 6); }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; }
}
"""


# Kurdish Sorani and Arabic. Inserted between BASE_CSS and ICON_GUARD_CSS so the
# icon guard still wins for Material Symbols. Same weights as the Latin design,
# but never any tracking: negative letter-spacing breaks Arabic-script joins.
RTL_CSS = r"""
:root {
    --font-ui: Vazirmatn, Tahoma, "Segoe UI", sans-serif;
    --track-display: normal;
    --track-title: normal;
    --track-label: normal;
}
.stApp :is(h1, h2, h3, h4, h5, h6, p, li, label, div, a, button, summary, input, textarea),
[data-baseweb="popover"] :is(li, div) {
    font-family: Vazirmatn, Tahoma, "Segoe UI", sans-serif;
}
/* Arabic-script text is never letter-spaced. */
.stApp, .stApp *, [data-baseweb="popover"] * { letter-spacing: normal !important; }

[data-testid="stMain"],
[data-baseweb="popover"],
[role="tooltip"] {
    direction: rtl;
    text-align: right;
}
[data-testid="stMain"] :is(input, textarea) { direction: rtl; text-align: right; }
/* Emails and passwords are Latin: keep them left-to-right. */
.st-key-login_email_v2 input,
.st-key-signup_email_v2 input,
[data-testid="stTextInput"] input[type="password"] { direction: ltr; text-align: left; }
[data-testid="stMain"] [dir="auto"] { text-align: right; }
.latin { direction: ltr; unicode-bidi: isolate; }
.opp-summary [dir="ltr"] { text-align: left; }
/* Vazirmatn sits taller than Inter; give the large lines room. */
.hero-headline, .auth-headline { line-height: 1.25; }
.section-title, .opp-title, .card-title, .auth-panel-title { line-height: 1.35; }
.opp-score-value, .stat-value, .dl-days, .boost-badge { line-height: 1.15; }
"""


FONT_IMPORTS = {
    "en": (
        "<style>@import url('https://fonts.googleapis.com/css2?"
        "family=Inter:wght@200;400;600&display=swap');</style>"
    ),
    "rtl": (
        "<style>@import url('https://fonts.googleapis.com/css2?"
        "family=Vazirmatn:wght@200;400;600&display=swap');</style>"
    ),
}


ICON_GUARD_CSS = r"""
/* Icon guard: keep last. Material Symbols render via font ligatures, so any
   inherited font-family, letter-spacing, text-transform or RTL direction turns
   them back into literal names such as "visibility". */
[data-testid="stIconMaterial"],
[class*="material-symbols"],
[class*="material-icons"] {
    font-family: "Material Symbols Rounded" !important;
    font-style: normal !important;
    font-weight: normal !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    font-feature-settings: "liga" 1 !important;
    -webkit-font-smoothing: antialiased;
}
</style>
"""


GLOBAL_CSS = BASE_CSS + ICON_GUARD_CSS

_SUN_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24">'
    '<circle cx="12" cy="12" r="4.2" fill="#F4B740"/>'
    '<g stroke="#F4B740" stroke-width="2" stroke-linecap="round">'
    '<line x1="12" y1="1.8" x2="12" y2="4.4"/><line x1="12" y1="19.6" x2="12" y2="22.2"/>'
    '<line x1="1.8" y1="12" x2="4.4" y2="12"/><line x1="19.6" y1="12" x2="22.2" y2="12"/>'
    '<line x1="4.8" y1="4.8" x2="6.6" y2="6.6"/><line x1="17.4" y1="17.4" x2="19.2" y2="19.2"/>'
    '<line x1="4.8" y1="19.2" x2="6.6" y2="17.4"/><line x1="17.4" y1="6.6" x2="19.2" y2="4.8"/>'
    "</g></svg>"
)
# st.html sanitizes inline <svg>, so the logo mark ships as an image data URI.
SUN_ICON = (
    '<img class="brand-mark" width="28" height="28" alt="" '
    'src="data:image/svg+xml;base64,' + base64.b64encode(_SUN_SVG.encode()).decode() + '">'
)

# Kurdistan Region / Iraq time (UTC+3, no DST); fixed so it works without tzdata.
IRAQ_TIME = timezone(timedelta(hours=3))
CLOSING_SOON_DAYS = 14
FULLY_FUNDED = re.compile(r"fully[\s-]funded|full scholarship|full funding|fully financed", re.IGNORECASE)
MAX_LIST_ITEMS = 4


def build_global_css(lang: str) -> str:
    """Base styles, then RTL overrides for ckb/ar, then the icon guard last."""
    if is_rtl(lang):
        return BASE_CSS + RTL_CSS + ICON_GUARD_CSS
    return GLOBAL_CSS


def inject_global_styles(lang: str | None = None) -> None:
    lang = lang or active_language()
    st.markdown(FONT_IMPORTS["rtl" if is_rtl(lang) else "en"], unsafe_allow_html=True)
    st.markdown(build_global_css(lang), unsafe_allow_html=True)


def language_switcher(key: str) -> None:
    """کوردی · English · العربية; an explicit choice wins for this session."""
    st.session_state[key] = active_language()

    def apply_choice() -> None:
        chosen = normalize_language(st.session_state.get(key))
        if chosen:
            st.session_state[CHOICE_KEY] = chosen
            st.session_state[ACTIVE_KEY] = chosen
            st.query_params["lang"] = chosen

    st.segmented_control(
        t("lang.label"),
        LANGUAGES,
        format_func=LANGUAGE_LABELS.get,
        key=key,
        on_change=apply_choice,
        required=True,
        label_visibility="collapsed",
    )


def latin(text: object) -> str:
    """Escaped Latin-script name (source, brand) isolated inside RTL text."""
    return f'<bdi class="latin">{html.escape(str(text))}</bdi>'


def t_html(key: str, lang: str | None = None, **parts: str) -> str:
    """Escaped translation with trusted HTML fragments placed in its slots."""
    text = html.escape(t(key, lang=lang))
    for name, fragment in parts.items():
        text = text.replace("{" + name + "}", fragment)
    return text


def status_label(status: str, lang: str | None = None) -> str:
    slug = status.lower() if status in {"Open", "Closed", "Upcoming"} else "review"
    return t(f"status.{slug}", lang=lang)


def greeting_key(now: datetime | None = None) -> str:
    hour = (now or datetime.now(IRAQ_TIME)).hour
    if 5 <= hour < 12:
        return "header.greeting_morning"
    if 12 <= hour < 17:
        return "header.greeting_afternoon"
    return "header.greeting_evening"


def section_header(number: str, eyebrow: str, title: str, description: str, anchor: str) -> None:
    st.html(
        f"""
        <section class="section" id="{html.escape(anchor)}">
            <div class="section-eyebrow label accent">{html.escape(number)}&ensp;{html.escape(eyebrow)}</div>
            <h2 class="section-title">{html.escape(title)}</h2>
            <div class="section-copy">{html.escape(description)}</div>
        </section>
        """
    )


def profile_group(title: str, description: str = "") -> None:
    copy = (
        f'<div class="profile-group-copy">{html.escape(description)}</div>'
        if description
        else ""
    )
    st.html(
        f"""
        <div class="profile-group">
            <div class="profile-group-title">{html.escape(title)}</div>
            {copy}
        </div>
        """
    )


def telegram_steps(connection: dict | None, lang: str | None = None) -> list[tuple[str, str]]:
    """The Telegram section in reading order: status, instruction, button."""
    if connection:
        connected_on = format_date(
            str(connection.get("connected_at") or "")[:10],
            lang,
        )
        return [
            ("status", t("telegram.connected_since", lang=lang, date=connected_on)),
            ("instruction", t("telegram.connected_copy", lang=lang)),
            ("button", t("telegram.disconnect_button", lang=lang)),
        ]

    return [
        ("status", t("telegram.not_connected", lang=lang)),
        ("instruction", t("telegram.instruction", lang=lang)),
        ("button", t("telegram.connect_button", lang=lang)),
    ]


def render_empty_state(title: str, description: str) -> None:
    st.html(
        f"""
        <div class="empty-state" role="status">
            <div class="empty-state-title">{html.escape(title)}</div>
            <div class="empty-state-copy">{html.escape(description)}</div>
        </div>
        """
    )


def format_deadline(value: object, lang: str | None = None) -> str:
    return format_date(value, lang)


def card_status(opportunity: dict, today: object = None) -> tuple[str, str]:
    """Badge label and CSS slug, using the same status rules as matching."""
    status = effective_status(opportunity, today=today)
    slug = status.lower() if status in {"Open", "Closed", "Upcoming"} else "review"
    return status, slug


def result_sort_key(item: tuple[dict, dict], today: object = None) -> tuple:
    """Open (after deadline) first, then eligible, score and readiness."""
    opportunity, result = item
    return (
        effective_status(opportunity, today=today) == "Open",
        result["eligible"],
        result["score"],
        result["readiness"],
    )


def result_kpis(results: list[tuple[dict, dict]], today: object = None) -> dict:
    """Map KPI counts over (opportunity, result) pairs, using effective status."""
    open_pairs = [
        (opportunity, result)
        for opportunity, result in results
        if effective_status(opportunity, today=today) == "Open"
    ]
    open_results = [result for _, result in open_pairs]
    return {
        "open": len(open_results),
        "eligible": sum(1 for result in open_results if result["eligible"]),
        # 100% readiness with no tracked documents is not "ready".
        "ready": sum(
            1
            for opportunity, result in open_pairs
            if result["eligible"]
            and result["readiness"] == 100
            and has_document_requirements(opportunity)
        ),
        "best_score": max((result["score"] for result in open_results), default=0),
    }


NO_DOCUMENT_REQUIREMENTS = t("card.no_document_requirements", lang="en")


def readiness_display(opportunity: dict, result: dict, lang: str | None = None) -> tuple[str, str]:
    """Readiness label and tone; a 100% with nothing to check is not shown."""
    if not has_document_requirements(opportunity):
        return t("card.no_document_requirements", lang=lang), "neutral"
    readiness = int(result.get("readiness") or 0)
    return format_percent(readiness, lang), "success" if readiness == 100 else "warning"


def days_until(deadline: object, today: date | None = None) -> int | None:
    try:
        due = date.fromisoformat(str(deadline or "").strip()[:10])
    except ValueError:
        return None
    return (due - (today or datetime.now(IRAQ_TIME).date())).days


def deadline_info(opportunity: dict, lang: str | None = None, today: date | None = None) -> tuple[str, str, bool]:
    """(deadline text, days-left text, closing soon)."""
    deadline = opportunity.get("deadline")
    if not deadline:
        return t("email.no_deadline", lang=lang), "", False
    days = days_until(deadline, today)
    if days is None:
        return str(deadline), "", False
    if days < 0:
        left = ""
    elif days == 0:
        left = t("email.closes_today", lang=lang)
    elif days == 1:
        left = t("email.one_day_left", lang=lang)
    else:
        left = t("email.days_left", lang=lang, days=format_number(days, lang))
    return format_date(deadline, lang), left, 0 <= days <= CLOSING_SOON_DAYS


def is_closing_soon(opportunity: dict, today: date | None = None) -> bool:
    if effective_status(opportunity, today=today) != "Open":
        return False
    days = days_until(opportunity.get("deadline"), today)
    return days is not None and 0 <= days <= CLOSING_SOON_DAYS


def is_fully_funded(opportunity: dict) -> bool:
    """Heuristic: no structured field exists, so look for the phrase."""
    text = " ".join(
        str(opportunity.get(field) or "")
        for field in ("title", "summary_en", "notes")
    )
    return bool(FULLY_FUNDED.search(text))


FEED_PAGE_SIZE = 10
FEED_LIMIT_KEY = "helai_feed_limit"
FEED_VIEW_KEY = "helai_feed_view"


def feed_limit(state, view: tuple) -> int:
    """How many tickets to show; a new filter or search starts again at one page."""
    if state.get(FEED_VIEW_KEY) != view:
        state[FEED_VIEW_KEY] = view
        state[FEED_LIMIT_KEY] = FEED_PAGE_SIZE
    return state.get(FEED_LIMIT_KEY, FEED_PAGE_SIZE)


def show_more(state) -> None:
    state[FEED_LIMIT_KEY] = state.get(FEED_LIMIT_KEY, FEED_PAGE_SIZE) + FEED_PAGE_SIZE


def feed_page(items: list, limit: int) -> tuple[list, int, int]:
    """(items to show in their existing order, how many remain, size of the next page)."""
    shown = items[:limit]
    remaining = len(items) - len(shown)
    return shown, remaining, min(FEED_PAGE_SIZE, remaining)


def filter_results(results: list[tuple[dict, dict]], mode: str, query: str = "", today: date | None = None) -> list:
    query = query.strip().lower()
    filtered = []
    for opportunity, result in results:
        if query:
            haystack = " ".join(
                str(opportunity.get(field) or "")
                for field in ("title", "organization", "source", "source_name", "summary_en", "summary_ku")
            ).lower()
            if query not in haystack:
                continue
        if mode == "eligible" and not (result["eligible"] and effective_status(opportunity, today=today) == "Open"):
            continue
        if mode == "closing" and not is_closing_soon(opportunity, today):
            continue
        if mode == "funded" and not is_fully_funded(opportunity):
            continue
        filtered.append((opportunity, result))
    return filtered


NAV_SECTIONS = (
    ("ai-import", "nav.ai_import"),
    ("cloud-profile", "nav.cloud_profile"),
    ("opportunity-booster", "nav.opportunity_booster"),
    ("opportunity-map", "nav.opportunity_map"),
)


def nav_brand_html() -> str:
    return f'<div class="brand">{SUN_ICON}{latin("HelAI")}</div>'


def nav_links_html(lang: str) -> str:
    """Section links, in page order."""
    links = "".join(
        f'<a class="nav-link" href="#{anchor}">{html.escape(t(key, lang=lang))}</a>'
        for anchor, key in NAV_SECTIONS
    )
    return f'<nav class="nav-links" aria-label="{html.escape(t("sidebar.workspace", lang=lang))}">{links}</nav>'


def nav_cta_html(has_profile: bool, lang: str) -> str:
    """The page's one filled pill: matches once there is a profile to match."""
    if has_profile:
        return f'<a class="nav-cta" href="#opportunity-map">{html.escape(t("nav.cta_matches", lang=lang))}</a>'
    return f'<a class="nav-cta" href="#cloud-profile">{html.escape(t("nav.cta_profile", lang=lang))}</a>'


def render_header(name: str, email: str, completion: int, lang: str, search_key: str) -> str:
    """Greeting with the account line, and search; returns the search text."""
    greeting_col, search_col = st.columns([1.5, 1], vertical_alignment="center")
    with greeting_col:
        first_name = (name or "").split()[0] if (name or "").split() else name
        details = [
            html.escape(format_date(datetime.now(IRAQ_TIME).date(), lang)),
            latin(email) if email else "",
            html.escape(t("sidebar.profile_complete", lang=lang, pct=format_percent(completion, lang))),
        ]
        account = '<span class="sep" aria-hidden="true">·</span>'.join(part for part in details if part)
        st.html(
            f'<h1 class="greeting">{t_html(greeting_key(), lang, name=f"<bdi>{html.escape(first_name)}</bdi>")}</h1>'
            f'<div class="greeting-sub">{account}</div>'
        )
    with search_col:
        query = st.text_input(
            t("header.search", lang=lang),
            placeholder=t("header.search_placeholder", lang=lang),
            key=search_key,
            label_visibility="collapsed",
            icon=":material/search:",
        )
    return query


def render_hero(kpis: dict, total_open: int, source_names: list[str], lang: str) -> None:
    template, phrase = count_phrase(kpis["eligible"], lang)
    headline = html.escape(template).replace(
        "{count}", f'<span class="count">{html.escape(phrase)}</span>'
    )
    sources = " · ".join(latin(name) for name in source_names)
    subline = t_html("hero.subline", lang, total=html.escape(format_number(total_open, lang)), sources=sources)
    cells = (
        (t("kpi.open", lang=lang), format_number(kpis["open"], lang), ""),
        (t("kpi.eligible", lang=lang), format_number(kpis["eligible"], lang), ""),
        (t("kpi.ready", lang=lang), format_number(kpis["ready"], lang), ""),
        (t("kpi.best", lang=lang), format_percent(kpis["best_score"], lang), " accent"),
    )
    strip = "".join(
        f'<div class="stat-cell"><div class="stat-value{tone}">{html.escape(value)}</div>'
        f'<div class="stat-label label">{html.escape(label)}</div></div>'
        for label, value, tone in cells
    )
    st.html(
        f'<section class="hero">'
        f'<h2 class="hero-headline">{headline}</h2>'
        f'<div class="hero-sub">{subline}</div>'
        f'<div class="stat-strip">{strip}</div></section>'
    )


def _list_html(items: list[str], tone: str, empty: str, lang: str | None = None) -> str:
    if not items:
        return f'<div class="opp-empty">{html.escape(empty)}</div>'
    rows = "".join(
        f'<li>{html.escape(translate_match_message(item, lang))}</li>'
        for item in items[:MAX_LIST_ITEMS]
    )
    return f'<ul class="opp-list {tone}-list">{rows}</ul>'


def _fact_html(label: str, value: str, tone: str = "") -> str:
    tone_class = f' class="{tone}"' if tone else ""
    return f'<div><dt class="label">{html.escape(label)}</dt><dd{tone_class}>{html.escape(value)}</dd></div>'


def _labels_html(parts: list[str]) -> str:
    return f'<div class="opp-labels">{"".join(parts)}</div>'


def ticket_html(opportunity: dict, result: dict, lang: str | None = None, today: date | None = None) -> str:
    """One opportunity as a row: the match score on one side, the rest as text."""
    lang = lang or active_language()
    title = str(opportunity.get("title") or t("card.untitled", lang=lang))
    organization = str(opportunity.get("organization") or t("card.no_organization", lang=lang))
    source_name = str(opportunity.get("source") or opportunity.get("source_name") or t("card.unknown_source", lang=lang))
    source_url = str(opportunity.get("source_url") or "")
    opportunity_type = str(opportunity.get("type") or "")
    type_label = t_value("type", opportunity_type, lang) if opportunity_type else t("card.opportunity", lang=lang)
    status, status_slug = card_status(opportunity, today)
    eligible = bool(result.get("eligible"))
    record_kind = str(opportunity.get("record_kind") or "").strip().lower()
    needs_review = record_kind in {"roundup", "informational"}
    deadline, days_left, soon = deadline_info(opportunity, lang, today)
    location = str(opportunity.get("location") or "")
    meta = " · ".join(
        part
        for part in (
            f'<span dir="auto">{html.escape(organization)}</span>',
            f'<span dir="auto">{html.escape(t_value("location", location, lang))}</span>' if location else "",
        )
        if part
    )
    deadline_text = f"{deadline} · {days_left}" if days_left else deadline
    labels = [
        f'<span class="label">{latin(source_name)}</span>',
        f'<span class="label">{html.escape(type_label)}</span>',
        f'<span class="label status-{status_slug}">{html.escape(status_label(status, lang))}</span>',
        f'<span class="label{" amber" if soon and status == "Open" else ""}">{html.escape(deadline_text)}</span>',
    ]
    if opportunity.get("is_ai_imported"):
        labels.append(f'<span class="label">{html.escape(t("card.ai_imported", lang=lang))}</span>')

    if status != "Open":
        return (
            f'<article class="opp compact">'
            f'<div class="opp-score" aria-hidden="true"></div>'
            f'<div class="opp-body">{_labels_html(labels)}'
            f'<h3 class="opp-title" dir="auto">{html.escape(title)}</h3>'
            f'<div class="opp-meta">{meta}</div>'
            f'<span class="opp-notify" role="button" aria-disabled="true" '
            f'title="{html.escape(t("card.coming_soon", lang=lang))}">{html.escape(t("card.notify_next", lang=lang))}</span>'
            f"</div></article>"
        )

    summary_ku = normalize_sorani_terms(opportunity.get("summary_ku")).strip()
    summary_en = str(opportunity.get("summary_en") or opportunity.get("notes") or "").strip()
    if lang == "ckb" and summary_ku:
        summary = f'<div class="opp-summary">{html.escape(summary_ku)}</div>'
    elif summary_en:
        note = (
            f'<div class="opp-summary-note">{html.escape(t(f"card.summary_missing_{lang}", lang=lang))}</div>'
            if lang in {"ckb", "ar"}
            else ""
        )
        summary = f'<div class="opp-summary">{note}<div dir="ltr">{html.escape(summary_en)}</div></div>'
    else:
        summary = ""

    if eligible:
        eligibility, tone = t("card.eligible", lang=lang), "mint"
    elif needs_review:
        eligibility, tone = t("card.review", lang=lang), "muted"
    else:
        eligibility, tone = t("card.not_eligible", lang=lang), "coral"
    readiness, _ = readiness_display(opportunity, result, lang)
    facts = (
        f'<dl class="opp-facts">'
        f'{_fact_html(t("field.eligibility", lang=lang), eligibility, tone)}'
        f'{_fact_html(t("field.readiness", lang=lang), readiness)}'
        f"</dl>"
    )

    # Reasons and gaps come from matcher.py in English; translated for display.
    missing = list(result.get("eligibility_gaps") or []) + list(result.get("readiness_gaps") or [])
    lists = (
        f'<div class="opp-lists">'
        f'<div><div class="list-title mint">{html.escape(t("card.why_it_fits", lang=lang))}</div>'
        f'{_list_html(list(result.get("reasons") or []), "mint", t("card.why_empty", lang=lang), lang)}</div>'
        f'<div><div class="list-title coral">{html.escape(t("card.still_missing", lang=lang))}</div>'
        f'{_list_html(missing, "coral", t("email.nothing_missing", lang=lang), lang)}</div>'
        f"</div>"
    )
    link = (
        f'<a class="opp-link" href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener">'
        f'{html.escape(t("card.view", lang=lang))}</a>'
        if source_url
        else ""
    )
    return (
        f'<article class="opp">'
        f'<div class="opp-score"><div class="label">{html.escape(t("field.match", lang=lang))}</div>'
        f'<div class="opp-score-value">{html.escape(format_percent(int(result.get("score") or 0), lang))}</div></div>'
        f'<div class="opp-body">{_labels_html(labels)}'
        f'<h3 class="opp-title" dir="auto">{html.escape(title)}</h3>'
        f'<div class="opp-meta">{meta}</div>{summary}{facts}{lists}{link}</div>'
        f"</article>"
    )


def render_opportunity_card(
    opportunity: dict,
    result: dict,
    index: int,
    lang: str | None = None,
) -> None:
    st.html(ticket_html(opportunity, result, lang))


def render_booster_card(improvements: list, lang: str) -> None:
    """Section 03 body; its section header supplies the title and anchor."""
    rows = "".join(
        f'<div class="boost-row">'
        f'<span class="boost-badge" dir="ltr">+{html.escape(format_number(data["unlocked"] or data["improved"], lang))}</span>'
        f'<div><div class="boost-action">{html.escape(translate_booster_label(label, lang))}</div>'
        f'<div class="boost-effect">{html.escape(t("rail.booster_effect", lang=lang, unlocked=format_number(data["unlocked"], lang), improved=format_number(data["improved"], lang)))}</div></div>'
        f"</div>"
        for label, data in improvements[:5]
    ) or f'<div class="rail-copy">{html.escape(t("booster.all_covered", lang=lang))}</div>'
    st.html(
        f'<section class="booster">{rows}</section>'
    )


def render_alerts_card(enabled: bool, lang: str) -> None:
    state = "on" if enabled else "off"
    st.html(
        f'<section class="rail-card alerts"><div class="rail-title">{html.escape(t("rail.alerts_title", lang=lang))}'
        f'<span class="onoff {state}">{html.escape(t(f"rail.alerts_{state}", lang=lang))}</span></div>'
        f'<div class="rail-copy">{html.escape(t(f"rail.alerts_copy_{state}", lang=lang))}</div>'
        f'<a class="rail-link" href="#cloud-profile">{html.escape(t("email.manage_alerts", lang=lang))}</a></section>'
    )


def deadlines_html(results: list[tuple[dict, dict]], lang: str, today: date | None = None) -> str:
    """Next deadlines among eligible, open matches only."""
    upcoming = []
    for opportunity, result in results:
        if not result.get("eligible") or effective_status(opportunity, today=today) != "Open":
            continue
        days = days_until(opportunity.get("deadline"), today)
        if days is not None and days >= 0:
            upcoming.append((days, opportunity))
    upcoming.sort(key=lambda item: item[0])
    rows = "".join(
        f'<div class="dl-row"><div><div class="dl-days{" amber" if days <= CLOSING_SOON_DAYS else ""}">{html.escape(format_number(days, lang))}</div>'
        f'<div class="dl-unit">{html.escape(t("rail.days_unit", lang=lang))}</div></div>'
        f'<div><div class="dl-title" dir="auto">{html.escape(str(opportunity.get("title") or ""))}</div>'
        f'<div class="dl-date">{html.escape(format_date(opportunity.get("deadline"), lang))}</div></div></div>'
        for days, opportunity in upcoming[:5]
    ) or f'<div class="rail-copy">{html.escape(t("rail.deadlines_empty", lang=lang))}</div>'
    return (
        f'<section class="rail-card"><div class="rail-title">{html.escape(t("rail.deadlines_title", lang=lang))}</div>{rows}</section>'
    )


def render_deadlines_rail(results: list[tuple[dict, dict]], lang: str, today: date | None = None) -> None:
    st.html(deadlines_html(results, lang, today))


def sources_html(sources: list[tuple[str, str, bool]], loaded: int, lang: str) -> str:
    """Each source with its last run, then how many opportunities are loaded.

    `sources` holds (name, run detail, failed) rows.
    """
    rows = "".join(
        f'<div><div class="source-name">{latin(name)}</div>'
        f'<div class="source-meta{" coral" if failed else ""}">{html.escape(detail)}</div></div>'
        for name, detail, failed in sources
    )
    return (
        f'<section class="sources"><div class="label accent">{html.escape(t("sidebar.sources", lang=lang))}</div>'
        f'<div class="source-list">{rows}</div>'
        f'<div class="sources-total">{html.escape(t("sidebar.opportunities_loaded", lang=lang, count=format_number(loaded, lang)))}</div>'
        f"</section>"
    )


PREVIEW_SCORE = 87  # Fictional example on the sign-in page, labelled as such.
PREVIEW_DAYS_LEFT = 30


def preview_ticket_html(lang: str, today: date | None = None) -> str:
    """Sign-in preview: a clearly fictional example, never a real opportunity."""
    today = today or datetime.now(IRAQ_TIME).date()
    example = {
        "deadline": (today + timedelta(days=PREVIEW_DAYS_LEFT)).isoformat(),
    }
    deadline, days_left, soon = deadline_info(example, lang, today)
    deadline_text = f"{deadline} · {days_left}" if days_left else deadline
    labels = [
        f'<span class="label">{html.escape(t_value("type", "Scholarships", lang))}</span>',
        f'<span class="label">{html.escape(status_label("Open", lang))}</span>',
        f'<span class="label{" amber" if soon else ""}">{html.escape(deadline_text)}</span>',
    ]
    return (
        f'<article class="opp preview" aria-label="{html.escape(t("signin.preview", lang=lang))}">'
        f'<div class="opp-score"><div class="label">{html.escape(t("field.match", lang=lang))}</div>'
        f'<div class="opp-score-value">{html.escape(format_percent(PREVIEW_SCORE, lang))}</div></div>'
        f'<div class="opp-body">{_labels_html(labels)}'
        f'<h3 class="opp-title">{html.escape(t("signin.example_title", lang=lang))}</h3>'
        f'<div class="opp-meta">{html.escape(t("signin.example_org", lang=lang))}</div>'
        f'<dl class="opp-facts">{_fact_html(t("field.eligibility", lang=lang), t("card.eligible", lang=lang), "mint")}</dl>'
        f"</div></article>"
    )


def sign_in_intro_html(lang: str, today: date | None = None) -> str:
    preview_html = (
        f'<div class="auth-preview"><div class="label accent auth-preview-label">{html.escape(t("signin.preview", lang=lang))}</div>'
        f"{preview_ticket_html(lang, today)}</div>"
    )
    return (
        f'<section class="auth-intro">'
        f'<div class="auth-wordmark brand">{SUN_ICON}{latin("HelAI")}</div>'
        f'<h1 class="auth-headline">{html.escape(t("signin.headline_1", lang=lang))} '
        f'<span class="muted-line">{html.escape(t("signin.headline_2", lang=lang))}</span></h1>'
        f'<div class="auth-sub">{html.escape(t("signin.subline", lang=lang))}</div>'
        f"{preview_html}</section>"
    )


def profile_completion(profile: dict) -> int:
    fields = (
        "full_name", "date_of_birth", "nationality", "country_of_residence", "city",
        "education", "field_of_study", "grade", "languages", "skills", "interests",
        "opportunity_types",
    )
    filled = sum(1 for field in fields if (profile or {}).get(field))
    return round(100 * filled / len(fields))


def localized_index(value: str, lang: str | None = None) -> str:
    return localize_digits(value, lang)
