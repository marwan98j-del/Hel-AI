import streamlit as st
import streamlit.components.v1 as components
import html
import re
from datetime import date

from matcher import calculate_match, analyze_improvements
from ai_extractor import extract_opportunity
from opportunity_service import load_opportunities
from auth_service import (
    sign_up_user,
    sign_in_user,
    get_profile,
    update_profile,
    sign_out_user,
)


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="HelAI | هەلی جیهانی",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# KURDISH SORANI UI HELPERS
# =========================================================

KU_DISPLAY = {
    "Open": "کراوە",
    "Closed": "داخراوە",
    "Upcoming": "داهاتوو",
    "Unknown": "نادیار",
    "Any": "هەر ئاستێک",
    "High School": "ئامادەیی",
    "Diploma": "دیپلۆما",
    "Bachelor's Degree": "بەکالۆریۆس",
    "Master's Degree": "ماستەر",
    "PhD": "دکتۆرا",
    "Sulaymaniyah": "سلێمانی",
    "Erbil": "هەولێر",
    "Duhok": "دهۆک",
    "Halabja": "هەڵەبجە",
    "Kirkuk": "کەرکووک",
    "Baghdad": "بەغدا",
    "Iraq": "عێراق",
    "Kurdistan Region": "هەرێمی کوردستان",
    "International": "نێودەوڵەتی",
    "Other": "هیتر",
    "Kurdish Sorani": "کوردی سۆرانی",
    "Kurdish Kurmanji": "کوردی کرمانجی",
    "Arabic": "عەرەبی",
    "English": "ئینگلیزی",
    "Persian": "فارسی",
    "Turkish": "تورکی",
    "Artificial Intelligence": "زیرەکی دەستکرد",
    "Programming": "بەرنامەسازی",
    "Graphic Design": "دیزاینی گرافیک",
    "Social Media": "سۆشیال میدیا",
    "Digital Media": "میدیای دیجیتاڵ",
    "Video Editing": "دەستکاریکردنی ڤیدیۆ",
    "Writing": "نووسین",
    "Translation": "وەرگێڕان",
    "Microsoft Office": "مایکرۆسۆفت ئۆفیس",
    "Data Analysis": "شیکردنەوەی داتا",
    "Marketing": "مارکێتینگ",
    "Photography": "وێنەگرتن",
    "Project Management": "بەڕێوەبردنی پڕۆژە",
    "Technology": "تەکنەلۆجیا",
    "Media": "میدیا",
    "Business": "بازرگانی",
    "Education": "پەروەردە",
    "Entrepreneurship": "کارئافرینی",
    "Leadership": "سەرکردایەتی",
    "Design": "دیزاین",
    "Research": "توێژینەوە",
    "Environment": "ژینگە",
    "Health": "تەندروستی",
    "Culture": "کەلتوور",
    "International Programs": "بەرنامە نێودەوڵەتییەکان",
    "Scholarships": "بورسەکان",
    "Internships": "ڕاهێنانی کار",
    "Competitions": "پێشبڕکێکان",
    "Training Programs": "بەرنامەکانی ڕاهێنان",
    "Grants": "گرانتەکان",
    "Fellowships": "فێلۆشیپەکان",
    "Volunteering": "خۆبەخشین",
    "Exchange Programs": "بەرنامەکانی ئاڵوگۆڕ",
    "Passport": "پاسپۆرت",
    "Valid passport": "پاسپۆرتی دروست",
    "IELTS / English certificate": "IELTS / بڕوانامەی ئینگلیزی",
    "Portfolio": "پۆرتفۆلیۆ",
    "CV": "سیڤی",
}


def ku_value(value):
    text = str(value or "")
    return KU_DISPLAY.get(text, text)


def ku_list(values):
    return "، ".join(ku_value(value) for value in (values or []))


