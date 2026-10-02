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
:root {
    --bg-main: #0E1014;
    --bg-sidebar: #0B0D10;
    --surface-1: #171A21;
    --surface-2: #1A1E26;
    --surface-inset: #12151A;
    --surface-hover: #1F232B;
    --surface-input: #12151A;
    --border-subtle: #1F232B;
    --border-strong: #252A33;
    --text-primary: #F3F1EC;
    --text-secondary: #B3B7C1;
    --text-muted: #A3A8B3;
    --accent: #F4B740;
    --accent-hover: #F7C45E;
    --accent-text: #16130B;
    --accent-soft: rgba(244, 183, 64, 0.12);
    --success: #5FD8A4;
    --success-text: #7BE3B6;
    --success-soft: rgba(95, 216, 164, 0.12);
    --danger: #F2896B;
    --danger-text: #F6A88E;
    --danger-soft: rgba(242, 137, 107, 0.12);
    --warning: #F4C76A;
    --warning-soft: rgba(244, 199, 106, 0.12);
    --focus-ring: #F4B740;
    --radius-card: 22px;
    --radius-panel: 16px;
    --radius-inset: 14px;
    --radius-button: 12px;
    --font-ui: Geist, "Segoe UI", system-ui, sans-serif;
    --font-display: "Bricolage Grotesque", Geist, "Segoe UI", sans-serif;
}

html { scroll-behavior: smooth; scroll-padding-top: 24px; }
html, body, .stApp { background: var(--bg-main) !important; color: var(--text-primary); }

/* Zero-specificity typography: Streamlit's own component classes (including
   the Material Symbols icon spans) always win over this default. */
:where(.stApp, .stApp button, .stApp input, .stApp textarea, .stApp select) {
    font-family: Geist, "Segoe UI", system-ui, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }
a, button, summary, [role="button"], [role="tab"], label { touch-action: manipulation; }
a { color: var(--accent); text-underline-offset: 3px; }
a:hover { color: var(--accent-hover); }
:where(a, button, input, textarea, select, summary, [role="button"], [role="tab"], [tabindex]):focus-visible {
    outline: 2px solid var(--focus-ring) !important;
    outline-offset: 3px !important;
}

.block-container { max-width: 1320px; padding: 1.6rem 2.4rem 5rem; overflow-x: clip; }
header[data-testid="stHeader"] { background: transparent !important; }
footer { visibility: hidden; }
.stApp p { color: var(--text-secondary); font-size: 0.95rem; line-height: 1.65; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--text-primary); font-family: var(--font-display); }
.display { font-family: var(--font-display); }
.accent { color: var(--accent); }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-inline-end: 1px solid var(--border-subtle);
    box-shadow: none;
}
section[data-testid="stSidebar"] > div { padding-top: 1rem; }
section[data-testid="stSidebar"] p { font-size: 0.82rem; line-height: 1.45; }
.sidebar-brand { display: flex; align-items: center; gap: 10px; padding: 4px 2px 18px; }
.brand-sun { flex: 0 0 auto; }
.brand-name { color: var(--text-primary); font-family: var(--font-display); font-size: 1.3rem; font-weight: 700; }
.brand-subtitle { color: var(--text-muted); font-size: .74rem; margin-top: 1px; }
.sidebar-label { margin: 18px 2px 8px; color: var(--text-muted); font-size: .72rem; font-weight: 600; }

.account-card { padding: 14px; border: 1px solid var(--border-subtle); border-radius: var(--radius-panel); background: var(--surface-inset); }
.account-row { display: flex; align-items: center; gap: 11px; }
.account-avatar {
    display: grid; place-items: center; flex: 0 0 38px; width: 38px; height: 38px;
    border-radius: 50%; background: var(--accent-soft); color: var(--accent);
    font-size: .78rem; font-weight: 700;
}
.account-name, .source-name { color: var(--text-primary); font-size: .84rem; font-weight: 600; }
.account-email { color: var(--text-muted); font-size: .72rem; overflow-wrap: anywhere; }
.account-status { margin-top: 12px; color: var(--text-secondary); font-size: .72rem; }
.progress-track { height: 6px; margin-top: 6px; border-radius: 999px; background: var(--border-strong); overflow: hidden; }
.progress-fill { height: 100%; border-radius: 999px; background: var(--accent); }

.side-nav { display: grid; gap: 2px; }
.side-nav-row {
    display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 8px 10px;
    border-radius: var(--radius-button); color: var(--text-secondary) !important;
    font-size: .86rem; text-decoration: none !important; transition: background .16s ease, color .16s ease;
}
.side-nav-row:hover { background: var(--surface-hover); color: var(--text-primary) !important; }
.side-nav-number { min-width: 20px; color: var(--text-muted); font-size: .72rem; font-variant-numeric: tabular-nums; }

.source-list { display: grid; gap: 2px; }
.source-row { display: grid; grid-template-columns: 8px minmax(0, 1fr); gap: 10px; align-items: start; padding: 8px 4px; }
.source-dot { width: 8px; height: 8px; margin-top: 6px; border-radius: 50%; background: var(--success); }
.source-dot.danger { background: var(--danger); }
.source-meta { color: var(--text-muted); font-size: .72rem; line-height: 1.4; }

