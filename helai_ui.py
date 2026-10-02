"""Reusable presentation helpers for the HelAI Streamlit interface."""

from __future__ import annotations

import html

import streamlit as st

from helai_i18n import (
    ACTIVE_KEY,
    CHOICE_KEY,
    LANGUAGE_LABELS,
    LANGUAGES,
    active_language,
    format_date,
    format_number,
    format_percent,
    is_rtl,
    localize_digits,
    normalize_language,
    t,
    t_value,
)
from opportunity_rules import effective_status


BASE_CSS = r"""
<style>
:root {
    --bg-main: #0b0d12;
    --bg-sidebar: #0d1016;
    --surface-1: #11151d;
    --surface-2: #151a23;
    --surface-hover: #1a202b;
    --surface-input: #10141c;
    --border-subtle: rgba(255, 255, 255, 0.07);
    --border-strong: rgba(255, 255, 255, 0.13);
    --text-primary: #f5f7fa;
    --text-secondary: #a7b0be;
    --text-muted: #788391;
    --accent: #7c5cfc;
    --accent-hover: #8d73ff;
    --accent-soft: rgba(124, 92, 252, 0.13);
    --success: #3ccb8e;
    --success-soft: rgba(60, 203, 142, 0.11);
    --warning: #e7b84b;
    --warning-soft: rgba(231, 184, 75, 0.11);
    --danger: #f06a6a;
    --danger-soft: rgba(240, 106, 106, 0.11);
    --info: #6ca8ff;
    --info-soft: rgba(108, 168, 255, 0.11);
    --focus-ring: #b8a9ff;
    --overlay: rgba(5, 7, 11, 0.72);
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;
    --space-8: 32px;
    --space-10: 40px;
    --space-12: 48px;
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-card: 16px;
    --radius-lg: 20px;
    --shadow-card: 0 14px 36px rgba(0, 0, 0, 0.18);
}

html { scroll-behavior: smooth; }
html { scroll-padding-top: var(--space-6); }

html, body, .stApp {
    background: var(--bg-main) !important;
    color: var(--text-primary);
}

/* Zero-specificity typography: Streamlit's own component classes (including
   the Material Symbols icon spans) always win over this default. */
:where(.stApp, .stApp button, .stApp input, .stApp textarea, .stApp select) {
    font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }
a, button, summary, [role="button"], [role="tab"], label { touch-action: manipulation; }
a { color: #b8a9ff; text-underline-offset: 3px; }
a:hover { color: #d5ceff; }
:where(a, button, input, textarea, select, summary, [role="button"], [role="tab"], [tabindex]):focus-visible {
    outline: 2px solid var(--focus-ring) !important;
    outline-offset: 3px !important;
}

.stApp {
    background-image:
        radial-gradient(circle at 72% -12%, rgba(124, 92, 252, .10), transparent 31rem),
        linear-gradient(rgba(255,255,255,.012) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.012) 1px, transparent 1px) !important;
    background-size: auto, 40px 40px, 40px 40px !important;
}

.block-container {
    max-width: 1240px;
    padding: 2rem 3rem 5rem;
    overflow-x: clip;
}

header[data-testid="stHeader"] { background: transparent !important; }
footer { visibility: hidden; }

.stApp p {
    color: var(--text-secondary);
    font-size: 0.95rem;
    line-height: 1.65;
}

.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    color: var(--text-primary);
    letter-spacing: -0.025em;
}

.stApp h3 { font-size: 1.05rem !important; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border-subtle);
    box-shadow: none;
}

section[data-testid="stSidebar"] > div { padding-top: 1.1rem; }
section[data-testid="stSidebar"] p { font-size: 0.82rem; line-height: 1.45; }
section[data-testid="stSidebar"] hr { margin: 1rem 0; border-color: var(--border-subtle); }
.sidebar-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 2px 18px;
}

.brand-mark {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 10px;
    background: var(--accent);
    color: white;
    font-weight: 800;
    letter-spacing: -0.04em;
    box-shadow: 0 8px 22px rgba(124, 92, 252, .22);
}

.brand-name { color: var(--text-primary); font-size: 1rem; font-weight: 750; }
.brand-subtitle { color: var(--text-muted); font-size: .72rem; margin-top: 1px; }

.sidebar-label {
    margin: 18px 2px 8px;
    color: var(--text-muted);
    font-size: .68rem;
    font-weight: 700;
    letter-spacing: .09em;
    text-transform: uppercase;
}

.account-card {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 12px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    background: var(--surface-1);
}

.account-avatar {
    display: grid;
    place-items: center;
    flex: 0 0 36px;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: var(--accent-soft);
    border: 1px solid rgba(124, 92, 252, .25);
    color: #c9bcff;
    font-size: .76rem;
    font-weight: 800;
}

.account-name, .source-name { color: var(--text-primary); font-size: .8rem; font-weight: 650; }
.account-email { color: var(--text-muted); font-size: .7rem; overflow-wrap: anywhere; }
.account-status { margin-top: 4px; color: #86ddb8; font-size: .68rem; }
.account-status::before { content: ""; display: inline-block; width: 6px; height: 6px; margin-right: 6px; border-radius: 50%; background: var(--success); }

.side-nav { display: grid; gap: 3px; }
.side-nav-row {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 34px;
    padding: 7px 9px;
    border-radius: var(--radius-sm);
    color: var(--text-secondary) !important;
    font-size: .78rem;
    text-decoration: none !important;
    transition: background .16s ease, color .16s ease;
}
.side-nav-row:hover { background: var(--surface-hover); color: var(--text-primary) !important; }
.side-nav-number { width: 18px; color: var(--text-muted); font-size: .66rem; font-variant-numeric: tabular-nums; }

.source-list { display: grid; gap: 2px; }
.source-row {
    display: grid;
    grid-template-columns: 8px minmax(0, 1fr);
    gap: 9px;
    align-items: start;
    padding: 8px 4px;
}
.source-dot { width: 7px; height: 7px; margin-top: 5px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 3px var(--success-soft); }
.source-dot.danger { background: var(--danger); box-shadow: 0 0 0 3px var(--danger-soft); }
.source-meta { color: var(--text-muted); font-size: .68rem; line-height: 1.35; }

/* Sign out: last sidebar element, pinned to the bottom by a flexible spacer. */
[data-testid="stSidebarUserContent"]:has(.st-key-helai_sign_out) { padding-bottom: var(--space-6); }
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"]:has(> .st-key-helai_sign_out) {
    min-height: calc(100vh - 120px);
    min-height: calc(100dvh - 120px);
}
.st-key-helai_sign_out {
    margin-top: auto;
    padding-top: var(--space-4);
    border-top: 1px solid var(--border-subtle);
}
section[data-testid="stSidebar"] .st-key-helai_sign_out .stButton > button[kind] {
    width: 100%;
    min-height: 40px;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-sm) !important;
    background: rgba(255, 255, 255, .018) !important;
    color: var(--text-secondary) !important;
    box-shadow: none !important;
    font-size: .78rem !important;
    font-weight: 620 !important;
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
body:has(.auth-page-marker) .block-container { max-width: 1160px; padding-top: 5rem; }

.auth-shell {
    min-height: 650px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    position: relative;
    overflow: hidden;
    padding: 48px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    background:
        radial-gradient(circle at 15% 8%, rgba(124,92,252,.20), transparent 18rem),
        linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px),
        var(--surface-1);
    background-size: auto, 32px 32px, 32px 32px, auto;
}
.auth-shell::after {
    content: "";
    position: absolute;
    right: 10%;
    bottom: 10%;
    width: 150px;
    height: 150px;
    border-radius: 50%;
    background: rgba(124,92,252,.14);
    filter: blur(44px);
    pointer-events: none;
}
.auth-wordmark { margin-bottom: 68px; color: var(--text-primary); font-size: 1rem; font-weight: 800; letter-spacing: .08em; }
.auth-eyebrow, .section-eyebrow, .workspace-eyebrow {
    color: #ad9cff;
    font-size: .72rem;
    font-weight: 750;
    letter-spacing: .10em;
    text-transform: uppercase;
}
.auth-title { max-width: 520px; margin: 16px 0; color: var(--text-primary); font-size: clamp(2.1rem, 4vw, 3.6rem); line-height: 1.04; letter-spacing: -.045em; font-weight: 760; }
.auth-copy { max-width: 500px; color: var(--text-secondary); font-size: .98rem; line-height: 1.7; }
.auth-features { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 28px; }
.auth-feature { padding: 7px 10px; border: 1px solid var(--border-subtle); border-radius: 999px; background: rgba(255,255,255,.025); color: var(--text-secondary); font-size: .73rem; }

.auth-panel-intro { margin: 16px 0 24px; }
.auth-panel-title { margin: 0 0 6px; color: var(--text-primary); font-size: 1.65rem; font-weight: 720; letter-spacing: -.03em; }
.auth-panel-copy { color: var(--text-secondary); font-size: .86rem; }
body:has(.auth-page-marker) [data-testid="stColumn"]:last-child > div {
    padding: 24px 30px 30px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    background: rgba(17,21,29,.94);
    box-shadow: var(--shadow-card);
}

/* Tabs */
[data-baseweb="tab-list"] {
    gap: 4px;
    padding: 4px;
    border-radius: 10px;
    background: var(--bg-main);
}
[data-baseweb="tab"] {
    min-height: 44px;
    border-radius: 8px;
    color: var(--text-muted);
    font-size: .76rem;
    font-weight: 650;
}
[aria-selected="true"][data-baseweb="tab"] { background: var(--surface-2); color: var(--text-primary); }
[data-baseweb="tab"]:hover { color: var(--text-primary); background: rgba(255,255,255,.025); }
[data-baseweb="tab"]:focus-visible { box-shadow: inset 0 0 0 2px var(--focus-ring); outline: 0 !important; }
[data-baseweb="tab-highlight"] { display: none; }

/* Top bar and hero */
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 28px;
    color: var(--text-muted);
    font-size: .72rem;
}
.topbar-brand { display: flex; align-items: center; gap: 9px; color: var(--text-primary); font-weight: 760; }
.topbar-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 3px var(--success-soft); }

.hero { display: none; }
.product-hero {
    position: relative;
    overflow: hidden;
    padding: 64px 56px;
    margin-bottom: 56px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    background:
        radial-gradient(circle at 80% 6%, rgba(124,92,252,.17), transparent 24rem),
        var(--surface-1);
}
.product-hero::after {
    content: "";
    position: absolute;
    inset: 0;
    background-image: linear-gradient(rgba(255,255,255,.014) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.014) 1px, transparent 1px);
    background-size: 40px 40px;
    mask-image: linear-gradient(to left, black, transparent 72%);
    pointer-events: none;
}
.hero-title { max-width: 760px; margin: 14px 0 18px; color: var(--text-primary); font-size: clamp(2.8rem, 5vw, 4.5rem); line-height: 1.02; letter-spacing: -.052em; font-weight: 760; }
.gradient-word { background: linear-gradient(100deg, #f5f7fa 15%, #c4b8ff 68%, #8d73ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.hero-copy { max-width: 650px; color: var(--text-secondary); font-size: 1rem; line-height: 1.7; }
.hero-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 28px; }
.hero-chip, .meta-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 10px;
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    background: rgba(255,255,255,.025);
    color: var(--text-secondary);
    font-size: .72rem;
    font-weight: 600;
}

/* Sections and workspaces */
.section { margin: 64px 0 24px; scroll-margin-top: 24px; }
div.section, .explainer { display: none; }
.section-heading-row { display: grid; grid-template-columns: 42px minmax(0,1fr); gap: 16px; align-items: start; }
.section-number { display: grid; place-items: center; width: 36px; height: 36px; border: 1px solid var(--border-subtle); border-radius: 10px; color: #b9aaff; background: var(--accent-soft); font-size: .72rem; font-weight: 750; }
.section-title { margin: 6px 0 8px; color: var(--text-primary); font-size: clamp(1.7rem, 3vw, 2.25rem); line-height: 1.15; letter-spacing: -.035em; font-weight: 720; }
.section-copy { max-width: 690px; color: var(--text-secondary); font-size: .9rem; line-height: 1.65; }

.workspace-card, div[data-testid="stForm"] {
    padding: 24px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-card);
    background: var(--surface-1);
}
.workspace-heading { display: flex; align-items: center; gap: 9px; margin-bottom: 5px; color: var(--text-primary); font-size: 1rem; font-weight: 680; }
.spark { display: grid; place-items: center; width: 25px; height: 25px; border-radius: 8px; color: #c7bbff; background: var(--accent-soft); }
.workspace-copy { margin-bottom: 18px; color: var(--text-secondary); font-size: .82rem; }
.profile-group { margin: 6px 0 16px; padding-bottom: 9px; border-bottom: 1px solid var(--border-subtle); }
.profile-group-title { color: var(--text-primary); font-size: .86rem; font-weight: 680; }
.profile-group-copy { margin-top: 3px; color: var(--text-muted); font-size: .72rem; }
.profile-callout { display: flex; gap: 12px; margin-bottom: 20px; padding: 14px 16px; border: 1px solid rgba(124,92,252,.22); border-radius: var(--radius-md); background: var(--accent-soft); color: var(--text-secondary); font-size: .8rem; line-height: 1.5; }

/* Inputs */
label[data-testid="stWidgetLabel"] p { color: var(--text-secondary) !important; font-size: .78rem !important; font-weight: 620 !important; }
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div,
[data-baseweb="base-input"],
[data-baseweb="select"] > div {
    min-height: 44px;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-md) !important;
    background: var(--surface-input) !important;
    box-shadow: none !important;
    transition: border-color .16s ease, background .16s ease, box-shadow .16s ease;
}
div[data-baseweb="input"] > div:hover,
div[data-baseweb="textarea"] > div:hover,
div[data-baseweb="select"] > div:hover { border-color: rgba(255,255,255,.20) !important; }
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-soft) !important; }
input, textarea { color: var(--text-primary) !important; font-size: .9rem !important; }
input::placeholder, textarea::placeholder { color: #707b89 !important; opacity: 1; }
textarea { min-height: 180px; }
span[data-baseweb="tag"] { border: 1px solid rgba(124,92,252,.24) !important; border-radius: 7px !important; background: var(--accent-soft) !important; color: #d7d0ff !important; }
[data-testid="stCheckbox"] { padding: 7px 9px; border-radius: 9px; transition: background .16s ease; }
[data-testid="stCheckbox"]:hover { background: rgba(255,255,255,.025); }
[data-testid="stCheckbox"] label p { font-size: .82rem !important; }
[data-testid="stCheckbox"] input:focus-visible + div { box-shadow: 0 0 0 3px var(--accent-soft) !important; }

/* Disabled and read-only controls */
:where(button, input, textarea, select):disabled,
[aria-disabled="true"] {
    cursor: not-allowed !important;
    opacity: .52 !important;
    transform: none !important;
    box-shadow: none !important;
}
input[readonly], textarea[readonly] { color: var(--text-secondary) !important; background: var(--surface-2) !important; }

/* Buttons */
.stButton > button, .stFormSubmitButton > button, .stLinkButton > a {
    min-height: 44px;
    border-radius: 10px !important;
    font-size: .8rem !important;
    font-weight: 680 !important;
    transition: transform .16s ease, border-color .16s ease, background .16s ease, box-shadow .16s ease !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button {
    border: 1px solid var(--accent) !important;
    background: var(--accent) !important;
    color: white !important;
    box-shadow: 0 8px 20px rgba(124,92,252,.18);
}
/* Label <p> and icon follow the button colour instead of `.stApp p`. */
.stButton > button[kind="primary"] :where(p, span),
.stFormSubmitButton > button :where(p, span) {
    color: inherit !important;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover {
    transform: translateY(-1px);
    background: var(--accent-hover) !important;
    border-color: var(--accent-hover) !important;
}
.stButton > button[kind="secondary"], .stLinkButton > a {
    border: 1px solid var(--border-strong) !important;
    background: var(--surface-1) !important;
    color: var(--text-primary) !important;
    box-shadow: none;
}
.stButton > button[kind="secondary"]:hover, .stLinkButton > a:hover { background: var(--surface-hover) !important; border-color: rgba(255,255,255,.20) !important; }
.stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible, .stLinkButton > a:focus-visible { outline: 2px solid #b5a6ff !important; outline-offset: 2px; }
.stButton > button:active, .stFormSubmitButton > button:active, .stLinkButton > a:active { transform: translateY(0) scale(.99); }

/* KPIs */
.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; margin: 8px 0 28px; }
.kpi-card { min-height: 110px; padding: 17px 18px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--surface-1); }
.kpi-accent { width: 22px; height: 3px; margin-bottom: 20px; border-radius: 999px; background: var(--info); }
.kpi-card.success .kpi-accent { background: var(--success); }
.kpi-card.violet .kpi-accent, .kpi-card.accent .kpi-accent { background: var(--accent); }
.kpi-label { color: var(--text-muted); font-size: .71rem; font-weight: 620; }
.kpi-value { margin-top: 5px; color: var(--text-primary); font-size: 1.7rem; line-height: 1; font-weight: 740; letter-spacing: -.035em; }
.kpi-support { margin-top: 8px; color: var(--text-muted); font-size: .67rem; }

/* Opportunity and Booster cards */
[data-testid="stVerticalBlockBorderWrapper"] {
    margin: 14px 0 20px;
    border-color: var(--border-subtle) !important;
    border-radius: var(--radius-card) !important;
    background: var(--surface-1);
    box-shadow: none;
    transition: background .18s ease, border-color .18s ease, transform .18s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover { background: #131821; border-color: var(--border-strong) !important; }

.opportunity-head { padding: 2px 2px 4px; }
.opportunity-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-bottom: 14px; }
.status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 9px; border: 1px solid var(--border-subtle); border-radius: 999px; color: var(--text-secondary); background: rgba(255,255,255,.025); font-size: .68rem; font-weight: 650; }
.status-badge::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); }
.status-badge.open::before, .status-badge.eligible::before { background: var(--success); }
.status-badge.closed::before, .status-badge.not-eligible::before { background: var(--danger); }
.status-badge.upcoming::before, .status-badge.review::before { background: var(--warning); }
.opportunity-title { margin: 0; color: var(--text-primary); font-size: clamp(1.15rem, 2vw, 1.4rem); line-height: 1.28; font-weight: 710; letter-spacing: -.025em; overflow-wrap: anywhere; }
.opportunity-org { margin-top: 6px; color: var(--text-secondary); font-size: .83rem; }
.summary-panel { margin: 14px 0 16px; padding: 14px 16px; border-left: 2px solid var(--accent); border-radius: 0 var(--radius-sm) var(--radius-sm) 0; background: rgba(124,92,252,.055); color: var(--text-secondary); font-size: .85rem; line-height: 1.7; }
.summary-panel[dir="rtl"] { border-left: 0; border-right: 2px solid var(--accent); border-radius: var(--radius-sm) 0 0 var(--radius-sm); text-align: right; font-family: Tahoma, Arial, sans-serif; line-height: 1.95; }
.summary-label { display: block; margin-bottom: 5px; color: #b8a9ff; font-size: .66rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.score-strip { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); margin: 16px 0 12px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); overflow: hidden; }
.score-item { min-width: 0; padding: 13px 14px; background: rgba(255,255,255,.015); }
.score-item + .score-item { border-left: 1px solid var(--border-subtle); }
.score-label { color: var(--text-muted); font-size: .64rem; font-weight: 680; letter-spacing: .06em; text-transform: uppercase; }
.score-value { margin-top: 5px; color: var(--text-primary); font-size: .94rem; font-weight: 700; overflow-wrap: anywhere; }
.score-value.success { color: #78dcb0; }
.score-value.danger { color: #f58e8e; }
.score-value.warning { color: #eac871; }

.detail-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; margin-top: 14px; }
.detail-panel { padding: 14px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: rgba(255,255,255,.014); }
.detail-title { margin-bottom: 8px; color: var(--text-primary); font-size: .72rem; font-weight: 700; }
.detail-item { margin: 6px 0; color: var(--text-secondary); font-size: .76rem; line-height: 1.45; }
.detail-item { display: grid; grid-template-columns: 6px minmax(0, 1fr); gap: 8px; overflow-wrap: anywhere; }
.detail-item::before { content: ""; width: 5px; height: 5px; margin-top: .55em; border-radius: 50%; background: var(--accent-hover); }

.booster-intro { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; margin-bottom: 18px; }
.booster-step { padding: 14px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--surface-1); }
.booster-step-label { color: var(--text-muted); font-size: .66rem; font-weight: 700; text-transform: uppercase; }
.booster-step-copy { margin-top: 5px; color: var(--text-secondary); font-size: .78rem; }
.booster-title { color: var(--text-primary); font-size: 1rem; font-weight: 680; }

/* Native metrics used by extraction and booster */
div[data-testid="stMetric"] { min-height: 92px; padding: 14px 15px; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: rgba(255,255,255,.018); }
div[data-testid="stMetricLabel"] p { color: var(--text-muted) !important; font-size: .7rem !important; font-weight: 620 !important; }
div[data-testid="stMetricValue"] { color: var(--text-primary) !important; font-size: 1.25rem !important; font-weight: 710 !important; }
[data-testid="stProgress"] { margin: 8px 0; }
[data-testid="stProgress"] p { color: var(--text-muted) !important; font-size: .72rem !important; }
[data-testid="stProgress"] > div > div { border-radius: 999px; }

details { border: 1px solid var(--border-subtle) !important; border-radius: var(--radius-md) !important; background: rgba(255,255,255,.014) !important; }
details summary { min-height: 44px; color: var(--text-secondary); font-size: .78rem !important; font-weight: 650 !important; cursor: pointer; }
[data-testid="stAlert"] { border: 1px solid var(--border-strong) !important; border-radius: var(--radius-md) !important; font-size: .82rem; box-shadow: none !important; }
[data-testid="stAlert"] p { margin: 0; color: inherit !important; font-size: .82rem; line-height: 1.5; }
[data-testid="stNotification"] { border-radius: var(--radius-md) !important; }
[data-testid="stSpinner"] { color: var(--text-secondary) !important; }
[data-testid="stSkeleton"] { border-radius: var(--radius-sm); background: var(--surface-2) !important; }

/* Tables and dense data surfaces */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    max-width: 100%;
    overflow: auto;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    background: var(--surface-1);
}
[data-testid="stDataFrame"] * { font-variant-numeric: tabular-nums; }

/* Menus, popovers, and tooltips */
[data-baseweb="popover"], [role="listbox"], [role="tooltip"] {
    border-color: var(--border-strong) !important;
    background: var(--surface-2) !important;
    color: var(--text-primary) !important;
}
[role="option"] { min-height: 40px; }
[role="option"]:hover, [role="option"][aria-selected="true"] { background: var(--accent-soft) !important; }
hr { margin: 32px 0; border: 0; border-top: 1px solid var(--border-subtle); }

.footer { display: flex; justify-content: space-between; gap: 14px; margin-top: 64px; padding-top: 20px; border-top: 1px solid var(--border-subtle); color: var(--text-muted); font-size: .7rem; }

.empty-state {
    margin: 16px 0 28px;
    padding: 28px;
    border: 1px dashed var(--border-strong);
    border-radius: var(--radius-card);
    background: rgba(255,255,255,.012);
    text-align: center;
}
.empty-state-mark { width: 32px; height: 4px; margin: 0 auto 16px; border-radius: 999px; background: var(--accent); }
.empty-state-title { color: var(--text-primary); font-size: 1rem; font-weight: 700; }
.empty-state-copy { max-width: 560px; margin: 7px auto 0; color: var(--text-secondary); font-size: .82rem; line-height: 1.6; }

@media (max-width: 1024px) {
    .block-container { padding-left: 1.75rem; padding-right: 1.75rem; }
    .product-hero { padding: 48px 40px; }
    .kpi-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
    .score-strip { grid-template-columns: repeat(2, minmax(0,1fr)); }
    .score-item:nth-child(3) { border-left: 0; border-top: 1px solid var(--border-subtle); }
    .score-item:nth-child(4) { border-top: 1px solid var(--border-subtle); }
}

@media (max-width: 768px) {
    .block-container { padding: 1rem 1rem 4rem; }
    input, textarea, select { font-size: 1rem !important; }
    body:has(.auth-page-marker) .block-container { padding-top: 1.25rem; }
    body:has(.auth-page-marker) [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 16px !important; }
    body:has(.auth-page-marker) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 100% !important; width: 100% !important; }
    .auth-shell { min-height: auto; padding: 34px 26px; }
    .auth-wordmark { margin-bottom: 48px; }
    body:has(.auth-page-marker) [data-testid="stColumn"]:last-child > div { padding: 20px; }
    .product-hero { padding: 40px 28px; margin-bottom: 40px; }
    .hero-title { font-size: clamp(2.4rem, 12vw, 3.2rem); }
    .section { margin-top: 48px; }
    .section-heading-row { grid-template-columns: 34px minmax(0,1fr); gap: 12px; }
    .section-number { width: 32px; height: 32px; }
    .detail-grid, .booster-intro { grid-template-columns: 1fr; }
    .footer, .topbar { align-items: flex-start; flex-direction: column; }
    [data-testid="stVerticalBlockBorderWrapper"] { margin: 10px 0 16px; }
}

@media (max-width: 480px) {
    .block-container { padding-inline: 12px; }
    .kpi-grid, .score-strip { grid-template-columns: 1fr; }
    .score-item + .score-item { border-left: 0; border-top: 1px solid var(--border-subtle); }
    .product-hero { padding: 34px 22px; }
    .workspace-card, div[data-testid="stForm"] { padding: 18px; }
    .opportunity-title { font-size: 1.1rem; }
    .auth-shell { padding: 28px 20px; }
    .auth-title { font-size: clamp(2rem, 11vw, 2.65rem); }
    .auth-features { gap: 6px; }
    .auth-feature, .hero-chip, .meta-pill, .status-badge { white-space: normal; }
    [data-testid="stHorizontalBlock"] { gap: 10px !important; }
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

.account-status::before { margin-right: 0; margin-left: 6px; }
.summary-panel { border-left: 0; border-right: 2px solid var(--accent); border-radius: var(--radius-sm) 0 0 var(--radius-sm); line-height: 1.95; }
.summary-panel [dir="ltr"] { text-align: left; line-height: 1.7; }
.summary-note { margin-bottom: 8px; color: var(--text-muted); font-size: .76rem; }
.score-item + .score-item { border-left: 0; border-right: 1px solid var(--border-subtle); }
@media (max-width: 1024px) {
    .score-item:nth-child(3) { border-right: 0; }
}
@media (max-width: 480px) {
    .score-item + .score-item { border-right: 0; }
}
"""