def ku_match_text(text):
    text = str(text or "").strip()

    exact = {
        "This opportunity is closed": "ئەم هەلە داخراوە.",
        "You meet the age requirement": "مەرجی تەمەنت دابین کردووە.",
        "No specific education level is required": "هیچ ئاستێکی دیاریکراوی خوێندن پێویست نییە.",
        "You meet the language requirements": "مەرجەکانی زمانت دابین کردووە.",
        "You meet the Iraq residency requirement": "مەرجی نیشتەجێبوون لە عێراقت دابین کردووە.",
        "You meet the Kurdistan Region residency requirement": "مەرجی نیشتەجێبوون لە هەرێمی کوردستانت دابین کردووە.",
        "Applicants must live in the Kurdistan Region": "داواکار دەبێت لە هەرێمی کوردستان نیشتەجێ بێت.",
        "Location compatibility is neutral": "گونجانی شوێن لە ئاستێکی ناوەنددایە.",
        "The opportunity is available across the Kurdistan Region": "ئەم هەلە لە سەرانسەری هەرێمی کوردستان بەردەستە.",
        "The opportunity is available in Iraq": "ئەم هەلە لە عێراق بەردەستە.",
        "This is an international opportunity": "ئەمە هەلێکی نێودەوڵەتییە.",
    }

    if text in exact:
        return exact[text]

    patterns = [
        (r"^Minimum age is (.+)$", lambda m: f"کەمترین تەمەن {m.group(1)} ساڵە."),
        (r"^Maximum age is (.+)$", lambda m: f"زۆرترین تەمەن {m.group(1)} ساڵە."),
        (r"^Your education matches the required (.+) level$", lambda m: f"ئاستی خوێندنت لەگەڵ {ku_value(m.group(1))} دەگونجێت."),
        (r"^This opportunity specifically targets (.+) applicants$", lambda m: f"ئەم هەلە بە تایبەتی بۆ داواکاری ئاستی {ku_value(m.group(1))} ـە."),
        (r"^Your education meets the (.+) requirement$", lambda m: f"خوێندنت مەرجی {ku_value(m.group(1))} دابین دەکات."),
        (r"^Requires at least (.+)$", lambda m: f"لانیکەم {ku_value(m.group(1))} پێویستە."),
        (r"^Your grade meets the minimum (.+)% requirement$", lambda m: f"نمرەکەت کەمترین مەرجی {m.group(1)}٪ دابین دەکات."),
        (r"^Requires a minimum academic average of (.+)%$", lambda m: f"لانیکەم ناوەندی ئەکادیمی {m.group(1)}٪ پێویستە."),
        (r"^You meet the (.+)-year work experience requirement$", lambda m: f"مەرجی {m.group(1)} ساڵ ئەزموونی کارت دابین کردووە."),
        (r"^Requires (.+) years of work experience$", lambda m: f"{m.group(1)} ساڵ ئەزموونی کار پێویستە."),
        (r"^Missing required language: (.+)$", lambda m: f"زمانی پێویست کەمە: {ku_value(m.group(1))}."),
        (r"^You meet the (.+) residency requirement$", lambda m: f"مەرجی نیشتەجێبوون لە {ku_value(m.group(1))} دابین دەکەیت."),
        (r"^Applicants must live in (.+)$", lambda m: f"داواکار دەبێت لە {ku_value(m.group(1))} نیشتەجێ بێت."),
        (r"^The opportunity is located in (.+)$", lambda m: f"شوێنی ئەم هەلە {ku_value(m.group(1))} ـە."),
        (r"^The opportunity is outside your selected city \((.+)\)$", lambda m: f"ئەم هەلە لە دەرەوەی شاری هەڵبژێردراوتە ({ku_value(m.group(1))})."),
        (r"^You already have the required (.+)$", lambda m: f"{ku_value(m.group(1))} ـی پێویستت هەیە."),
        (r"^Missing document: (.+)$", lambda m: f"بەڵگەنامەی کەم: {ku_value(m.group(1))}."),
        (r"^You are looking for (.+) opportunities$", lambda m: f"تۆ بەدوای هەلی {ku_value(m.group(1))} دەگەڕێیت."),
        (r"^Matching interests: (.+)$", lambda m: "بوارە گونجاوەکان: " + ku_list([x.strip() for x in m.group(1).split(",")]),
        (r"^Matching skills: (.+)$", lambda m: "توانا گونجاوەکان: " + ku_list([x.strip() for x in m.group(1).split(",")]),
    ]

    for pattern, formatter in patterns:
        match = re.match(pattern, text)
        if match:
            return formatter(match)

    return text


def ku_booster_label(text):
    text = str(text or "").strip()

    exact = {
        "Get a valid passport": "پاسپۆرتێکی دروست بەدەستبهێنە",
        "Get an IELTS / English certificate": "بڕوانامەی IELTS / ئینگلیزی بەدەستبهێنە",
        "Create a portfolio": "پۆرتفۆلیۆیەک دروست بکە",
        "Prepare a professional CV": "سیڤییەکی پیشەیی ئامادە بکە",
        "Add English language": "زمانی ئینگلیزی زیاد بکە",
        "Learn Artificial Intelligence": "زیرەکی دەستکرد فێربە",
        "Learn Programming": "بەرنامەسازی فێربە",
        "Learn Data Analysis": "شیکردنەوەی داتا فێربە",
        "Learn Project Management": "بەڕێوەبردنی پڕۆژە فێربە",
    }

    if text in exact:
        return exact[text]

    match = re.match(r"^Reach (.+) level$", text)
    if match:
        return f"بگە بە ئاستی {ku_value(match.group(1))}"

    match = re.match(r"^Reach a (.+)% academic average$", text)
    if match:
        return f"ناوەندی ئەکادیمی بگەیەنە {match.group(1)}٪"

    match = re.match(r"^Build (.+) years of work experience$", text)
    if match:
        return f"{match.group(1)} ساڵ ئەزموونی کار کۆبکەرەوە"

    return text


# =========================================================
# LOAD CLOUD OPPORTUNITIES
# =========================================================

@st.cache_data(ttl=300)
def get_cloud_opportunities():
    return load_opportunities()


try:
    opportunities = get_cloud_opportunities()
except Exception as error:
    st.error(
        "HelAI نەیتوانی هەلەکان لە بنکەدراوەی هەور بار بکات. "
        f"وردەکاریی تەکنیکی: {error}"
    )
    st.stop()


# =========================================================
# VISUAL DESIGN
# =========================================================

st.markdown(
    r"""
<style>

:root {
    --bg: #050816;
    --surface: rgba(12, 19, 43, 0.82);
    --surface-strong: rgba(15, 23, 52, 0.94);

    --white: #f7f9ff;
    --text: #e9edfa;
    --muted: #a7b2ce;

    --blue: #527cff;
    --violet: #8f62ff;
    --cyan: #42e5dd;

    --green: #70f5a0;
    --yellow: #ffc85d;
    --red: #ff6989;

    --border: rgba(130, 151, 255, 0.20);
}


/* ======================================================
   GLOBAL
   ====================================================== */

html {
    scroll-behavior: smooth;
}

html,
body {
    background: var(--bg) !important;
}

body,
button,
input,
textarea,
select {
    font-family:
        Inter,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Arial,
        sans-serif;
}


/* ======================================================
   ANIMATED PAGE BACKGROUND
   No pseudo-elements = cannot cover Streamlit UI
   ====================================================== */

.stApp {
    color: var(--text);

    background:
        radial-gradient(
            circle at 12% 18%,
            rgba(71, 94, 255, 0.28) 0%,
            transparent 31%
        ),
        radial-gradient(
            circle at 84% 78%,
            rgba(54, 228, 218, 0.19) 0%,
            transparent 30%
        ),
        radial-gradient(
            circle at 72% 10%,
            rgba(143, 98, 255, 0.19) 0%,
            transparent 25%
        ),
        linear-gradient(
            135deg,
            #040713 0%,
            #070b1a 42%,
            #09071c 100%
        );

    background-size:
        150% 150%,
        145% 145%,
        160% 160%,
        100% 100%;

    animation:
        ambientBackground 18s ease-in-out infinite alternate;
}


@keyframes ambientBackground {

    0% {
        background-position:
            0% 0%,
            100% 100%,
            70% 0%,
            0% 0%;
    }

    50% {
        background-position:
            15% 20%,
            80% 75%,
            90% 25%,
            0% 0%;
    }

    100% {
        background-position:
            30% 8%,
            65% 90%,
            65% 40%,
            0% 0%;
    }
}


/* ======================================================
   MINIMAL ROUND CURSOR
   ====================================================== */

.stApp,
.stApp button,
.stApp a,
.stApp select,
.stApp [role="button"],
section[data-testid="stSidebar"] {
    cursor:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 18 18'%3E%3Ccircle cx='9' cy='9' r='5.5' fill='%23050816' fill-opacity='.78' stroke='%2342e5dd' stroke-width='1.8'/%3E%3Ccircle cx='9' cy='9' r='1.3' fill='%23ffffff'/%3E%3C/svg%3E")
        9 9,
        auto !important;
}

.stApp:active,
.stApp *:active {
    cursor:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24'%3E%3Ccircle cx='12' cy='12' r='9' fill='%2342e5dd' fill-opacity='.12' stroke='%238f62ff' stroke-width='2'/%3E%3Ccircle cx='12' cy='12' r='2' fill='%2342e5dd'/%3E%3C/svg%3E")
        12 12,
        auto !important;
}

input,
textarea,
[contenteditable="true"] {
    cursor: text !important;
}


/* ======================================================
   MAIN CONTENT
   ====================================================== */

.block-container {
    max-width: 1320px;

    padding-top: 2.5rem;
    padding-bottom: 7rem;
    padding-left: 3.4rem;
    padding-right: 3.4rem;
}


/* ======================================================
   STREAMLIT DEFAULT TEXT
   ====================================================== */

.stApp p {
    color: var(--text);
    font-size: 17px;
    line-height: 1.65;
}

.stApp span {
    color: inherit;
}

.stApp label {
    color: var(--text);
}


/* ======================================================
   STREAMLIT HEADER
   ====================================================== */

header[data-testid="stHeader"] {
    background: transparent !important;
}

footer {
    visibility: hidden;
}


/* ======================================================
   SIDEBAR
   ====================================================== */

section[data-testid="stSidebar"] {

    background:
        linear-gradient(
            180deg,
            rgba(5, 9, 24, 0.98),
            rgba(10, 14, 34, 0.98)
        ) !important;

    border-right:
        1px solid rgba(106, 132, 255, 0.20);

    box-shadow:
        14px 0 60px rgba(0, 0, 0, 0.30);
}


section[data-testid="stSidebar"] h1 {

    font-size: 29px !important;
    font-weight: 950 !important;

    background:
        linear-gradient(
            90deg,
            #ffffff,
            #82a0ff,
            #58efe6
        );

    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}


section[data-testid="stSidebar"] h3 {
    font-size: 17px !important;
    color: #8ea8ff !important;
}


section[data-testid="stSidebar"] p {

    color: #b8c3df !important;
    font-size: 15px !important;
}


section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.09);
}


/* ======================================================
   TOP BAR
   ====================================================== */

.topbar {

    position: relative;
    overflow: hidden;

    display: flex;
    justify-content: space-between;
    align-items: center;

    gap: 20px;

    margin-bottom: 34px;
    padding: 17px 21px;

    border:
        1px solid rgba(115, 143, 255, 0.25);

    border-radius: 15px;

    background:
        rgba(8, 13, 31, 0.66);

    backdrop-filter: blur(18px);

    box-shadow:
        0 18px 50px rgba(0,0,0,0.25),
        inset 0 1px 0 rgba(255,255,255,0.06);

    color: #dfe6ff;

    font-size: 14px;
    font-weight: 800;

    letter-spacing: 0.8px;
}


.topbar::after {

    content: "";

    position: absolute;

    left: -35%;
    bottom: 0;

    width: 30%;
    height: 2px;

    background:
        linear-gradient(
            90deg,
            transparent,
            var(--blue),
            var(--violet),
            var(--cyan),
            transparent
        );

    animation:
        scanTopbar 5s linear infinite;
}


@keyframes scanTopbar {

    from {
        transform: translateX(0);
    }

    to {
        transform: translateX(500%);
    }
}


/* ======================================================
   HERO
   ====================================================== */

.hero {

    position: relative;
    overflow: hidden;

    min-height: 650px;

    display: flex;
    flex-direction: column;
    justify-content: center;

    padding: 75px 68px;
    margin-bottom: 95px;

    border:
        1px solid rgba(124, 149, 255, 0.25);

    border-radius: 30px;

    background:
        radial-gradient(
            circle at 82% 20%,
            rgba(91, 111, 255, 0.24),
            transparent 35%
        ),
        radial-gradient(
            circle at 15% 100%,
            rgba(54, 228, 218, 0.10),
            transparent 34%
        ),
        linear-gradient(
            135deg,
            rgba(12, 18, 41, 0.94),
            rgba(13, 18, 45, 0.75)
        );

    background-size:
        130% 130%,
        140% 140%,
        100% 100%;

    animation:
        heroBackground 11s ease-in-out infinite alternate;

    backdrop-filter: blur(20px);

    box-shadow:
        0 40px 100px rgba(0,0,0,0.38),
        inset 0 1px 0 rgba(255,255,255,0.08);
}


@keyframes heroBackground {

    from {
        background-position:
            100% 0%,
            0% 100%,
            0% 0%;
    }

    to {
        background-position:
            75% 30%,
            25% 70%,
            0% 0%;
    }
}


.hero-badge {

    width: fit-content;

    padding: 10px 16px;
    margin-bottom: 37px;

    border:
        1px solid rgba(66,229,221,0.42);

    border-radius: 999px;

    background:
        rgba(66,229,221,0.07);

    color: #75f5ed;

    font-size: 15px;

    font-weight: 850;

    letter-spacing: 1px;
}


.hero-title {

    max-width: 1050px;

    margin: 0;

    color: #ffffff;

    font-size:
        clamp(
            68px,
            7.8vw,
            122px
        );

    line-height: 0.87;

    letter-spacing: -6px;

    font-weight: 950;
}


.gradient-word {

    background:
        linear-gradient(
            90deg,
            #6c91ff 0%,
            #a66cff 43%,
            #4cebdd 86%
        );

    background-size: 220% 100%;

    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;

    animation:
        titleGradient 7s ease-in-out infinite;
}


@keyframes titleGradient {

    0% {
        background-position: 0% 50%;
    }

    50% {
        background-position: 100% 50%;
    }

    100% {
        background-position: 0% 50%;
    }
}


.hero-copy {

    max-width: 800px;

    margin-top: 42px;

    color: #c0cae4;

    font-size: 21px;

    line-height: 1.67;

    font-weight: 500;
}


.hero-chips {

    display: flex;
    flex-wrap: wrap;

    gap: 11px;

    margin-top: 38px;
}


.hero-chip {

    padding: 9px 14px;

    border:
        1px solid rgba(255,255,255,0.12);

    border-radius: 10px;

    background:
        rgba(255,255,255,0.045);

    color: #dde4f8;

    font-size: 14px;

    font-weight: 750;
}


/* ======================================================
   SECTION HEADERS
   ====================================================== */

.section {

    margin-top: 90px;
    margin-bottom: 38px;
}


.section-index {

    margin-bottom: 17px;

    color: #7899ff;

    font-size: 18px;

    font-weight: 850;

    letter-spacing: 1px;
}


.section-title {

    margin: 0;

    color: #ffffff;

    font-size:
        clamp(
            48px,
            5vw,
            76px
        );

    line-height: 0.95;

    letter-spacing: -3px;

    font-weight: 940;
}


.section-copy {

    max-width: 790px;

    margin-top: 20px;

    color: #aeb9d4;

    font-size: 19px;

    line-height: 1.65;
}


/* ======================================================
   EXPLAINER
   ====================================================== */

.explainer {

    padding: 26px 29px;
    margin: 10px 0 38px 0;

    border:
        1px solid rgba(103, 139, 255, 0.27);

    border-radius: 17px;

    background:
        linear-gradient(
            120deg,
            rgba(79,124,255,0.12),
            rgba(143,98,255,0.08),
            rgba(66,229,221,0.05)
        );

    color: #d9e0f3;

    font-size: 18px;

    line-height: 1.65;

    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.05);
}


/* ======================================================
   CARDS
   ====================================================== */

.card {

    position: relative;
    overflow: hidden;

    margin: 28px 0 30px 0;
    padding: 34px 35px;

    border:
        1px solid rgba(124, 149, 255, 0.23);

    border-radius: 21px;

    background:
        linear-gradient(
            145deg,
            rgba(15, 23, 51, 0.92),
            rgba(8, 13, 31, 0.86)
        );

    backdrop-filter: blur(18px);

    box-shadow:
        0 25px 70px rgba(0,0,0,0.30),
        inset 0 1px 0 rgba(255,255,255,0.06);

    transition:
        transform 0.25s ease,
        border-color 0.25s ease,
        box-shadow 0.25s ease;
}


.card:hover {

    transform: translateY(-6px);

    border-color:
        rgba(101, 150, 255, 0.52);

    box-shadow:
        0 34px 90px rgba(0,0,0,0.40),
        0 0 50px rgba(79,124,255,0.10);
}


.card::before {

    content: "";

    position: absolute;

    left: 0;
    top: 0;

    width: 100%;
    height: 2px;

    background:
        linear-gradient(
            90deg,
            transparent,
            var(--blue),
            var(--violet),
            var(--cyan),
            transparent
        );

    background-size: 220% 100%;

    animation:
        cardLine 5s linear infinite;
}


@keyframes cardLine {

    from {
        background-position: 200% 0%;
    }

    to {
        background-position: -200% 0%;
    }
}


.card-green {
    border-color: rgba(112,245,160,0.26);
}

.card-green::before {
    background:
        linear-gradient(
            90deg,
            transparent,
            var(--green),
            var(--cyan),
            transparent
        );
}


.card-yellow {
    border-color: rgba(255,200,93,0.28);
}

.card-yellow::before {
    background:
        linear-gradient(
            90deg,
            transparent,
            var(--yellow),
            var(--violet),
            transparent
        );
}


.card-red {
    border-color: rgba(255,105,137,0.28);
}

.card-red::before {
    background:
        linear-gradient(
            90deg,
            transparent,
            var(--red),
            var(--violet),
            transparent
        );
}


.card-number {

    margin-bottom: 15px;

    color: #7698ff;

    font-size: 15px;

    font-weight: 850;

    letter-spacing: 1px;
}


.card-title {

    margin-bottom: 9px;

    color: #ffffff;

    font-size: 34px;

    line-height: 1.08;

    letter-spacing: -1.3px;

    font-weight: 920;
}


.card-org {

    color: #a6b1cd;

    font-size: 17px;

    font-weight: 600;
}


.ai-tag {

    display: inline-block;

    margin-top: 18px;
    padding: 8px 12px;

    border:
        1px solid rgba(168,112,255,0.4);

    border-radius: 9px;

    background:
        rgba(143,98,255,0.11);

    color: #d1baff;

    font-size: 13px;

    font-weight: 850;
}


/* ======================================================
   METRICS
   ====================================================== */

div[data-testid="stMetric"] {

    min-height: 116px;

    padding: 21px 23px;

    border:
        1px solid rgba(126,149,255,0.20);

    border-radius: 17px;

    background:
        linear-gradient(
            145deg,
            rgba(17,25,55,0.86),
            rgba(9,14,32,0.82)
        );

    box-shadow:
        0 15px 38px rgba(0,0,0,0.22),
        inset 0 1px 0 rgba(255,255,255,0.05);
}


div[data-testid="stMetricLabel"] {

    color: #9caac9 !important;

    font-size: 15px !important;

    font-weight: 750 !important;
}


div[data-testid="stMetricValue"] {

    color: #ffffff !important;

    font-size: 31px !important;

    font-weight: 900 !important;

    letter-spacing: -1px;
}


/* ======================================================
   FORMS
   ====================================================== */

label[data-testid="stWidgetLabel"] p {

    color: #dce3f5 !important;

    font-size: 16px !important;

    font-weight: 750 !important;
}


div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div {

    border:
        1px solid rgba(126,149,255,0.25) !important;

    border-radius:
        13px !important;

    background:
        rgba(9,14,33,0.86) !important;

    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.04);
}


input,
textarea {

    color: #f4f7ff !important;

    font-size: 17px !important;
}


textarea {
    min-height: 225px;
}


span[data-baseweb="tag"] {

    border:
        1px solid rgba(103,145,255,0.35) !important;

    border-radius:
        8px !important;

    background:
        rgba(79,124,255,0.13) !important;

    color:
        #e1e8ff !important;
}


/* ======================================================
   BUTTONS
   ====================================================== */

.stButton > button,
.stFormSubmitButton > button {

    min-height: 59px;

    border:
        1px solid rgba(132,153,255,0.38) !important;

    border-radius:
        13px !important;

    background:
        linear-gradient(
            110deg,
            #416dff,
            #7a58f6,
            #32d3ca
        ) !important;

    background-size:
        220% 100% !important;

    color:
        #ffffff !important;

    font-size:
        16px !important;

    font-weight:
        850 !important;

    letter-spacing:
        0.4px;

    box-shadow:
        0 17px 40px rgba(77,124,255,0.24);

    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease;

    animation:
        buttonFlow 5s ease-in-out infinite;
}


@keyframes buttonFlow {

    0% {
        background-position: 0% 50%;
    }

    50% {
        background-position: 100% 50%;
    }

    100% {
        background-position: 0% 50%;
    }
}


.stButton > button:hover,
.stFormSubmitButton > button:hover {

    transform:
        translateY(-3px)
        scale(1.004);

    box-shadow:
        0 23px 55px rgba(77,124,255,0.35);
}


/* ======================================================
   CHECKBOXES
   ====================================================== */

[data-testid="stCheckbox"] label {

    color:
        #dce4f7 !important;

    font-size:
        16px !important;
}


/* ======================================================
   ALERTS
   ====================================================== */

[data-testid="stAlert"] {

    border-radius:
        14px !important;

    border:
        1px solid rgba(255,255,255,0.12);

    font-size:
        16px;
}


/* ======================================================
   EXPANDERS
   ====================================================== */

details {

    border:
        1px solid rgba(124,147,255,0.21) !important;

    border-radius:
        14px !important;

    background:
        rgba(9,14,33,0.72) !important;
}


details summary {

    font-size:
        16px !important;

    font-weight:
        750 !important;
}


/* ======================================================
   RESULT HEADINGS
   ====================================================== */

.stApp h3 {

    color:
        #f3f6ff !important;

    font-size:
        21px !important;

    font-weight:
        850 !important;
}


/* ======================================================
   STATUS CHIPS
   ====================================================== */

.chips {

    display:
        flex;

    flex-wrap:
        wrap;

    gap:
        10px;

    margin-top:
        18px;

    margin-bottom:
        21px;
}


.chip {

    padding:
        8px 12px;

    border-radius:
        9px;

    font-size:
        13px;

    font-weight:
        850;

    letter-spacing:
        0.4px;
}


.chip-green {

    color:
        #afffc7;

    border:
        1px solid rgba(112,245,160,0.31);

    background:
        rgba(112,245,160,0.08);
}


.chip-yellow {

    color:
        #ffdc8d;

    border:
        1px solid rgba(255,200,93,0.30);

    background:
        rgba(255,200,93,0.08);
}


.chip-red {

    color:
        #ffa1b5;

    border:
        1px solid rgba(255,105,137,0.30);

    background:
        rgba(255,105,137,0.08);
}


/* ======================================================
   PROGRESS
   ====================================================== */

[data-testid="stProgress"] {

    margin-top:
        13px;

    margin-bottom:
        15px;
}


[data-testid="stProgress"] p {

    color:
        #a3afca !important;

    font-size:
        15px !important;
}


/* ======================================================
   DIVIDERS
   ====================================================== */

hr {

    border:
        none;

    border-top:
        1px solid rgba(255,255,255,0.09);

    margin:
        55px 0;
}


/* ======================================================
   FOOTER
   ====================================================== */

.footer {

    display:
        flex;

    justify-content:
        space-between;

    gap:
        20px;

    margin-top:
        95px;

    padding-top:
        28px;

    border-top:
        1px solid rgba(255,255,255,0.10);

    color:
        #8492b1;

    font-size:
        14px;

    font-weight:
        700;
}


/* ======================================================
   MOBILE
   ====================================================== */

@media (max-width: 800px) {

    .block-container {

        padding-left:
            1.2rem;

        padding-right:
            1.2rem;
    }


    .hero {

        min-height:
            auto;

        padding:
            52px 29px;

        border-radius:
            22px;
    }


    .hero-title {

        font-size:
            56px;

        letter-spacing:
            -3px;
    }


    .hero-copy {

        font-size:
            18px;
    }


    .section-title {

        font-size:
            46px;
    }


    .topbar,
    .footer {

        flex-direction:
            column;

        align-items:
            flex-start;
    }
}



/* ======================================================
   KURDISH SORANI / RTL OVERRIDES
   ====================================================== */

html,
body,
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.block-container {
    direction: rtl !important;
}

body,
button,
input,
textarea,
select,
.stApp,
.stApp p,
.stApp span,
.stApp label,
.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4,
.stApp h5,
.stApp h6 {
    font-family: Tahoma, "Segoe UI", Arial, sans-serif !important;
}

.block-container,
.stApp p,
.stApp label,
.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4,
.stApp h5,
.stApp h6,
.section,
.card,
.explainer {
    text-align: right !important;
}

[data-testid="stHorizontalBlock"] {
    direction: rtl !important;
}

section[data-testid="stSidebar"] {
    order: 2 !important;
    direction: rtl !important;
    text-align: right !important;
    border-right: none !important;
    border-left: 1px solid rgba(106, 132, 255, 0.20) !important;
    box-shadow: -14px 0 60px rgba(0, 0, 0, 0.30) !important;
}

[data-testid="stAppViewContainer"] {
    order: 1 !important;
}

section[data-testid="stSidebar"] [data-testid="stSidebarContent"],
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    direction: rtl !important;
    text-align: right !important;
}

.topbar,
.hero,
.hero-copy,
.section-copy,
.card-title,
.card-org,
.card-number,
.footer,
.chips {
    direction: rtl !important;
    text-align: right !important;
}

.hero-chips,
.chips {
    justify-content: flex-start !important;
}

.hero-badge {
    margin-left: auto !important;
    margin-right: 0 !important;
}

input,
textarea {
    direction: rtl !important;
    text-align: right !important;
}

div[data-baseweb="select"] {
    direction: rtl !important;
    text-align: right !important;
}

.stButton > button,
.stFormSubmitButton > button {
    text-align: center !important;
}

.stButton > button:active,
.stFormSubmitButton > button:active {
    transform: translateY(1px) scale(0.97) !important;
}

div[data-testid="stMetric"],
div[data-testid="stMetricLabel"],
div[data-testid="stMetricValue"] {
    direction: rtl !important;
    text-align: right !important;
}

details,
details summary {
    direction: rtl !important;
    text-align: right !important;
}

@media (max-width: 900px) {
    .block-container {
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
    }
}

</style>
""",
    unsafe_allow_html=True
)



# =========================================================
# CURSOR CLICK EFFECT
# =========================================================

components.html(
    """
<script>
(function () {
    const doc = window.parent.document;

    if (!doc.getElementById("helai-click-fx-style")) {
        const style = doc.createElement("style");
        style.id = "helai-click-fx-style";
        style.textContent = `
            .helai-click-ripple {
                position: fixed;
                width: 14px;
                height: 14px;
                border: 2px solid #42e5dd;
                border-radius: 999px;
                pointer-events: none;
                z-index: 2147483647;
                transform: translate(-50%, -50%) scale(.45);
                box-shadow: 0 0 18px rgba(66, 229, 221, .55);
                animation: helaiRipple .52s ease-out forwards;
            }

            @keyframes helaiRipple {
                0% {
                    opacity: .95;
                    transform: translate(-50%, -50%) scale(.45);
                }

                100% {
                    opacity: 0;
                    transform: translate(-50%, -50%) scale(2.8);
                }
            }
        `;
        doc.head.appendChild(style);
    }

    if (!doc.documentElement.dataset.helaiClickFx) {
        doc.documentElement.dataset.helaiClickFx = "1";

        doc.addEventListener(
            "pointerdown",
            function (event) {
                const ripple = doc.createElement("div");
                ripple.className = "helai-click-ripple";
                ripple.style.left = event.clientX + "px";
                ripple.style.top = event.clientY + "px";
                doc.body.appendChild(ripple);

                window.setTimeout(function () {
                    ripple.remove();
                }, 560);
            },
            true
        );
    }
})();
</script>
""",
    height=0,
    width=0,
)


# =========================================================
# SESSION STATE
# =========================================================

if "ai_imported_opportunity" not in st.session_state:
    st.session_state.ai_imported_opportunity = None

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None

if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if "cloud_profile" not in st.session_state:
    st.session_state.cloud_profile = None


# =========================================================
# HELPERS
# =========================================================

def safe_index(options, value, fallback=0):
    if value in options:
        return options.index(value)
    return fallback


def safe_multiselect_defaults(options, values):
    if not values:
        return []

    return [
        value
        for value in values
        if value in options
    ]


def parse_saved_date(value):
    if isinstance(value, date):
        return value

    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None

    return None


def calculate_age(date_of_birth):
    today = date.today()

    return (
        today.year
        - date_of_birth.year
        - (
            (today.month, today.day)
            <
            (date_of_birth.month, date_of_birth.day)
        )
    )


def clear_auth_state():
    st.session_state.access_token = None
    st.session_state.refresh_token = None
    st.session_state.auth_user = None
    st.session_state.cloud_profile = None
    st.session_state.ai_imported_opportunity = None


def load_cloud_profile():
    if (
        not st.session_state.access_token
        or not st.session_state.refresh_token
    ):
        return None

    result = get_profile(
        access_token=st.session_state.access_token,
        refresh_token=st.session_state.refresh_token,
    )

    if result["success"]:
        st.session_state.cloud_profile = result["profile"]
        return result["profile"]

    return None


# =========================================================
# AUTHENTICATION GATE
# =========================================================

if not st.session_state.access_token:

    with st.sidebar:

        st.title("HELAI")

        st.caption(
            "ئەیجێنتی زیرەکی دەستکردی فرەزمانی تۆ بۆ هەلی جیهانی."
        )

        st.divider()

        st.markdown("### HELAI چی دەکات")

        st.write("٠١  لە ڕاگەیاندنی هەلەکان تێدەگات")
        st.write("٠٢  پڕۆفایلێکی بەردەوام بۆ بەکارهێنەر دروست دەکات")
        st.write("٠٣  گونجان و شایستەبوون دەپشکنێت")
        st.write("٠٤  ئامادەیی بۆ داواکاری دەپێوێت")
        st.write("٠٥  نیشان دەدات چی هەلی زیاتر دەکاتەوە")

        st.divider()

        st.caption("زانیاری هەژمارەکەت بە پارێزراوی لە Supabase هەڵدەگیرێت")
        st.caption("ئۆڵمپیادی AI کوردستان ٢٠٢٦")


    st.html(
        """
<div class="topbar">

    <div>
        HELAI
    </div>

    <div>
        ئەیجێنتی هەلی جیهانی / ٢٠٢٦
    </div>

</div>
"""
    )


    st.html(
        """
<section class="hero">

    <div class="hero-badge">
        ● ئەیجێنتی هەلی جیهانی بە هێزی AI
    </div>

    <h1 class="hero-title">

        هەلی<br>

        <span class="gradient-word">
            جیهانی.
        </span>

    </h1>

    <div class="hero-copy">

        HelAI هەلەکان دەدۆزێتەوە و لێیان تێدەگات، مەرجە ئاڵۆزەکان
        دەگۆڕێت بۆ زانیاریی ڕێکخراو، لەگەڵ پڕۆفایلەکەت بەراوردیان
        دەکات و نیشانت دەدات بۆ چی شایستەیت و چی هێشتا پێویستتە.

    </div>

    <div class="hero-chips">

        <span class="hero-chip">
            AI فرەزمان
        </span>

        <span class="hero-chip">
            پڕۆفایلی هەور
        </span>

        <span class="hero-chip">
            شایستەبوون
        </span>

        <span class="hero-chip">
            ئامادەیی
        </span>

        <span class="hero-chip">
            بەهێزکەری هەل
        </span>

    </div>

</section>
"""
    )


    st.html(
        """
<div class="section">

    <div class="section-index">
        هەژماری HELAI
    </div>

    <div class="section-title">
        بچۆ ژوورەوە یان<br>
        هەژمار دروست بکە.
    </div>

    <div class="section-copy">

        پڕۆفایلەکەت بە پارێزراوی لە هەور هەڵدەگیرێت بۆ ئەوەی
        HelAI هەڵبژاردەکانی هەل و نیشانەکانی شایستەبوونت
        لە هەموو جارێکی بەکارهێناندا بەردەست بگرێت.

    </div>

</div>
"""
    )


    sign_in_tab, sign_up_tab = st.tabs(
        [
            "چوونەژوورەوە",
            "دروستکردنی هەژمار",
        ]
    )


    with sign_in_tab:

        with st.form("helai_sign_in_form"):

            login_email = st.text_input(
                "ئیمەیڵ",
                placeholder="you@example.com",
            )

            login_password = st.text_input(
                "وشەی نهێنی",
                type="password",
            )

            login_submitted = st.form_submit_button(
                "چوونەژوورەوە بۆ HELAI ←",
                use_container_width=True,
            )


        if login_submitted:

            if not login_email.strip() or not login_password:

                st.warning(
                    "ئیمەیڵ و وشەی نهێنی بنووسە."
                )

            else:

                with st.spinner("چوونەژوورەوە..."):

                    login_result = sign_in_user(
                        email=login_email.strip(),
                        password=login_password,
                    )


                if login_result["success"]:

                    st.session_state.access_token = (
                        login_result["access_token"]
                    )

                    st.session_state.refresh_token = (
                        login_result["refresh_token"]
                    )

                    st.session_state.auth_user = (
                        login_result["user"]
                    )

                    profile_result = get_profile(
                        access_token=login_result["access_token"],
                        refresh_token=login_result["refresh_token"],
                    )

                    if profile_result["success"]:
                        st.session_state.cloud_profile = (
                            profile_result["profile"]
                        )

                    st.success(
                        "بە سەرکەوتوویی چوویتە ژوورەوە."
                    )

                    st.rerun()

                else:

                    st.error(
                        "چوونەژوورەوە سەرکەوتوو نەبوو. ئیمەیڵ و وشەی نهێنی بپشکنە."
                    )


    with sign_up_tab:

        with st.form("helai_sign_up_form"):

            signup_name = st.text_input(
                "ناوی تەواو",
                placeholder="ناوی تەواوت",
            )

            signup_email = st.text_input(
                "ئیمەیڵ",
                placeholder="you@example.com",
                key="signup_email",
            )

            signup_password = st.text_input(
                "وشەی نهێنی",
                type="password",
                key="signup_password",
            )

            signup_password_confirm = st.text_input(
                "دووبارەکردنەوەی وشەی نهێنی",
                type="password",
            )

            signup_submitted = st.form_submit_button(
                "هەژماری HELAI دروست بکە ←",
                use_container_width=True,
            )


        if signup_submitted:

            if not signup_name.strip():

                st.warning(
                    "ناوی تەواوت بنووسە."
                )

            elif not signup_email.strip():

                st.warning(
                    "ئیمەیڵەکەت بنووسە."
                )

            elif len(signup_password) < 6:

                st.warning(
                    "وشەی نهێنییەک بە لانیکەم ٦ پیت/ژمارە بەکاربهێنە."
                )

            elif signup_password != signup_password_confirm:

                st.warning(
                    "دوو وشەی نهێنییەکە یەک ناگرنەوە."
                )

            else:

                with st.spinner("هەژماری HELAI دروست دەکرێت..."):

                    signup_result = sign_up_user(
                        email=signup_email.strip(),
                        password=signup_password,
                        full_name=signup_name.strip(),
                    )


                if signup_result["success"]:

                    signup_session = signup_result.get(
                        "session"
                    )

                    if signup_session:

                        st.session_state.access_token = (
                            signup_session.access_token
                        )

                        st.session_state.refresh_token = (
                            signup_session.refresh_token
                        )

                        st.session_state.auth_user = {
                            "id": signup_result["user_id"],
                            "email": signup_result["email"],
                        }

                        load_cloud_profile()

                        st.success(
                            "هەژمار دروست کرا و چوویتە ژوورەوە."
                        )

                        st.rerun()

                    else:

                        st.success(
                            signup_result["message"]
                        )

                        st.info(
                            "After confirming your email, return here "
                            "and sign in."
                        )

                else:

                    st.error(
                        "دروستکردنی هەژمار سەرکەوتوو نەبوو. زانیارییەکان بپشکنە و دووبارە هەوڵ بدە."
                    )


    st.stop()


# =========================================================
# LOAD AUTHENTICATED PROFILE
# =========================================================

if st.session_state.cloud_profile is None:

    cloud_profile_result = get_profile(
        access_token=st.session_state.access_token,
        refresh_token=st.session_state.refresh_token,
    )

    if cloud_profile_result["success"]:

        st.session_state.cloud_profile = (
            cloud_profile_result["profile"]
        )

    else:

        st.warning(
            "چوویتە ژوورەوە، بەڵام HelAI نەیتوانی پڕۆفایلی هەورت بار بکات. "
            "پەڕەکە نوێ بکەرەوە و دووبارە هەوڵ بدە."
        )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("HELAI")

    st.caption(
        "ئەیجێنتی AI ـی تۆ بۆ دۆزینەوەی هەلی جیهانی، "
        "گونجان و ئامادەیی."
    )

    st.divider()

    st.markdown("### هەژمار")

    account_email = ""

    if st.session_state.auth_user:
        account_email = (
            st.session_state.auth_user.get("email")
            or ""
        )

    if not account_email and st.session_state.cloud_profile:
        account_email = (
            st.session_state.cloud_profile.get("email")
            or ""
        )

    if account_email:
        st.caption(account_email)

    if st.session_state.cloud_profile:

        account_name = (
            st.session_state.cloud_profile.get("full_name")
            or ""
        )

        if account_name:
            st.write(account_name)

        if st.session_state.cloud_profile.get(
            "profile_complete",
            False,
        ):
            st.success("پڕۆفایلی هەور ئامادەیە")
        else:
            st.info("پڕۆفایلەکەت لە خوارەوە تەواو بکە")


    if st.button(
        "چوونەدەرەوە",
        use_container_width=True,
        key="logout_button",
    ):

        sign_out_user(
            access_token=st.session_state.access_token,
            refresh_token=st.session_state.refresh_token,
        )

        clear_auth_state()

        st.rerun()


    st.divider()

    st.markdown("### سیستەم")

    st.write("٠١  دەرهێنانی زانیاری بە AI")
    st.write("٠٢  پڕۆفایلی هەور")
    st.write("٠٣  گونجانی پەیوەندی")
    st.write("٠٤  شایستەبوون")
    st.write("٠٥  ئامادەیی")
    st.write("٠٦  بەهێزکەری هەل")

    st.divider()

    st.caption(
        f"{len(opportunities)} هەل بارکرا"
    )

    st.caption(
        "ئۆڵمپیادی AI کوردستان ٢٠٢٦"
    )


# =========================================================
# TOP BAR
# =========================================================

st.html(
    """
<div class="topbar">

    <div>
        HELAI
    </div>

    <div>
        ئەیجێنتی هەلی جیهانی / ٢٠٢٦
    </div>

</div>
"""
)


# =========================================================
# HERO
# =========================================================

st.html(
    """
<section class="hero">

    <div class="hero-badge">
        ● زیرەکی هەلی جیهانی بە هێزی AI
    </div>

    <h1 class="hero-title">

        ئەوە بدۆزەوە<br>

        <span class="gradient-word">
            کە بۆ تۆیە.
        </span>

    </h1>

    <div class="hero-copy">

        HelAI ڕاگەیاندنی هەلە جیهانییەکان دەگۆڕێت بۆ ئەنجامی
        تایبەت بە تۆ. لە مەرجەکان تێدەگات، لەگەڵ پڕۆفایلی
        هەڵگیراوت بەراوردیان دەکات و نیشانت دەدات چی دەگونجێت،
        بۆ چی شایستەیت و پێش داواکردن چی هێشتا پێویستتە.

    </div>

    <div class="hero-chips">

        <span class="hero-chip">
            AI فرەزمان
        </span>

        <span class="hero-chip">
            پڕۆفایلی هەور
        </span>

        <span class="hero-chip">
            نمرەی گونجان
        </span>

        <span class="hero-chip">
            شایستەبوون
        </span>

        <span class="hero-chip">
            بەهێزکەری هەل
        </span>

    </div>

</section>
"""
)


# =========================================================
# SECTION 01 — AI IMPORT
# =========================================================

st.html(
    """
<div class="section">

    <div class="section-index">
        ٠١ / هاوردەکردن بە AI
    </div>

    <div class="section-title">
        هەر هەلێک<br>
        لێرە دابنێ.
    </div>

    <div class="section-copy">

        هەلێک لە فەیسبووک، تێلەگرام، ماڵپەڕ، ئیمەیڵ یان
        هەر سەرچاوەیەکی تر کۆپی بکە. دەکرێت بە کوردی،
        عەرەبی، ئینگلیزی یان تێکەڵ بێت. AI ڕاگەیاندنەکە
        دەگۆڕێت بۆ مەرج و زانیاریی ڕێکخراو.

    </div>

</div>
"""
)


announcement_text = st.text_area(
    "ڕاگەیاندنی هەل",
    height=230,
    placeholder=(
        "دەقی بورس، پێشبڕکێ، ڕاهێنان، کارفێرکاری، "
        "فێلۆشیپ یان گرانت لێرە دابنێ..."
    )
)


if st.button(
    "بە AI شیکاری بکە ←",
    use_container_width=True
):

    if not announcement_text.strip():

        st.warning(
            "سەرەتا ڕاگەیاندنی هەلێک لێرە دابنێ."
        )

    else:

        with st.spinner(
            "AI ڕاگەیاندنەکە شیکار دەکات..."
        ):

            try:

                extracted = extract_opportunity(
                    announcement_text
                )

                st.session_state.ai_imported_opportunity = (
                    extracted
                )

                st.success(
                    "دەرهێنانی زانیاری بە AI بە سەرکەوتوویی تەواو بوو."
                )

            except Exception as error:

                st.error(
                    f"دەرهێنانی زانیاری بە AI سەرکەوتوو نەبوو: {error}"
                )


# =========================================================
# DISPLAY AI EXTRACTION
# =========================================================

if st.session_state.ai_imported_opportunity:

    extracted = (
        st.session_state.ai_imported_opportunity
    )

    title_safe = html.escape(
        str(
            extracted.get(
                "title",
                "هەلی هاوردەکراو بە AI"
            )
        )
    )

    org_safe = html.escape(
        str(
            extracted.get(
                "organization",
                ""
            )
        )
    )


    st.html(
        f"""
<div class="card">

    <div class="card-number">
        دەرهێنانی AI / تەواو
    </div>

    <div class="card-title">
        {title_safe}
    </div>

    <div class="card-org">
        {org_safe}
    </div>

    <div class="ai-tag">
        لە دەقی ڕێکنەخراو دروست کراوە
    </div>

</div>
"""
    )


    a1, a2, a3, a4 = st.columns(4)


    with a1:

        st.metric(
            "جۆر",
            ku_value(extracted.get(
                "type",
                ""
            ))
        )


    with a2:

        st.metric(
            "دۆخ",
            ku_value(extracted.get(
                "status",
                ""
            ))
        )


    with a3:

        st.metric(
            "شوێن",
            extracted.get(
                "location",
                ""
            )
        )


    with a4:

        st.metric(
            "دوا وادە",
            extracted.get(
                "deadline",
                ""
            ) or "دیاری نەکراوە"
        )


    ex1, ex2 = st.columns(
        2,
        gap="large"
    )


    with ex1:

        st.markdown(
            "### زانیاریی شایستەبوون"
        )

        st.write(
            "**خوێندن:**",
            ku_value(
                extracted.get(
                    "education",
                    "Any"
                )
            )
        )

        education_rule = extracted.get(
            "education_rule",
            "minimum"
        )

        st.write(
            "**یاسای خوێندن:**",
            (
                "ئاستی دیاریکراو"
                if education_rule == "exact"
                else "کەمترین ئاست"
            )
        )

        minimum_age = extracted.get(
            "minimum_age"
        )

        maximum_age = extracted.get(
            "maximum_age"
        )

        if (
            minimum_age is not None
            or maximum_age is not None
        ):

            st.write(
                "**تەمەن:**",
                (
                    f"{minimum_age if minimum_age is not None else 'بێ سنووری خوارەوە'}"
                    f" — "
                    f"{maximum_age if maximum_age is not None else 'بێ سنووری سەرەوە'}"
                )
            )

        residency = extracted.get(
            "residency_requirement",
            ""
        )

        st.write(
            "**نیشتەجێبوون:**",
            ku_value(residency) if residency else "هیچ شتێک نەدۆزرایەوە"
        )

        minimum_grade = extracted.get(
            "minimum_grade",
            0
        )

        if minimum_grade:

            st.write(
                "**کەمترین نمرە:**",
                f"{minimum_grade}%"
            )

        required_work = extracted.get(
            "minimum_work_experience_years",
            0
        )

        if required_work:

            st.write(
                "**ئەزموونی کار:**",
                f"{required_work} ساڵ"
            )


    with ex2:

        st.markdown(
            "### نیشانەکانی پڕۆفایل"
        )

        st.write(
            "**زمانەکان:**",
            ku_list(
                extracted.get(
                    "languages",
                    []
                )
            ) or "دیاری نەکراوە"
        )

        st.write(
            "**بوارەکانی حەز:**",
            ku_list(
                extracted.get(
                    "interests",
                    []
                )
            ) or "دیاری نەکراوە"
        )

        st.write(
            "**تواناکان:**",
            ku_list(
                extracted.get(
                    "skills",
                    []
                )
            ) or "دیاری نەکراوە"
        )

        required_docs = []

        if extracted.get(
            "requires_passport",
            False
        ):
            required_docs.append(
                "Passport"
            )

        if extracted.get(
            "requires_ielts",
            False
        ):
            required_docs.append(
                "IELTS / English certificate"
            )

        if extracted.get(
            "requires_portfolio",
            False
        ):
            required_docs.append(
                "Portfolio"
            )

        if extracted.get(
            "requires_cv",
            False
        ):
            required_docs.append(
                "CV"
            )

        st.write(
            "**بەڵگەنامە پێویستەکان:**",
            (
                ku_list(required_docs)
                if required_docs
                else "هیچ شتێک نەدۆزرایەوە"
            )
        )


    with st.expander(
        "بینینی داتای خاو"
    ):

        st.json(
            extracted
        )


    st.markdown("---")



# =========================================================
# SECTION 02 — PROFILE
# =========================================================

st.html(
    """
<div class="section">

    <div class="section-index">
        02 / پڕۆفایلی هەور
    </div>

    <div class="section-title">
        پڕۆفایلەکەت<br>
        تەواو بکە.
    </div>

    <div class="section-copy">

        پڕۆفایلەکەت لە Supabase هەڵدەگیرێت. HelAI خوێندن،
        شوێنی نیشتەجێبوون، زمان، توانا، بوارەکانی حەز،
        ئەزموون و بەڵگەنامەکانت وەک نیشانەی گونجان بەکاردەهێنێت.

    </div>

</div>

<div class="explainer">

    <strong>گونجان</strong> پەیوەندی هەلەکە بە تۆ دەپێوێت.
    <strong>شایستەبوون</strong> مەرجە ناچارییەکان دەپشکنێت.
    <strong>ئامادەیی</strong> دەپشکنێت ئایا بەڵگەنامە پێویستەکان
    بۆ داواکردن ئامادەن یان نا.

</div>
"""
)


saved_profile = (
    st.session_state.cloud_profile
    or {}
)


city_options = [
    "Sulaymaniyah",
    "Erbil",
    "Duhok",
    "Halabja",
    "Kirkuk",
    "Baghdad",
    "Other",
]


education_options = [
    "High School",
    "Diploma",
    "Bachelor's Degree",
    "Master's Degree",
    "PhD",
]


language_options = [
    "Kurdish Sorani",
    "Kurdish Kurmanji",
    "Arabic",
    "English",
    "Persian",
    "Turkish",
    "Other",
]


skill_options = [
    "Artificial Intelligence",
    "Programming",
    "Graphic Design",
    "Social Media",
    "Digital Media",
    "Video Editing",
    "Writing",
    "Translation",
    "Microsoft Office",
    "Data Analysis",
    "Marketing",
    "Photography",
    "Project Management",
]


interest_options = [
    "Artificial Intelligence",
    "Technology",
    "Media",
    "Digital Media",
    "Business",
    "Education",
    "Entrepreneurship",
    "Leadership",
    "Design",
    "Research",
    "Environment",
    "Health",
    "Culture",
    "International Programs",
]


opportunity_type_options = [
    "Scholarships",
    "Internships",
    "Competitions",
    "Training Programs",
    "Grants",
    "Fellowships",
    "Volunteering",
    "Exchange Programs",
]


preferred_language_options = [
    "Kurdish Sorani",
    "English",
    "Arabic",
    "Kurdish Kurmanji",
]


saved_dob = parse_saved_date(
    saved_profile.get(
        "date_of_birth"
    )
)


with st.form(
    "profile_form"
):

    left, right = st.columns(
        2,
        gap="large"
    )


    with left:

        full_name = st.text_input(
            "ناوی تەواو",
            value=(
                saved_profile.get("full_name")
                or ""
            ),
            placeholder="ناوی تەواوت",
        )

        date_of_birth = st.date_input(
            "بەرواری لەدایکبوون",
            value=saved_dob,
            min_value=date(1940, 1, 1),
            max_value=date.today(),
        )

        if date_of_birth:

            st.caption(
                f"تەمەنی بەکارهاتوو بۆ گونجان: "
                f"{calculate_age(date_of_birth)}"
            )

        nationality = st.text_input(
            "نەتەوەیی",
            value=(
                saved_profile.get("nationality")
                or ""
            ),
            placeholder="نموونە: عێراقی",
        )

        country_of_residence = st.text_input(
            "وڵاتی نیشتەجێبوون",
            value=(
                saved_profile.get("country_of_residence")
                or ""
            ),
            placeholder="نموونە: عێراق",
        )

        city = st.selectbox(
            "شار / نیشتەجێبوون",
            city_options,
            format_func=ku_value,
            index=safe_index(
                city_options,
                saved_profile.get("city"),
                0,
            ),
        )

        education = st.selectbox(
            "بەرزترین ئاستی خوێندن",
            education_options,
            format_func=ku_value,
            index=safe_index(
                education_options,
                saved_profile.get("education"),
                0,
            ),
        )

        field_of_study = st.text_input(
            "بواری خوێندن",
            value=(
                saved_profile.get("field_of_study")
                or ""
            ),
            placeholder="نموونە: زانستی کۆمپیوتەر",
        )

        grade = st.number_input(
            "ناوەندی دەرچوون / ڕێژە",
            min_value=0.0,
            max_value=100.0,
            value=float(
                saved_profile.get("grade")
                or 0.0
            ),
            step=0.1,
        )

        work_experience_years = st.number_input(
            "ساڵانی ئەزموونی کار",
            min_value=0.0,
            max_value=50.0,
            value=float(
                saved_profile.get(
                    "work_experience_years"
                )
                or 0.0
            ),
            step=0.5,
        )


    with right:

        languages = st.multiselect(
            "زمانەکان",
            language_options,
            format_func=ku_value,
            placeholder="هەڵبژێرە",
            default=safe_multiselect_defaults(
                language_options,
                saved_profile.get("languages"),
            ),
        )

        skills = st.multiselect(
            "تواناکان",
            skill_options,
            format_func=ku_value,
            placeholder="هەڵبژێرە",
            default=safe_multiselect_defaults(
                skill_options,
                saved_profile.get("skills"),
            ),
        )

        interests = st.multiselect(
            "بوارەکانی حەز",
            interest_options,
            format_func=ku_value,
            placeholder="هەڵبژێرە",
            default=safe_multiselect_defaults(
                interest_options,
                saved_profile.get("interests"),
            ),
        )

        opportunity_types = st.multiselect(
            "جۆرەکانی هەل",
            opportunity_type_options,
            format_func=ku_value,
            placeholder="هەڵبژێرە",
            default=safe_multiselect_defaults(
                opportunity_type_options,
                saved_profile.get(
                    "opportunity_types"
                ),
            ),
        )

        preferred_language = st.selectbox(
            "زمانی پەسەندکراوی HelAI",
            preferred_language_options,
            format_func=ku_value,
            index=safe_index(
                preferred_language_options,
                saved_profile.get(
                    "preferred_language"
                ),
                0,
            ),
        )

        email_notifications = st.checkbox(
            "کاتێک HelAI هەلی گونجاو دەدۆزێتەوە بە ئیمەیڵ ئاگادارم بکەرەوە",
            value=bool(
                saved_profile.get(
                    "email_notifications",
                    True,
                )
            ),
        )

        st.markdown(
            "### بەڵگەنامەکان"
        )

        has_passport = st.checkbox(
            "پاسپۆرتێکی دروستم هەیە",
            value=bool(
                saved_profile.get(
                    "has_passport",
                    False,
                )
            ),
        )

        has_ielts = st.checkbox(
            "بڕوانامەی IELTS / ئینگلیزیم هەیە",
            value=bool(
                saved_profile.get(
                    "has_ielts",
                    False,
                )
            ),
        )

        has_portfolio = st.checkbox(
            "پۆرتفۆلیۆم هەیە",
            value=bool(
                saved_profile.get(
                    "has_portfolio",
                    False,
                )
            ),
        )

        has_cv = st.checkbox(
            "سیڤیم هەیە",
            value=bool(
                saved_profile.get(
                    "has_cv",
                    False,
                )
            ),
        )


    submitted = st.form_submit_button(
        "پڕۆفایل هەڵبگرە + شیکاری بکە ←",
        use_container_width=True,
    )


# =========================================================
# SAVE PROFILE + PREPARE MATCHING
# =========================================================

run_matching = False
profile = None
matching_opportunities = []
results = []


if submitted:

    if not full_name.strip():

        st.warning(
            "تکایە ناوی تەواوت بنووسە."
        )

    elif date_of_birth is None:

        st.warning(
            "تکایە بەرواری لەدایکبوونت دیاری بکە."
        )

    else:

        cloud_profile_data = {
            "full_name": full_name.strip(),
            "date_of_birth": date_of_birth.isoformat(),
            "nationality": nationality.strip(),
            "country_of_residence": (
                country_of_residence.strip()
            ),
            "city": city,
            "education": education,
            "field_of_study": field_of_study.strip(),
            "grade": float(grade),
            "work_experience_years": float(
                work_experience_years
            ),
            "languages": languages,
            "skills": skills,
            "interests": interests,
            "opportunity_types": opportunity_types,
            "has_passport": has_passport,
            "has_ielts": has_ielts,
            "has_portfolio": has_portfolio,
            "has_cv": has_cv,
            "preferred_language": preferred_language,
            "email_notifications": email_notifications,
            "profile_complete": True,
        }


        with st.spinner(
            "پڕۆفایلی هەوری HelAI هەڵدەگیرێت..."
        ):

            save_result = update_profile(
                access_token=st.session_state.access_token,
                refresh_token=st.session_state.refresh_token,
                profile_data=cloud_profile_data,
            )


        if not save_result["success"]:

            st.error(
                "HelAI نەیتوانی پڕۆفایلەکەت هەڵبگرێت. تکایە دووبارە هەوڵ بدە."
            )

        else:

            if save_result["profile"]:

                st.session_state.cloud_profile = (
                    save_result["profile"]
                )

            else:

                refreshed_profile = get_profile(
                    access_token=st.session_state.access_token,
                    refresh_token=st.session_state.refresh_token,
                )

                if refreshed_profile["success"]:
                    st.session_state.cloud_profile = (
                        refreshed_profile["profile"]
                    )


            st.success(
                "پڕۆفایلەکەت بە سەرکەوتوویی لە Supabase هەڵگیرا."
            )


            profile = {
                "full_name": full_name.strip(),
                "city": city,
                "age": calculate_age(
                    date_of_birth
                ),
                "education": education,
                "field_of_study": field_of_study.strip(),
                "grade": float(grade),
                "languages": languages,
                "skills": skills,
                "interests": interests,
                "opportunity_types": opportunity_types,
                "has_passport": has_passport,
                "has_ielts": has_ielts,
                "has_portfolio": has_portfolio,
                "has_cv": has_cv,
                "work_experience_years": float(
                    work_experience_years
                ),
            }


            matching_opportunities = list(
                opportunities
            )


            if st.session_state.ai_imported_opportunity:

                ai_opportunity = dict(
                    st.session_state.ai_imported_opportunity
                )

                ai_opportunity[
                    "source"
                ] = "ڕاگەیاندنی هاوردەکراو بە AI"

                ai_opportunity[
                    "is_ai_imported"
                ] = True

                matching_opportunities.append(
                    ai_opportunity
                )


            for opportunity in matching_opportunities:

                result = calculate_match(
                    profile,
                    opportunity
                )

                results.append(
                    (
                        opportunity,
                        result
                    )
                )


            results.sort(
                key=lambda item: (
                    item[0].get(
                        "status"
                    ) == "Open",
                    item[1]["eligible"],
                    item[1]["score"],
                    item[1]["readiness"]
                ),
                reverse=True
            )


            run_matching = True


if run_matching:

# =====================================================
    # SECTION 03
    # =====================================================

    st.markdown("---")


    st.html(
        """
<div class="section">

    <div class="section-index">
        ٠٣ / نەخشەی هەلەکان
    </div>

    <div class="section-title">
        باشترین<br>
        هەڵبژاردەکانت.
    </div>

    <div class="section-copy">

        سیستەم گونجان لە شایستەبوون جیا دەکاتەوە.
        هەلێک ڕەنگە زۆر لەگەڵت بگونجێت، بەڵام ئەگەر
        مەرجێکی ناچاری کەم بێت، وەک ناشایستە نیشان بدرێت.

    </div>

</div>
"""
    )


    open_count = sum(
        1
        for opportunity, result in results
        if opportunity.get(
            "status"
        ) == "Open"
    )


    eligible_count = sum(
        1
        for opportunity, result in results
        if (
            opportunity.get(
                "status"
            ) == "Open"
            and result["eligible"]
        )
    )


    ready_count = sum(
        1
        for opportunity, result in results
        if (
            opportunity.get(
                "status"
            ) == "Open"
            and result["eligible"]
            and result["readiness"] == 100
        )
    )


    best_score = max(
        (
            result["score"]
            for opportunity, result in results
            if opportunity.get(
                "status"
            ) == "Open"
        ),
        default=0
    )


    m1, m2, m3, m4 = st.columns(4)


    with m1:

        st.metric(
            "هەلە کراوەکان",
            open_count
        )


    with m2:

        st.metric(
            "ئێستا شایستەیت",
            eligible_count
        )


    with m3:

        st.metric(
            "ئامادەی داواکردن",
            ready_count
        )


    with m4:

        st.metric(
            "باشترین گونجان",
            f"{best_score}%"
        )


    st.markdown("---")


    # =====================================================
    # RESULT CARDS
    # =====================================================

    for index, (
        opportunity,
        result
    ) in enumerate(
        results,
        start=1
    ):


        title_safe = html.escape(
            str(
                opportunity.get(
                    "title",
                    "هەلی بێ ناونیشان"
                )
            )
        )


        org_safe = html.escape(
            str(
                opportunity.get(
                    "organization",
                    ""
                )
            )
        )


        if (
            opportunity.get(
                "status"
            ) == "Closed"
        ):

            card_class = "card card-red"


        elif (
            result["eligible"]
            and result["readiness"] == 100
        ):

            card_class = "card card-green"


        elif result["eligible"]:

            card_class = "card card-yellow"


        else:

            card_class = "card"


        ai_tag = ""


        if opportunity.get(
            "is_ai_imported",
            False
        ):

            ai_tag = (
                '<div class="ai-tag">'
                'بە AI هاوردەکراو'
                '</div>'
            )


        st.html(
            f"""
<div class="{card_class}">

    <div class="card-number">
        {index:02d} / هەل
    </div>

    <div class="card-title">
        {title_safe}
    </div>

    <div class="card-org">
        {org_safe}
    </div>

    {ai_tag}

</div>
"""
        )



        # HELAI LOCALIZED OPPORTUNITY SUMMARY

        active_language = str(
            (
                st.session_state.cloud_profile
                or {}
            ).get(
                "preferred_language",
                "English"
            )
        ).strip()


        summary_ku = str(
            opportunity.get(
                "summary_ku"
            )
            or ""
        ).strip()


        summary_en = str(
            opportunity.get(
                "summary_en"
            )
            or ""
        ).strip()


        summary_notes = str(
            opportunity.get(
                "notes"
            )
            or ""
        ).strip()


        if (
            active_language
            == "Kurdish Sorani"
            and summary_ku
        ):

            summary_safe = (
                html.escape(
                    summary_ku
                )
                .replace(
                    "\n",
                    "<br>"
                )
            )


            st.html(
                f"""
<div
    dir="rtl"
    style="
        margin: 16px 0 24px 0;
        padding: 20px 22px;

        background:
            rgba(15, 23, 52, 0.78);

        border:
            1px solid
            rgba(130, 151, 255, 0.24);

        border-radius: 14px;

        direction: rtl;
        text-align: right;

        font-family:
            Tahoma,
            Arial,
            sans-serif;

        line-height: 2;

        color: #e9edfa;
    "
>

    <div
        style="
            margin-bottom: 10px;

            color: #42e5dd;

            font-size: 12px;
            font-weight: 700;

            letter-spacing: 0.4px;
        "
    >
        پوختەی کوردی
    </div>


    <div
        style="
            font-size: 16px;
        "
    >
        {summary_safe}
    </div>

</div>
"""
            )


        elif summary_en or summary_notes:

            summary_text = (
                summary_en
                or summary_notes
            )


            st.markdown(
                "#### دەربارەی ئەم هەلە"
            )


            st.write(
                summary_text
            )


        c1, c2, c3, c4 = st.columns(4)


        with c1:

            st.metric(
                "گونجان",
                f"{result['score']}%"
            )


        with c2:

            st.metric(
                "شایستەبوون",
                (
                    "شایستە"
                    if result["eligible"]
                    else "ناشایستە"
                )
            )


        with c3:

            st.metric(
                "ئامادەیی",
                f"{result['readiness']}%"
            )


        with c4:

            st.metric(
                "دوا وادە",
                opportunity.get(
                    "deadline",
                    ""
                ) or "دیاری نەکراوە"
            )


        st.progress(
            result["score"] / 100,
            text=(
                f"گونجانی هەل · "
                f"{result['score']}%"
            )
        )


        st.progress(
            result["readiness"] / 100,
            text=(
                f"ئامادەیی بۆ داواکردن · "
                f"{result['readiness']}%"
            )
        )


        status = opportunity.get(
            "status",
            ""
        )


        status_class = (
            "chip-green"
            if status == "Open"
            else "chip-red"
        )


        eligibility_class = (
            "chip-green"
            if result["eligible"]
            else "chip-red"
        )


        readiness_class = (
            "chip-green"
            if result["readiness"] == 100
            else "chip-yellow"
        )


        st.html(
            f"""
<div class="chips">

    <span class="chip {status_class}">
        {html.escape(ku_value(status))}
    </span>

    <span class="chip {eligibility_class}">
        {"شایستە" if result["eligible"] else "ناشایستە"}
    </span>

    <span class="chip {readiness_class}">
        ئامادەیی {result["readiness"]}%
    </span>

</div>
"""
        )


        if (
            result["eligible"]
            and result["readiness"] == 100
        ):

            st.success(
                "وا دیارە شایستەیت و بۆ داواکردن ئامادەیت."
            )


        elif result["eligible"]:

            st.info(
                "وا دیارە شایستەیت، بەڵام هێشتا هەندێک هەنگاوی ئامادەکاری ماوە."
            )


        else:

            st.warning(
                "ئەم هەلە ڕەنگە لەگەڵت بگونجێت، "
                "بەڵام ئێستا یەک یان زیاتر لە "
                "مەرجە ناچارییەکانی شایستەبوونت کەمە."
            )


        why_col, eligibility_col, readiness_col = (
            st.columns(
                3,
                gap="large"
            )
        )


        with why_col:

            st.markdown(
                "### بۆچی لەگەڵت دەگونجێت"
            )

            if result["reasons"]:

                for reason in result["reasons"]:

                    st.write(
                        f"＋ {ku_match_text(reason)}"
                    )

            else:

                st.caption(
                    "هیچ نیشانەیەکی گونجاوی ئەرێنی نییە."
                )


        with eligibility_col:

            st.markdown(
                "### شایستەبوون"
            )

            if result["eligibility_gaps"]:

                for issue in result[
                    "eligibility_gaps"
                ]:

                    st.write(
                        f"— {ku_match_text(issue)}"
                    )

            else:

                st.success(
                    "هیچ کەموکوڕییەکی ناچاری لە شایستەبووندا نییە."
                )


        with readiness_col:

            st.markdown(
                "### ئامادەیی"
            )

            if result["readiness_gaps"]:

                for issue in result[
                    "readiness_gaps"
                ]:

                    st.write(
                        f"— {ku_match_text(issue)}"
                    )

            else:

                st.success(
                    "هیچ بەڵگەنامەی پێویست کەم نییە."
                )


        with st.expander(
            "بینینی وردەکاریی هەل"
        ):

            st.write(
                "**جۆر:**",
                ku_value(
                    opportunity.get(
                        "type",
                        ""
                    )
                )
            )

            st.write(
                "**شوێن:**",
                opportunity.get(
                    "location",
                    ""
                )
            )

            st.write(
                "**خوێندن:**",
                ku_value(
                    opportunity.get(
                        "education",
                        "Any"
                    )
                )
            )

            st.write(
                "**یاسای خوێندن:**",
                (
                    "ئاستی دیاریکراو"
                    if opportunity.get(
                        "education_rule",
                        "minimum"
                    ) == "exact"
                    else "کەمترین ئاست"
                )
            )

            residency = opportunity.get(
                "residency_requirement",
                ""
            )

            st.write(
                "**مەرجی نیشتەجێبوون:**",
                ku_value(residency) if residency else "دیاری نەکراوە"
            )

            notes = opportunity.get(
                "notes",
                ""
            )

            if notes:

                st.write(
                    "**تێبینی:**",
                    notes
                )

            source = opportunity.get(
                "source",
                ""
            )

            if source:

                st.write(
                    "**سەرچاوە:**",
                    source
                )


        st.markdown("---")


    # =====================================================
    # SECTION 04 — BOOSTER
    # =====================================================

    st.html(
        """
<div class="section">

    <div class="section-index">
        04 / بەهێزکەری هەل
    </div>

    <div class="section-title">
        هەلی زیاتر<br>
        بکەرەوە.
    </div>

    <div class="section-copy">

        بەهێزکەری هەل گۆڕانکارییەکانی پڕۆفایلەکەت تاقی دەکاتەوە
        و دیاری دەکات کام هەنگاو دەتوانێت هەلی زیاتر بکاتەوە
        یان ئامادەییت بۆ داواکردن زیاد بکات.

    </div>

</div>
"""
    )


    improvements = analyze_improvements(
        profile,
        matching_opportunities
    )


    if improvements:

        for rank, (
            label,
            data
        ) in enumerate(
            improvements[:5],
            start=1
        ):


            safe_label = html.escape(
                ku_booster_label(
                    label
                )
            )


            st.html(
                f"""
<div class="card">

    <div class="card-number">
        پێشنیار / {rank:02d}
    </div>

    <div class="card-title">
        {safe_label}
    </div>

</div>
"""
            )


            b1, b2, b3, b4 = st.columns(4)


            with b1:

                st.metric(
                    "کراوەوە",
                    data["unlocked"]
                )


            with b2:

                st.metric(
                    "باشترکراو",
                    data["improved"]
                )


            with b3:

                st.metric(
                    "زیادبوونی گونجان",
                    f"+{data['score_gain']}"
                )


            with b4:

                st.metric(
                    "زیادبوونی ئامادەیی",
                    f"+{data['readiness_gain']}"
                )


    else:

        st.success(
            "پڕۆفایلەکەت هەموو ئەو باشترکردنانەی "
            "ئەم نموونەیە تاقی دەکاتەوە، لەخۆگرتووە."
        )


# =========================================================
# FOOTER
# =========================================================

st.html(
    """
<div class="footer">

    <div>
        HELAI / نموونەی سەرەتایی
    </div>

    <div>
        ئۆڵمپیادی AI کوردستان / ٢٠٢٦
    </div>

</div>
"""
)