/* Sign out: last sidebar element, pinned to the bottom by a flexible spacer. */
[data-testid="stSidebarUserContent"]:has(.st-key-helai_sign_out) { padding-bottom: 24px; }
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"]:has(> .st-key-helai_sign_out) {
    min-height: calc(100vh - 120px);
    min-height: calc(100dvh - 120px);
}
.st-key-helai_sign_out {
    margin-top: auto;
    padding-top: 16px;
    border-top: 1px solid var(--border-subtle);
}
section[data-testid="stSidebar"] .st-key-helai_sign_out .stButton > button[kind] {
    width: 100%;
    min-height: 44px;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-button) !important;
    background: transparent !important;
    color: var(--text-secondary) !important;
    box-shadow: none !important;
    font-size: .84rem !important;
    font-weight: 600 !important;
    transform: none !important;
}
section[data-testid="stSidebar"] .st-key-helai_sign_out .stButton > button[kind] :where(p, span) {
    color: inherit !important;
    -webkit-text-fill-color: currentColor;
    opacity: 1 !important;
    visibility: visible !important;
}
section[data-testid="stSidebar"] .st-key-helai_sign_out .stButton > button[kind]:hover {
    border-color: var(--danger-soft) !important;
    background: var(--surface-hover) !important;
    color: var(--danger) !important;
}
section[data-testid="stSidebar"] .st-key-helai_sign_out .stButton > button[kind]:focus-visible {
    outline: 2px solid var(--accent) !important;
    outline-offset: 2px !important;
}

/* Authentication */
body:has(.auth-page-marker) section[data-testid="stSidebar"],
body:has(.auth-page-marker) [data-testid="collapsedControl"] { display: none !important; }
body:has(.auth-page-marker) .block-container { max-width: 1240px; padding-top: 4rem; }
body:has(.auth-page-marker) [data-testid="stColumn"]:last-child > div {
    padding: 28px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-card);
    background: var(--bg-sidebar);
}
.auth-wordmark { display: flex; align-items: center; gap: 10px; margin-bottom: 56px; color: var(--text-primary); font-family: var(--font-display); font-size: 1.35rem; font-weight: 700; }
.auth-headline { max-width: 620px; margin: 0 0 18px; color: var(--text-primary); font-family: var(--font-display); font-size: clamp(2.4rem, 5vw, 4.2rem); line-height: 1.04; font-weight: 700; }
.auth-sub { max-width: 540px; color: var(--text-secondary); font-size: 1rem; line-height: 1.75; }
.auth-preview { max-width: 520px; margin-top: 36px; }
.auth-preview-label { margin-bottom: 8px; color: var(--text-muted); font-size: .74rem; }
.auth-panel-title { margin: 18px 0 6px; color: var(--text-primary); font-family: var(--font-display); font-size: 1.6rem; font-weight: 700; }
.auth-panel-copy { margin-bottom: 18px; color: var(--text-secondary); font-size: .9rem; }

/* Segmented controls and pills */
[data-testid="stButtonGroup"] button {
    min-height: 44px;
    border-radius: var(--radius-button) !important;
    border-color: var(--border-strong) !important;
    background: var(--surface-inset) !important;
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
}
[data-testid="stButtonGroup"] button:hover { color: var(--text-primary) !important; border-color: var(--text-muted) !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: var(--accent-text) !important;
}
[data-testid="stButtonGroup"] button[aria-checked="true"] :where(p, span) { color: var(--accent-text) !important; }
.st-key-helai_filter [data-testid="stButtonGroup"] button { border-radius: 999px !important; padding-inline: 16px !important; }
.st-key-helai_filter [data-testid="stButtonGroup"] > div { flex-wrap: wrap !important; row-gap: 8px; }

/* Header */
.greeting { margin: 0; color: var(--text-primary); font-family: var(--font-display); font-size: 1.55rem; font-weight: 700; line-height: 1.3; }
.greeting-sub { margin-top: 2px; color: var(--text-muted); font-size: .84rem; }

/* Hero and stat strip */
.hero { margin: 26px 0 22px; }
.hero-headline { max-width: 900px; margin: 0; color: var(--text-primary); font-family: var(--font-display); font-size: clamp(2.1rem, 4.2vw, 3.6rem); line-height: 1.1; font-weight: 700; }
.hero-sub { max-width: 760px; margin-top: 14px; color: var(--text-secondary); font-size: 1rem; line-height: 1.7; }
.stat-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 22px 0 8px; border: 1px solid var(--border-strong); border-radius: var(--radius-panel); background: var(--surface-1); overflow: hidden; }
.stat-cell { min-width: 0; padding: 16px 18px; }
.stat-cell + .stat-cell { border-inline-start: 1px solid var(--border-strong); }
.stat-value { color: var(--text-primary); font-family: var(--font-display); font-size: 1.9rem; line-height: 1.1; font-weight: 700; font-variant-numeric: tabular-nums; }
.stat-value.accent { color: var(--accent); }
.stat-label { margin-top: 4px; color: var(--text-muted); font-size: .8rem; }