VAZIRMATN_IMPORT = (
    "<style>@import url('https://fonts.googleapis.com/css2?"
    "family=Vazirmatn:wght@400;500;600;700;800&display=swap');</style>"
)


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


def build_global_css(lang: str) -> str:
    """Base styles, then RTL overrides for ckb/ar, then the icon guard last."""
    if is_rtl(lang):
        return BASE_CSS + RTL_CSS + ICON_GUARD_CSS
    return GLOBAL_CSS


def inject_global_styles(lang: str | None = None) -> None:
    lang = lang or active_language()
    if is_rtl(lang):
        st.markdown(VAZIRMATN_IMPORT, unsafe_allow_html=True)
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


def status_label(status: str, lang: str | None = None) -> str:
    slug = status.lower() if status in {"Open", "Closed", "Upcoming"} else "review"
    return t(f"status.{slug}", lang=lang)


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


def render_kpis(items: list[tuple[str, str, str, str]]) -> None:
    cards = "".join(
        f"""
        <div class="kpi-card {html.escape(tone)}">
            <div class="kpi-accent"></div>
            <div class="kpi-label">{html.escape(label)}</div>
            <div class="kpi-value">{html.escape(str(value))}</div>
            <div class="kpi-support">{html.escape(support)}</div>
        </div>
        """
        for label, value, support, tone in items
    )
    st.html(f'<div class="kpi-grid">{cards}</div>')


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
    open_results = [
        result
        for opportunity, result in results
        if effective_status(opportunity, today=today) == "Open"
    ]
    return {
        "open": len(open_results),
        "eligible": sum(1 for result in open_results if result["eligible"]),
        "ready": sum(
            1
            for result in open_results
            if result["eligible"] and result["readiness"] == 100
        ),
        "best_score": max((result["score"] for result in open_results), default=0),
    }