/* Sections, forms and inputs */
.section { margin: 56px 0 18px; scroll-margin-top: 24px; }
.section-heading-row { display: grid; grid-template-columns: 42px minmax(0,1fr); gap: 14px; align-items: start; }
.section-number { display: grid; place-items: center; width: 36px; height: 36px; border: 1px solid var(--border-strong); border-radius: var(--radius-button); color: var(--accent); background: var(--surface-inset); font-size: .76rem; font-weight: 700; }
.section-eyebrow { color: var(--accent); font-size: .78rem; font-weight: 600; }
.section-title { margin: 4px 0 6px; color: var(--text-primary); font-family: var(--font-display); font-size: clamp(1.5rem, 2.6vw, 2rem); line-height: 1.2; font-weight: 700; }
.section-copy { max-width: 690px; color: var(--text-secondary); font-size: .92rem; line-height: 1.65; }
.workspace-heading { display: flex; align-items: center; gap: 9px; margin-bottom: 5px; color: var(--text-primary); font-size: 1rem; font-weight: 650; }
.spark { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 8px; color: var(--accent); background: var(--accent-soft); }
.workspace-copy { margin-bottom: 16px; color: var(--text-secondary); font-size: .86rem; }
.profile-group { margin: 6px 0 16px; padding-bottom: 9px; border-bottom: 1px solid var(--border-subtle); }
.profile-group-title { color: var(--text-primary); font-size: .9rem; font-weight: 650; }
.profile-group-copy { margin-top: 3px; color: var(--text-muted); font-size: .76rem; }
.profile-callout { display: flex; gap: 12px; margin-bottom: 20px; padding: 14px 16px; border: 1px solid var(--border-strong); border-radius: var(--radius-panel); background: var(--surface-inset); color: var(--text-secondary); font-size: .84rem; line-height: 1.55; }
.card { padding: 22px; border: 1px solid var(--border-strong); border-radius: var(--radius-card); background: var(--surface-1); }
.card-number, .ai-tag { color: var(--text-muted); font-size: .74rem; }
.card-title { margin: 8px 0 4px; color: var(--text-primary); font-family: var(--font-display); font-size: 1.3rem; font-weight: 700; }
.card-org { color: var(--text-secondary); font-size: .88rem; }

div[data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"] {
    padding: 22px;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-card) !important;
    background: var(--surface-1);
}
label[data-testid="stWidgetLabel"] p { color: var(--text-secondary) !important; font-size: .82rem !important; font-weight: 600 !important; }
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div,
[data-baseweb="base-input"],
[data-baseweb="select"] > div {
    min-height: 44px;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-button) !important;
    background: var(--surface-input) !important;
    box-shadow: none !important;
    transition: border-color .16s ease;
}
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important; }
input, textarea { color: var(--text-primary) !important; font-size: .92rem !important; }
input::placeholder, textarea::placeholder { color: var(--text-muted) !important; opacity: 1; }
textarea { min-height: 180px; }
span[data-baseweb="tag"] { border: 1px solid var(--border-strong) !important; border-radius: 999px !important; background: var(--accent-soft) !important; color: var(--text-primary) !important; }
[data-testid="stCheckbox"] { min-height: 44px; padding: 7px 9px; border-radius: var(--radius-button); }
[data-testid="stCheckbox"]:hover { background: var(--surface-hover); }

:where(button, input, textarea, select):disabled,
[aria-disabled="true"] { cursor: not-allowed !important; opacity: .52 !important; transform: none !important; box-shadow: none !important; }

/* Buttons */
.stButton > button, .stFormSubmitButton > button, .stLinkButton > a {
    min-height: 44px;
    border-radius: var(--radius-button) !important;
    font-size: .88rem !important;
    font-weight: 650 !important;
    transition: background .16s ease, border-color .16s ease !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button {
    border: 1px solid var(--accent) !important;
    background: var(--accent) !important;
    color: #16130B !important;
    box-shadow: none;
}
/* Label <p> and icon follow the button colour instead of `.stApp p`. */
.stButton > button[kind="primary"] :where(p, span),
.stFormSubmitButton > button :where(p, span) {
    color: inherit !important;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover { background: var(--accent-hover) !important; border-color: var(--accent-hover) !important; }
.stButton > button[kind="secondary"], .stLinkButton > a { border: 1px solid var(--border-strong) !important; background: transparent !important; color: var(--text-primary) !important; box-shadow: none; }
.stButton > button[kind="secondary"]:hover, .stLinkButton > a:hover { background: var(--surface-hover) !important; }

/* Ticket cards */
.feed { display: grid; gap: 16px; }
.ticket {
    position: relative;
    display: flex;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-card);
    background: var(--surface-1);
    overflow: hidden;
}
.ticket-main { flex: 1 1 auto; min-width: 0; padding: 22px 24px; }
.ticket-perf { position: relative; flex: 0 0 0; border-inline-start: 2px dashed var(--border-strong); }
.ticket-perf::before, .ticket-perf::after {
    content: "";
    position: absolute;
    inset-inline-start: -13px;
    width: 24px;
    height: 24px;
    border: 1px solid var(--border-strong);
    border-radius: 50%;
    background: var(--bg-main);
}
.ticket-perf::before { top: -13px; }
.ticket-perf::after { bottom: -13px; }
.ticket-stub { flex: 0 0 248px; display: flex; flex-direction: column; gap: 12px; padding: 22px 22px 20px; background: var(--surface-2); }
.pill-row { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px; }
.pill {
    display: inline-flex; align-items: center; gap: 6px; min-height: 28px; padding: 4px 11px;
    border: 1px solid var(--border-strong); border-radius: 999px; color: var(--text-secondary);
    font-size: .76rem; font-weight: 600; white-space: nowrap;
}
.pill.open { color: var(--success-text); border-color: rgba(95,216,164,.35); background: var(--success-soft); }
.pill.closed { color: var(--danger-text); border-color: rgba(242,137,107,.35); background: var(--danger-soft); }
.pill.upcoming, .pill.review { color: var(--warning); border-color: rgba(244,199,106,.35); background: var(--warning-soft); }
.ticket-title { margin: 0; color: var(--text-primary); font-family: var(--font-display); font-size: clamp(1.15rem, 1.9vw, 1.42rem); line-height: 1.3; font-weight: 700; overflow-wrap: anywhere; }
.ticket-meta { margin-top: 6px; color: var(--text-muted); font-size: .84rem; }
.ticket-summary { margin-top: 14px; padding: 13px 15px; border: 1px solid var(--border-subtle); border-radius: var(--radius-inset); background: var(--surface-inset); color: var(--text-secondary); font-size: .88rem; line-height: 1.75; }
.ticket-summary-note { margin-bottom: 6px; color: var(--text-muted); font-size: .76rem; }
.ticket-lists { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 16px; }
.list-title { margin-bottom: 6px; font-size: .8rem; font-weight: 700; }
.list-title.mint { color: var(--success-text); }
.list-title.coral { color: var(--danger-text); }
.ticket-list { margin: 0; padding: 0; list-style: none; }
.ticket-list li { position: relative; margin: 5px 0; padding-inline-start: 14px; color: var(--text-secondary); font-size: .84rem; line-height: 1.5; overflow-wrap: anywhere; }
.ticket-list li::before { content: ""; position: absolute; inset-inline-start: 0; top: .6em; width: 5px; height: 5px; border-radius: 50%; background: var(--text-muted); }
.ticket-list.mint li::before { background: var(--success); }
.ticket-list.coral li::before { background: var(--danger); }
.ticket-empty { color: var(--text-muted); font-size: .84rem; }
.stub-label { color: var(--text-muted); font-size: .76rem; }
.stub-score { color: var(--accent); font-family: var(--font-display); font-size: 3.6rem; line-height: 1; font-weight: 700; font-variant-numeric: tabular-nums; }
.meter { display: grid; grid-template-columns: repeat(10, minmax(0, 1fr)); gap: 3px; margin-top: 6px; }
.meter span { height: 8px; border-radius: 3px; background: var(--border-strong); }
.meter span.on { background: var(--accent); }
.stub-value { margin-top: 3px; color: var(--text-primary); font-size: .9rem; font-weight: 650; }
.stub-value.mint { color: var(--success-text); }
.stub-value.coral { color: var(--danger-text); }
.stub-value.amber { color: var(--warning); }
.stub-days { margin-top: 2px; color: var(--text-secondary); font-size: .78rem; }
.stub-days.amber { color: var(--warning); }
.btn-saffron, .btn-outline {
    display: flex; align-items: center; justify-content: center; min-height: 44px; margin-top: auto;
    padding: 10px 14px; border-radius: var(--radius-button); font-size: .9rem; font-weight: 700;
    text-align: center; text-decoration: none !important;
}
.btn-saffron { background: var(--accent); color: var(--accent-text) !important; }
.btn-saffron:hover { background: var(--accent-hover); color: var(--accent-text) !important; }
.btn-outline { border: 1px solid var(--border-strong); background: transparent; color: var(--text-secondary) !important; cursor: not-allowed; }
.ticket.compact { opacity: .78; }
.ticket.compact .ticket-main { padding: 16px 20px; }
.ticket.compact .ticket-title { font-size: 1.02rem; }
.ticket.compact .ticket-stub { flex-basis: 248px; justify-content: center; padding: 14px 18px; }

/* Right rail */
.rail-card { margin-bottom: 16px; padding: 20px; border: 1px solid var(--border-strong); border-radius: var(--radius-card); background: var(--surface-1); }
.rail-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; color: var(--text-primary); font-family: var(--font-display); font-size: 1.05rem; font-weight: 700; }
.boost-row { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px; align-items: start; padding: 11px 0; border-top: 1px solid var(--border-subtle); }
.boost-row:first-of-type { border-top: 0; }
.boost-badge { display: grid; place-items: center; min-width: 44px; min-height: 30px; padding: 2px 8px; border-radius: 999px; background: var(--success-soft); color: var(--success-text); font-size: .86rem; font-weight: 700; }
.boost-action { color: var(--text-primary); font-size: .88rem; font-weight: 600; line-height: 1.4; }
.boost-effect { margin-top: 2px; color: var(--text-muted); font-size: .76rem; }
.onoff { padding: 3px 12px; border-radius: 999px; font-size: .76rem; font-weight: 700; }
.onoff.on { background: var(--success-soft); color: var(--success-text); }
.onoff.off { background: var(--danger-soft); color: var(--danger-text); }
.rail-copy { color: var(--text-secondary); font-size: .86rem; line-height: 1.6; }
.rail-link { display: inline-flex; align-items: center; min-height: 44px; color: var(--accent) !important; font-size: .86rem; font-weight: 650; text-decoration: none !important; }
.dl-row { display: grid; grid-template-columns: 58px minmax(0, 1fr); gap: 12px; align-items: center; padding: 10px 0; border-top: 1px solid var(--border-subtle); }
.dl-row:first-of-type { border-top: 0; }
.dl-days { color: var(--accent); font-family: var(--font-display); font-size: 1.9rem; line-height: 1; font-weight: 700; text-align: center; }
.dl-days.amber { color: var(--warning); }
.dl-unit { color: var(--text-muted); font-size: .7rem; text-align: center; }
.dl-title { color: var(--text-primary); font-size: .86rem; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
.dl-date { margin-top: 2px; color: var(--text-muted); font-size: .76rem; }

/* Native metrics, progress, alerts, menus */
div[data-testid="stMetric"] { min-height: 92px; padding: 14px 15px; border: 1px solid var(--border-strong); border-radius: var(--radius-panel); background: var(--surface-inset); }
div[data-testid="stMetricLabel"] p { color: var(--text-muted) !important; font-size: .76rem !important; }
div[data-testid="stMetricValue"] { color: var(--text-primary) !important; font-size: 1.25rem !important; font-weight: 700 !important; }
details { border: 1px solid var(--border-strong) !important; border-radius: var(--radius-panel) !important; background: var(--surface-inset) !important; }
details summary { min-height: 44px; color: var(--text-secondary); font-weight: 600 !important; cursor: pointer; }
[data-testid="stAlert"] { border: 1px solid var(--border-strong) !important; border-radius: var(--radius-panel) !important; box-shadow: none !important; }
[data-testid="stAlert"] p { margin: 0; color: inherit !important; font-size: .86rem; line-height: 1.5; }
[data-baseweb="popover"], [role="listbox"], [role="tooltip"] { border-color: var(--border-strong) !important; background: var(--surface-2) !important; color: var(--text-primary) !important; }
[role="option"] { min-height: 44px; }
[role="option"]:hover, [role="option"][aria-selected="true"] { background: var(--accent-soft) !important; }
hr { margin: 32px 0; border: 0; border-top: 1px solid var(--border-subtle); }

.empty-state { margin: 8px 0 24px; padding: 28px; border: 1px dashed var(--border-strong); border-radius: var(--radius-card); background: var(--surface-inset); text-align: center; }
.empty-state-mark { width: 32px; height: 4px; margin: 0 auto 16px; border-radius: 999px; background: var(--accent); }
.empty-state-title { color: var(--text-primary); font-size: 1rem; font-weight: 700; }
.empty-state-copy { max-width: 560px; margin: 7px auto 0; color: var(--text-secondary); font-size: .86rem; line-height: 1.6; }
.footer { display: flex; justify-content: space-between; gap: 14px; margin-top: 64px; padding-top: 20px; border-top: 1px solid var(--border-subtle); color: var(--text-muted); font-size: .76rem; }

@media (max-width: 1100px) {
    .block-container { padding-inline: 1.5rem; }
    .stat-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .stat-cell:nth-child(3) { border-inline-start: 0; }
    .stat-cell:nth-child(n+3) { border-top: 1px solid var(--border-strong); }
}
/* Phones: stub below the card body, horizontal perforation, stacked lists. */
@media (max-width: 767.98px) {
    .block-container { padding: 1rem 1rem 4rem; }
    input, textarea, select { font-size: 1rem !important; }
    body:has(.auth-page-marker) .block-container { padding-top: 1.25rem; }
    .auth-wordmark { margin-bottom: 32px; }
    .ticket { flex-direction: column; }
    .ticket-perf { flex-basis: auto; height: 0; border-inline-start: 0; border-top: 2px dashed var(--border-strong); }
    .ticket-perf::before, .ticket-perf::after { top: -13px; bottom: auto; }
    .ticket-perf::before { inset-inline-start: -13px; }
    .ticket-perf::after { inset-inline-start: auto; inset-inline-end: -13px; }
    .ticket-stub, .ticket.compact .ticket-stub { flex-basis: auto; }
    .ticket-lists { grid-template-columns: 1fr; }
    .section-heading-row { grid-template-columns: 34px minmax(0,1fr); gap: 12px; }
    .footer { flex-direction: column; }
    .hero-headline { font-size: clamp(1.8rem, 8vw, 2.4rem); }
    .greeting { font-size: 1.3rem; }
    .pill { font-size: .8rem; }
    .ticket-title { font-size: 1.15rem; }
    .ticket-meta, .ticket-summary, .ticket-list li, .ticket-empty,
    .rail-copy, .boost-effect, .dl-date, .stub-days { font-size: .92rem; line-height: 1.6; }
    .stub-label, .stat-label, .list-title { font-size: .84rem; }
    .stub-score { font-size: 3rem; }
}
@media (max-width: 480px) {
    /* Stat strip stays 2x2 from the 1100px rule. */
    .stat-cell { padding: 14px; }
    .stat-value { font-size: 1.6rem; }
    .ticket-main, .ticket-stub { padding: 18px; }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; }
}
"""


# Kurdish Sorani and Arabic. Inserted between BASE_CSS and ICON_GUARD_CSS so the
# icon guard still wins for Material Symbols. The sidebar stays on the left:
# Streamlit has no supported right-hand sidebar, and flipping it with CSS breaks
# its collapse animation and resize handle.
RTL_CSS = r"""
:root {
    --font-ui: Vazirmatn, Tahoma, "Segoe UI", sans-serif;
    --font-display: Vazirmatn, Tahoma, "Segoe UI", sans-serif;
}
.stApp :is(h1, h2, h3, h4, h5, h6, p, li, label, div, a, button, summary, input, textarea),
[data-baseweb="popover"] :is(li, div) {
    font-family: Vazirmatn, Tahoma, "Segoe UI", sans-serif;
}
/* Arabic-script text is never letter-spaced. */
.stApp, .stApp *, [data-baseweb="popover"] * { letter-spacing: normal !important; }