DOCUMENT_REQUIREMENT_FLAGS = (
    "requires_passport",
    "requires_ielts",
    "requires_portfolio",
    "requires_cv",
)

NO_DOCUMENT_REQUIREMENTS = t("card.no_document_requirements", lang="en")


def has_document_requirements(opportunity: dict) -> bool:
    return any(opportunity.get(flag) for flag in DOCUMENT_REQUIREMENT_FLAGS)


def readiness_display(opportunity: dict, result: dict, lang: str | None = None) -> tuple[str, str]:
    """Readiness label and tone; a 100% with nothing to check is not shown."""
    if not has_document_requirements(opportunity):
        return t("card.no_document_requirements", lang=lang), "neutral"
    readiness = int(result.get("readiness") or 0)
    return format_percent(readiness, lang), "success" if readiness == 100 else "warning"


def _detail_panel(title: str, items: list[str], empty: str) -> str:
    rendered = "".join(
        f'<div class="detail-item">{html.escape(str(item))}</div>' for item in items
    )
    if not rendered:
        rendered = f'<div class="detail-item">{html.escape(empty)}</div>'
    return f'<div class="detail-panel"><div class="detail-title">{html.escape(title)}</div>{rendered}</div>'


def render_opportunity_card(
    opportunity: dict,
    result: dict,
    index: int,
    lang: str | None = None,
) -> None:
    lang = lang or active_language()
    title = str(opportunity.get("title") or t("card.untitled", lang=lang))
    organization = str(opportunity.get("organization") or t("card.no_organization", lang=lang))
    source_name = str(
        opportunity.get("source_name") or opportunity.get("source") or t("card.unknown_source", lang=lang)
    )
    source_url = str(opportunity.get("source_url") or "")
    opportunity_type = str(opportunity.get("type") or "")
    type_label = t_value("type", opportunity_type, lang) if opportunity_type else t("card.opportunity", lang=lang)
    status, status_slug = card_status(opportunity)
    eligible = bool(result.get("eligible"))
    readiness = int(result.get("readiness") or 0)
    score = int(result.get("score") or 0)
    deadline = format_deadline(opportunity.get("deadline"), lang)
    record_kind = str(opportunity.get("record_kind") or "").strip().lower()
    needs_review = record_kind in {"roundup", "informational"}

    with st.container(border=True):
        review_badge = (
            f'<span class="status-badge review">{html.escape(t("card.reviewed_information", lang=lang))}</span>'
            if needs_review and record_kind != "opportunity"
            else ""
        )
        ai_badge = (
            f'<span class="meta-pill">{html.escape(t("card.ai_imported", lang=lang))}</span>'
            if opportunity.get("is_ai_imported")
            else ""
        )
        st.html(
            f"""
            <div class="opportunity-head">
                <div class="opportunity-meta">
                    <span class="meta-pill">{latin(source_name)}</span>
                    <span class="meta-pill">{html.escape(type_label)}</span>
                    <span class="status-badge {status_slug}">{html.escape(status_label(status, lang))}</span>
                    {review_badge}{ai_badge}
                </div>
                <h3 class="opportunity-title" dir="auto">{html.escape(title)}</h3>
                <div class="opportunity-org" dir="auto">{html.escape(organization)}</div>
            </div>
            """
        )

        # ckb shows the stored Sorani summary; en and ar show the original
        # English text (there is no Arabic summary column yet).
        summary_ku = str(opportunity.get("summary_ku") or "").strip()
        summary_en = str(opportunity.get("summary_en") or opportunity.get("notes") or "").strip()
        if lang == "ckb" and summary_ku:
            st.html(
                f'<div class="summary-panel" dir="rtl"><span class="summary-label">{html.escape(t("card.summary_kurdish", lang=lang))}</span>{html.escape(summary_ku).replace(chr(10), "<br>")}</div>'
            )
        elif summary_en:
            note = ""
            if lang in {"ckb", "ar"}:
                note = f'<div class="summary-note">{html.escape(t(f"card.summary_missing_{lang}", lang=lang))}</div>'
            st.html(
                f'<div class="summary-panel"><span class="summary-label">{html.escape(t("card.about", lang=lang))}</span>{note}<div dir="ltr">{html.escape(summary_en).replace(chr(10), "<br>")}</div></div>'
            )

        eligibility_text = t(
            "card.eligible" if eligible else ("card.review" if needs_review else "card.not_eligible"),
            lang=lang,
        )
        eligibility_tone = "success" if eligible else ("warning" if needs_review else "danger")
        readiness_text, readiness_tone = readiness_display(opportunity, result, lang)
        documents_tracked = has_document_requirements(opportunity)
        st.html(
            f"""
            <div class="score-strip">
                <div class="score-item"><div class="score-label">{html.escape(t("field.match", lang=lang))}</div><div class="score-value">{format_percent(score, lang)}</div></div>
                <div class="score-item"><div class="score-label">{html.escape(t("field.eligibility", lang=lang))}</div><div class="score-value {eligibility_tone}">{html.escape(eligibility_text)}</div></div>
                <div class="score-item"><div class="score-label">{html.escape(t("field.readiness", lang=lang))}</div><div class="score-value {readiness_tone}">{html.escape(readiness_text)}</div></div>
                <div class="score-item"><div class="score-label">{html.escape(t("field.deadline", lang=lang))}</div><div class="score-value">{html.escape(deadline)}</div></div>
            </div>
            """
        )

        st.progress(score / 100, text=t("card.match_progress", lang=lang, score=format_percent(score, lang)))
        if documents_tracked:
            st.progress(
                readiness / 100,
                text=t("card.readiness_progress", lang=lang, readiness=format_percent(readiness, lang)),
            )

        if eligible and not documents_tracked:
            st.info(t("card.alert_eligible_no_docs", lang=lang))
        elif eligible and readiness == 100:
            st.success(t("card.alert_ready", lang=lang))
        elif eligible:
            st.info(t("card.alert_tasks_remaining", lang=lang))
        elif needs_review:
            st.warning(t("card.alert_needs_review", lang=lang))
        else:
            st.warning(t("card.alert_not_eligible", lang=lang))

        # Reasons and gaps come from matcher.py and are still English.
        st.html(
            '<div class="detail-grid">'
            + _detail_panel(t("card.why_it_fits", lang=lang), list(result.get("reasons") or []), t("card.why_empty", lang=lang))
            + _detail_panel(t("field.eligibility", lang=lang), list(result.get("eligibility_gaps") or []), t("card.eligibility_empty", lang=lang))
            + _detail_panel(t("field.readiness", lang=lang), list(result.get("readiness_gaps") or []), t("card.readiness_empty", lang=lang))
            + "</div>"
        )

        action_col, details_col = st.columns([1, 1])
        with action_col:
            if source_url:
                st.link_button(
                    t("card.view", lang=lang),
                    source_url,
                    use_container_width=True,
                )
        with details_col:
            with st.expander(t("card.details", lang=lang)):
                education_rule = opportunity.get("education_rule") or "minimum"
                st.write(f"**{t('field.type', lang=lang)}:**", type_label)
                st.write(f"**{t('field.location', lang=lang)}:**", opportunity.get("location") or t("common.not_stated", lang=lang))
                st.write(f"**{t('field.education', lang=lang)}:**", t_value("education", opportunity.get("education") or "Any", lang))
                st.write(f"**{t('import.education_rule', lang=lang)}:**", t_value("education_rule", education_rule, lang))
                st.write(
                    f"**{t('field.residency_requirement', lang=lang)}:**",
                    t_value("city", opportunity.get("residency_requirement"), lang)
                    if opportunity.get("residency_requirement")
                    else t("common.none_specified", lang=lang),
                )
                if opportunity.get("notes"):
                    st.write(f"**{t('field.notes', lang=lang)}:**", opportunity["notes"])
                st.write(f"**{t('field.source', lang=lang)}:**", source_name)