[data-testid="stMain"],
section[data-testid="stSidebar"],
[data-baseweb="popover"],
[role="tooltip"] {
    direction: rtl;
    text-align: right;
}
[data-testid="stMain"] :is(input, textarea),
section[data-testid="stSidebar"] :is(input, textarea) { direction: rtl; text-align: right; }
/* Emails and passwords are Latin: keep them left-to-right. */
.st-key-login_email_v2 input,
.st-key-signup_email_v2 input,
[data-testid="stTextInput"] input[type="password"] { direction: ltr; text-align: left; }
[data-testid="stMain"] [dir="auto"] { text-align: right; }
.latin { direction: ltr; unicode-bidi: isolate; }
.ticket-summary [dir="ltr"] { text-align: left; line-height: 1.65; }
.stub-score, .stat-value, .dl-days { font-weight: 800; }
"""


FONT_IMPORTS = {
    "en": (
        "<style>@import url('https://fonts.googleapis.com/css2?"
        "family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800"
        "&family=Geist:wght@400;500;600;700&display=swap');</style>"
    ),
    "rtl": (
        "<style>@import url('https://fonts.googleapis.com/css2?"
        "family=Vazirmatn:wght@400;500;600;700;800&display=swap');</style>"
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
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
    '<circle cx="12" cy="12" r="4.2" fill="#F4B740"/>'
    '<g stroke="#F4B740" stroke-width="2" stroke-linecap="round">'
    '<line x1="12" y1="1.8" x2="12" y2="4.4"/><line x1="12" y1="19.6" x2="12" y2="22.2"/>'
    '<line x1="1.8" y1="12" x2="4.4" y2="12"/><line x1="19.6" y1="12" x2="22.2" y2="12"/>'
    '<line x1="4.8" y1="4.8" x2="6.6" y2="6.6"/><line x1="17.4" y1="17.4" x2="19.2" y2="19.2"/>'
    '<line x1="4.8" y1="19.2" x2="6.6" y2="17.4"/><line x1="17.4" y1="6.6" x2="19.2" y2="4.8"/>'
    "</g></svg>"
)
# st.html sanitizes inline <svg>, so the sun ships as an image data URI.
SUN_ICON = (
    '<img class="brand-sun" width="24" height="24" alt="" '
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
            <div class="section-heading-row">
                <div class="section-number">{html.escape(number)}</div>
                <div>
                    <div class="section-eyebrow">{html.escape(eyebrow)}</div>
                    <h2 class="section-title">{html.escape(title)}</h2>
                    <div class="section-copy">{html.escape(description)}</div>
                </div>
            </div>
        </section>
        """
    )