def render_booster_intro(lang: str | None = None) -> None:
    steps = "".join(
        f'<div class="booster-step"><div class="booster-step-label">{html.escape(t(label, lang=lang))}</div>'
        f'<div class="booster-step-copy">{html.escape(t(copy, lang=lang))}</div></div>'
        for label, copy in (
            ("booster.current", "booster.current_copy"),
            ("booster.suggested", "booster.suggested_copy"),
            ("booster.result", "booster.result_copy"),
        )
    )
    st.html(f'<div class="booster-intro">{steps}</div>')


def render_booster_card(label: str, data: dict, rank: int, lang: str | None = None) -> None:
    with st.container(border=True):
        recommendation = t("booster.recommendation", lang=lang, rank=localize_digits(f"{rank:02d}", lang))
        # The improvement label comes from matcher.analyze_improvements (English).
        st.html(
            f"""
            <div class="opportunity-meta"><span class="meta-pill">{html.escape(recommendation)}</span><span class="status-badge review">{html.escape(t("booster.simulation", lang=lang))}</span></div>
            <div class="booster-title" dir="auto">{html.escape(str(label))}</div>
            """
        )
        columns = st.columns(4)
        metrics = (
            ("booster.unlocked", format_number(data["unlocked"], lang)),
            ("booster.improved", format_number(data["improved"], lang)),
            ("booster.match_gain", "+" + format_number(data["score_gain"], lang)),
            ("booster.readiness_gain", "+" + format_number(data["readiness_gain"], lang)),
        )
        for column, (metric_key, value) in zip(columns, metrics):
            with column:
                st.metric(t(metric_key, lang=lang), value)