def profile_group(title: str, description: str) -> None:
    st.html(
        f"""
        <div class="profile-group">
            <div class="profile-group-title">{html.escape(title)}</div>
            <div class="profile-group-copy">{html.escape(description)}</div>
        </div>
        """
    )


def render_empty_state(title: str, description: str) -> None:
    st.html(
        f"""
        <div class="empty-state" role="status">
            <div class="empty-state-mark"></div>
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


def render_header(name: str, lang: str, search_key: str, switcher_key: str) -> str:
    """Greeting, search and language switcher; returns the search text."""
    greeting_col, search_col, switch_col = st.columns([1.35, 1.2, 0.95], vertical_alignment="center")
    with greeting_col:
        first_name = (name or "").split()[0] if (name or "").split() else name
        st.html(
            f'<h1 class="greeting">{t_html(greeting_key(), lang, name=f"<bdi>{html.escape(first_name)}</bdi>")}</h1>'
            f'<div class="greeting-sub">{html.escape(format_date(datetime.now(IRAQ_TIME).date(), lang))}</div>'
        )
    with search_col:
        query = st.text_input(
            t("header.search", lang=lang),
            placeholder=t("header.search_placeholder", lang=lang),
            key=search_key,
            label_visibility="collapsed",
            icon=":material/search:",
        )
    with switch_col:
        language_switcher(switcher_key)
    return query


def render_hero(kpis: dict, total_open: int, source_names: list[str], lang: str) -> None:
    template, phrase = count_phrase(kpis["eligible"], lang)
    headline = html.escape(template).replace(
        "{count}", f'<span class="accent">{html.escape(phrase)}</span>'
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
        f'<div class="stat-label">{html.escape(label)}</div></div>'
        for label, value, tone in cells
    )
    st.html(
        f'<section class="hero" id="opportunity-map">'
        f'<h2 class="hero-headline">{headline}</h2>'
        f'<div class="hero-sub">{subline}</div>'
        f'<div class="stat-strip">{strip}</div></section>'
    )


def _list_html(items: list[str], tone: str, empty: str, lang: str | None = None) -> str:
    if not items:
        return f'<div class="ticket-empty">{html.escape(empty)}</div>'
    rows = "".join(
        f'<li>{html.escape(translate_match_message(item, lang))}</li>'
        for item in items[:MAX_LIST_ITEMS]
    )
    return f'<ul class="ticket-list {tone}">{rows}</ul>'


def _meter_html(opportunity: dict, result: dict, lang: str) -> str:
    label, _ = readiness_display(opportunity, result, lang)
    if not has_document_requirements(opportunity):
        return f'<div class="stub-value">{html.escape(label)}</div>'
    filled = round(int(result.get("readiness") or 0) / 10)
    segments = "".join(f'<span class="{"on" if n < filled else ""}"></span>' for n in range(10))
    return (
        f'<div class="meter" role="img" aria-label="{html.escape(label)}">{segments}</div>'
        f'<div class="stub-days">{html.escape(label)}</div>'
    )


def ticket_html(opportunity: dict, result: dict, lang: str | None = None, today: date | None = None) -> str:
    """One opportunity as a ticket: details on the main side, score on the stub."""
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
    pills = (
        f'<span class="pill">{latin(source_name)}</span>'
        f'<span class="pill">{html.escape(type_label)}</span>'
        f'<span class="pill {status_slug}">{html.escape(status_label(status, lang))}</span>'
    )
    if opportunity.get("is_ai_imported"):
        pills += f'<span class="pill">{html.escape(t("card.ai_imported", lang=lang))}</span>'

    if status != "Open":
        return (
            f'<article class="ticket compact">'
            f'<div class="ticket-main"><div class="pill-row">{pills}</div>'
            f'<h3 class="ticket-title" dir="auto">{html.escape(title)}</h3>'
            f'<div class="ticket-meta">{meta} · {html.escape(deadline)}</div></div>'
            f'<div class="ticket-perf" aria-hidden="true"></div>'
            f'<aside class="ticket-stub"><span class="btn-outline" role="button" aria-disabled="true" '
            f'title="{html.escape(t("card.coming_soon", lang=lang))}">{html.escape(t("card.notify_next", lang=lang))}</span></aside>'
            f"</article>"
        )

    summary_ku = normalize_sorani_terms(opportunity.get("summary_ku")).strip()
    summary_en = str(opportunity.get("summary_en") or opportunity.get("notes") or "").strip()
    if lang == "ckb" and summary_ku:
        summary = f'<div class="ticket-summary">{html.escape(summary_ku)}</div>'
    elif summary_en:
        note = (
            f'<div class="ticket-summary-note">{html.escape(t(f"card.summary_missing_{lang}", lang=lang))}</div>'
            if lang in {"ckb", "ar"}
            else ""
        )
        summary = f'<div class="ticket-summary">{note}<div dir="ltr">{html.escape(summary_en)}</div></div>'
    else:
        summary = ""

    # Reasons and gaps come from matcher.py in English; translated for display.
    missing = list(result.get("eligibility_gaps") or []) + list(result.get("readiness_gaps") or [])
    lists = (
        f'<div class="ticket-lists">'
        f'<div><div class="list-title mint">{html.escape(t("card.why_it_fits", lang=lang))}</div>'
        f'{_list_html(list(result.get("reasons") or []), "mint", t("card.why_empty", lang=lang), lang)}</div>'
        f'<div><div class="list-title coral">{html.escape(t("card.still_missing", lang=lang))}</div>'
        f'{_list_html(missing, "coral", t("email.nothing_missing", lang=lang), lang)}</div>'
        f"</div>"
    )

    if eligible:
        eligibility, tone = t("card.eligible", lang=lang), "mint"
    elif needs_review:
        eligibility, tone = t("card.review", lang=lang), "amber"
    else:
        eligibility, tone = t("card.not_eligible", lang=lang), "coral"
    days_html = f'<div class="stub-days{" amber" if soon else ""}">{html.escape(days_left)}</div>' if days_left else ""
    button = (
        f'<a class="btn-saffron" href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener">'
        f'{html.escape(t("card.view", lang=lang).rstrip(" ↗"))}</a>'
        if source_url
        else ""
    )
    return (
        f'<article class="ticket">'
        f'<div class="ticket-main"><div class="pill-row">{pills}</div>'
        f'<h3 class="ticket-title" dir="auto">{html.escape(title)}</h3>'
        f'<div class="ticket-meta">{meta}</div>{summary}{lists}</div>'
        f'<div class="ticket-perf" aria-hidden="true"></div>'
        f'<aside class="ticket-stub">'
        f'<div><div class="stub-label">{html.escape(t("field.match", lang=lang))}</div>'
        f'<div class="stub-score">{html.escape(format_percent(int(result.get("score") or 0), lang))}</div></div>'
        f'<div><div class="stub-label">{html.escape(t("field.readiness", lang=lang))}</div>{_meter_html(opportunity, result, lang)}</div>'
        f'<div><div class="stub-label">{html.escape(t("field.eligibility", lang=lang))}</div>'
        f'<div class="stub-value {tone}">{html.escape(eligibility)}</div></div>'
        f'<div><div class="stub-label">{html.escape(t("field.deadline", lang=lang))}</div>'
        f'<div class="stub-value{" amber" if soon else ""}">{html.escape(deadline)}</div>{days_html}</div>'
        f"{button}</aside></article>"
    )


def render_opportunity_card(
    opportunity: dict,
    result: dict,
    index: int,
    lang: str | None = None,
) -> None:
    st.html(ticket_html(opportunity, result, lang))


def render_booster_rail(improvements: list, lang: str) -> None:
    rows = "".join(
        f'<div class="boost-row">'
        f'<span class="boost-badge" dir="ltr">+{html.escape(format_number(data["unlocked"] or data["improved"], lang))}</span>'
        f'<div><div class="boost-action">{html.escape(translate_booster_label(label, lang))}</div>'
        f'<div class="boost-effect">{html.escape(t("rail.booster_effect", lang=lang, unlocked=format_number(data["unlocked"], lang), improved=format_number(data["improved"], lang)))}</div></div>'
        f"</div>"
        for label, data in improvements[:5]
    ) or f'<div class="rail-copy">{html.escape(t("booster.all_covered", lang=lang))}</div>'
    st.html(
        f'<section class="rail-card" id="opportunity-booster">'
        f'<div class="rail-title">{html.escape(t("nav.opportunity_booster", lang=lang))}</div>{rows}</section>'
    )


def render_alerts_card(enabled: bool, lang: str) -> None:
    state = "on" if enabled else "off"
    st.html(
        f'<section class="rail-card"><div class="rail-title">{html.escape(t("rail.alerts_title", lang=lang))}'
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


PREVIEW_SCORE = 87  # Fictional example on the sign-in page, labelled as such.
PREVIEW_DAYS_LEFT = 30


def preview_ticket_html(lang: str, today: date | None = None) -> str:
    """Sign-in preview: a clearly fictional example, never a real opportunity."""
    today = today or datetime.now(IRAQ_TIME).date()
    example = {
        "deadline": (today + timedelta(days=PREVIEW_DAYS_LEFT)).isoformat(),
    }
    deadline, days_left, soon = deadline_info(example, lang, today)
    return (
        f'<article class="ticket" aria-label="{html.escape(t("signin.preview", lang=lang))}">'
        f'<div class="ticket-main"><div class="pill-row">'
        f'<span class="pill">{html.escape(t("signin.preview", lang=lang))}</span>'
        f'<span class="pill">{html.escape(t_value("type", "Scholarships", lang))}</span>'
        f'<span class="pill open">{html.escape(status_label("Open", lang))}</span></div>'
        f'<h3 class="ticket-title">{html.escape(t("signin.example_title", lang=lang))}</h3>'
        f'<div class="ticket-meta">{html.escape(t("signin.example_org", lang=lang))}</div>'
        f'<div class="ticket-meta"><span class="list-title mint">{html.escape(t("card.eligible", lang=lang))}</span></div></div>'
        f'<div class="ticket-perf" aria-hidden="true"></div>'
        f'<aside class="ticket-stub" style="flex-basis: 170px;">'
        f'<div><div class="stub-label">{html.escape(t("field.match", lang=lang))}</div>'
        f'<div class="stub-score" style="font-size: 2.6rem;">{html.escape(format_percent(PREVIEW_SCORE, lang))}</div></div>'
        f'<div><div class="stub-value{" amber" if soon else ""}">{html.escape(deadline)}</div>'
        f'<div class="stub-days">{html.escape(days_left)}</div></div></aside></article>'
    )


def sign_in_intro_html(lang: str, today: date | None = None) -> str:
    preview_html = (
        f'<div class="auth-preview"><div class="auth-preview-label">{html.escape(t("signin.preview", lang=lang))}</div>'
        f"{preview_ticket_html(lang, today)}</div>"
    )
    return (
        f'<section class="auth-intro">'
        f'<div class="auth-wordmark">{SUN_ICON}{latin("HelAI")}</div>'
        f'<h1 class="auth-headline">{html.escape(t("signin.headline_1", lang=lang))} '
        f'<span class="accent">{html.escape(t("signin.headline_2", lang=lang))}</span></h1>'
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
