import streamlit as st
import streamlit.components.v1 as components
import html
from datetime import date

from matcher import calculate_match, analyze_improvements
from ai_extractor import extract_opportunity
from opportunity_service import load_opportunities
from helai_source_status import load_source_status
from opportunity_rules import (
    APPLICANT_INDIVIDUAL,
    normalize_deadline,
    normalize_open_date,
    normalize_status,
)
from source_adapters import get_source_catalog
from auth_service import (
    sign_up_user,
    sign_in_user,
    get_profile,
    update_profile,
    sign_out_user,
)

MISSION_STATEMENT = (
    "HelAI is an AI-powered opportunity agent that automatically discovers "
    "global opportunities, understands their requirements, matches them with "
    "each user’s profile, and delivers personalized guidance on what they "
    "qualify for and what they need to apply."
)

MISSION_STATEMENT_HTML = html.escape(MISSION_STATEMENT)


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="HelAI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)


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
        "HelAI could not load opportunities from the cloud database. "
        f"Details: {error}"
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
   MINIMAL WHITE DOT + RING CURSOR
   ====================================================== */

.stApp,
.stApp button,
.stApp a,
.stApp select,
.stApp [role="button"],
section[data-testid="stSidebar"] {
    cursor:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='12' fill='none' stroke='%23ffffff' stroke-opacity='.14' stroke-width='1'/%3E%3Ccircle cx='16' cy='16' r='3.6' fill='%23ffffff'/%3E%3C/svg%3E")
        16 16,
        auto !important;
}

.stApp:active,
.stApp button:active,
.stApp a:active,
.stApp [role="button"]:active,
section[data-testid="stSidebar"]:active {
    cursor:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='12.7' fill='none' stroke='%23ffffff' stroke-opacity='.30' stroke-width='1.2'/%3E%3Ccircle cx='16' cy='16' r='4.2' fill='%23ffffff'/%3E%3C/svg%3E")
        16 16,
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

.mission-statement {

    max-width: 860px;

    margin-top: 28px;
    padding-left: 18px;

    border-left:
        2px solid rgba(66,229,221,0.48);

    color: #d9e1f5;

    font-size: 18px;

    line-height: 1.68;

    font-weight: 650;
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

</style>
""",
    unsafe_allow_html=True
)


# Small click ripple that appears exactly where the user clicks.
components.html(
    """
<script>
(function () {
    const doc = window.parent.document;

    if (!doc.getElementById("helai-click-ripple-style")) {
        const style = doc.createElement("style");
        style.id = "helai-click-ripple-style";
        style.textContent = `
            .helai-click-ripple {
                position: fixed;
                left: 0;
                top: 0;
                width: 28px;
                height: 28px;
                border: 1px solid rgba(255, 255, 255, .28);
                border-radius: 50%;
                pointer-events: none;
                z-index: 2147483647;
                transform: translate(-50%, -50%) scale(.86);
                animation: helaiClickRipple .42s ease-out forwards;
            }

            @keyframes helaiClickRipple {
                0% {
                    opacity: .75;
                    transform: translate(-50%, -50%) scale(.86);
                }

                100% {
                    opacity: 0;
                    transform: translate(-50%, -50%) scale(1.65);
                }
            }
        `;

        doc.head.appendChild(style);
    }

    if (!doc.documentElement.dataset.helaiClickRippleReady) {
        doc.documentElement.dataset.helaiClickRippleReady = "1";

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
            "Your multilingual AI agent for global opportunities."
        )

        st.divider()

        st.markdown("### WHAT HELAI DOES")

        st.write("01  Understands opportunity announcements")
        st.write("02  Builds a persistent user profile")
        st.write("03  Checks relevance and eligibility")
        st.write("04  Measures application readiness")
        st.write("05  Shows what can unlock more opportunities")

        st.divider()

        st.caption("Secure account data powered by Supabase")
        st.caption("AI Olympiad Kurdistan 2026")


    st.html(
        """
<div class="topbar">

    <div>
        HELAI
    </div>

    <div>
        GLOBAL OPPORTUNITY AGENT / 2026
    </div>

</div>
"""
    )


    st.html(
        f"""
<section class="hero">

    <div class="hero-badge">
        ● AI-POWERED GLOBAL OPPORTUNITY AGENT
    </div>

    <h1 class="hero-title">

        GLOBAL<br>

        <span class="gradient-word">
            OPPORTUNITIES.
        </span>

    </h1>

    <div class="mission-statement">

        {MISSION_STATEMENT_HTML}

    </div>

    <div class="hero-chips">

        <span class="hero-chip">
            MULTILINGUAL AI
        </span>

        <span class="hero-chip">
            CLOUD PROFILE
        </span>

        <span class="hero-chip">
            ELIGIBILITY
        </span>

        <span class="hero-chip">
            READINESS
        </span>

        <span class="hero-chip">
            OPPORTUNITY BOOSTER
        </span>

    </div>

</section>
"""
    )


    st.html(
        """
<div class="section">

    <div class="section-index">
        HELAI ACCOUNT
    </div>

    <div class="section-title">
        SIGN IN OR<br>
        CREATE ACCOUNT.
    </div>

    <div class="section-copy">

        Your profile is stored securely in the cloud so HelAI
        can keep your opportunity preferences and eligibility
        signals available across sessions.

    </div>

</div>
"""
    )


    sign_in_tab, sign_up_tab = st.tabs(
        [
            "SIGN IN",
            "CREATE ACCOUNT",
        ]
    )


    with sign_in_tab:

        with st.form("helai_sign_in_form"):

            login_email = st.text_input(
                "Email",
                placeholder="you@example.com",
            )

            login_password = st.text_input(
                "Password",
                type="password",
            )

            login_submitted = st.form_submit_button(
                "SIGN IN TO HELAI →",
                use_container_width=True,
            )


        if login_submitted:

            if not login_email.strip() or not login_password:

                st.warning(
                    "Enter your email and password."
                )

            else:

                with st.spinner("Signing in..."):

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
                        "Signed in successfully."
                    )

                    st.rerun()

                else:

                    st.error(
                        login_result["message"]
                    )


    with sign_up_tab:

        with st.form("helai_sign_up_form"):

            signup_name = st.text_input(
                "Full Name",
                placeholder="Your full name",
            )

            signup_email = st.text_input(
                "Email",
                placeholder="you@example.com",
                key="signup_email",
            )

            signup_password = st.text_input(
                "Password",
                type="password",
                key="signup_password",
            )

            signup_password_confirm = st.text_input(
                "Confirm Password",
                type="password",
            )

            signup_submitted = st.form_submit_button(
                "CREATE HELAI ACCOUNT →",
                use_container_width=True,
            )


        if signup_submitted:

            if not signup_name.strip():

                st.warning(
                    "Enter your full name."
                )

            elif not signup_email.strip():

                st.warning(
                    "Enter your email."
                )

            elif len(signup_password) < 6:

                st.warning(
                    "Use a password with at least 6 characters."
                )

            elif signup_password != signup_password_confirm:

                st.warning(
                    "The two passwords do not match."
                )

            else:

                with st.spinner("Creating your HelAI account..."):

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
                            "Account created and signed in."
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
                        signup_result["message"]
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
            "You are signed in, but HelAI could not load your "
            "cloud profile. You can still try again by reloading."
        )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("HELAI")

    st.caption(
        "Your AI agent for global opportunity discovery, "
        "matching and readiness."
    )

    st.divider()

    st.markdown("### ACCOUNT")

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
            st.success("Cloud profile ready")
        else:
            st.info("Complete your profile below")


    if st.button(
        "LOG OUT",
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

    st.markdown("### SYSTEM")

    st.write("01  AI extraction")
    st.write("02  Cloud profile")
    st.write("03  Relevance matching")
    st.write("04  Eligibility")
    st.write("05  Readiness")
    st.write("06  Opportunity Booster")

    st.divider()

    st.markdown("### OPPORTUNITY SOURCES")

    source_status = load_source_status()

    for source in get_source_catalog():
        key = source["key"]
        status = source_status.get(key, {})
        label = source["source_name"]

        if status:
            last_status = status.get(
                "last_status",
                "unknown",
            )

            imported = status.get(
                "imported"
            )

            discovered = status.get(
                "discovered"
            )

            st.caption(
                f"{label} - {last_status}"
            )

            if (
                discovered is not None
                and imported is not None
            ):
                st.caption(
                    f"Last run: {discovered} found, "
                    f"{imported} imported"
                )

        else:
            st.caption(
                f"{label} - active"
            )

    st.divider()

    st.caption(
        f"{len(opportunities)} opportunities loaded"
    )

    st.caption(
        "AI Olympiad Kurdistan 2026"
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
        GLOBAL OPPORTUNITY AGENT / 2026
    </div>

</div>
"""
)


# =========================================================
# HERO
# =========================================================

st.html(
    f"""
<section class="hero">

    <div class="hero-badge">
        ● AI-POWERED GLOBAL OPPORTUNITY INTELLIGENCE
    </div>

    <h1 class="hero-title">

        FIND WHAT<br>

        <span class="gradient-word">
            FITS YOU.
        </span>

    </h1>

    <div class="mission-statement">

        {MISSION_STATEMENT_HTML}

    </div>

    <div class="hero-chips">

        <span class="hero-chip">
            MULTILINGUAL AI
        </span>

        <span class="hero-chip">
            CLOUD PROFILE
        </span>

        <span class="hero-chip">
            MATCH SCORE
        </span>

        <span class="hero-chip">
            ELIGIBILITY
        </span>

        <span class="hero-chip">
            OPPORTUNITY BOOSTER
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
        01 / AI IMPORT
    </div>

    <div class="section-title">
        PASTE ANY<br>
        OPPORTUNITY.
    </div>

    <div class="section-copy">

        Copy an opportunity from Facebook, Telegram,
        a website, email or another source. It can be
        Kurdish, Arabic, English or mixed. The AI converts
        the announcement into structured requirements.

    </div>

</div>
"""
)


announcement_text = st.text_area(
    "Opportunity announcement",
    height=230,
    placeholder=(
        "Paste a scholarship, competition, training, "
        "internship, fellowship or grant announcement..."
    )
)


if st.button(
    "ANALYZE WITH AI →",
    use_container_width=True
):

    if not announcement_text.strip():

        st.warning(
            "Please paste an opportunity announcement first."
        )

    else:

        with st.spinner(
            "AI is understanding the announcement..."
        ):

            try:

                extracted = extract_opportunity(
                    announcement_text
                )

                extracted["status"] = normalize_status(
                    extracted.get("status")
                )

                extracted["open_date"] = normalize_open_date(
                    extracted.get("open_date"),
                    announcement_text,
                )

                extracted["deadline"] = normalize_deadline(
                    (
                        extracted.get("close_date")
                        or extracted.get("deadline")
                    ),
                    announcement_text,
                )

                st.session_state.ai_imported_opportunity = (
                    extracted
                )

                st.success(
                    "AI extraction completed successfully."
                )

            except Exception as error:

                st.error(
                    f"AI extraction failed: {error}"
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
                "AI Imported Opportunity"
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
        AI EXTRACTION / COMPLETE
    </div>

    <div class="card-title">
        {title_safe}
    </div>

    <div class="card-org">
        {org_safe}
    </div>

    <div class="ai-tag">
        GENERATED FROM UNSTRUCTURED TEXT
    </div>

</div>
"""
    )


    a1, a2, a3, a4 = st.columns(4)


    with a1:

        st.metric(
            "Type",
            extracted.get(
                "type",
                ""
            )
        )


    with a2:

        st.metric(
            "Status",
            extracted.get(
                "status",
                ""
            )
        )


    with a3:

        st.metric(
            "Location",
            extracted.get(
                "location",
                ""
            )
        )


    with a4:

        st.metric(
            "Deadline",
            extracted.get(
                "deadline",
                ""
            ) or "Not stated"
        )


    ex1, ex2 = st.columns(
        2,
        gap="large"
    )


    with ex1:

        st.markdown(
            "### ELIGIBILITY DATA"
        )

        st.write(
            "**Education:**",
            extracted.get(
                "education",
                "Any"
            )
        )

        education_rule = extracted.get(
            "education_rule",
            "minimum"
        )

        st.write(
            "**Education rule:**",
            (
                "Exact target level"
                if education_rule == "exact"
                else "Minimum level"
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
                "**Age:**",
                (
                    f"{minimum_age if minimum_age is not None else 'No minimum'}"
                    f" — "
                    f"{maximum_age if maximum_age is not None else 'No maximum'}"
                )
            )

        residency = extracted.get(
            "residency_requirement",
            ""
        )

        st.write(
            "**Residency:**",
            residency or "None detected"
        )

        applicant_types = extracted.get(
            "eligible_applicant_types",
            []
        )

        st.write(
            "**Applicant type:**",
            (
                ", ".join(applicant_types)
                if applicant_types
                else extracted.get(
                    "applicant_type",
                    ""
                )
                or "Not stated"
            )
        )

        minimum_grade = extracted.get(
            "minimum_grade",
            0
        )

        if minimum_grade:

            st.write(
                "**Minimum grade:**",
                f"{minimum_grade}%"
            )

        required_work = extracted.get(
            "minimum_work_experience_years",
            0
        )

        if required_work:

            st.write(
                "**Work experience:**",
                f"{required_work} years"
            )


    with ex2:

        st.markdown(
            "### PROFILE SIGNALS"
        )

        st.write(
            "**Languages:**",
            ", ".join(
                extracted.get(
                    "languages",
                    []
                )
            ) or "None specified"
        )

        st.write(
            "**Interests:**",
            ", ".join(
                extracted.get(
                    "interests",
                    []
                )
            ) or "None specified"
        )

        st.write(
            "**Skills:**",
            ", ".join(
                extracted.get(
                    "skills",
                    []
                )
            ) or "None specified"
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
            "**Required documents:**",
            (
                ", ".join(required_docs)
                if required_docs
                else "None detected"
            )
        )


    with st.expander(
        "VIEW RAW AI DATA"
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
        02 / CLOUD PROFILE
    </div>

    <div class="section-title">
        BUILD YOUR<br>
        SIGNAL.
    </div>

    <div class="section-copy">

        Your profile is saved in Supabase. HelAI uses your
        education, residence, languages, skills, interests,
        experience and application documents as matching
        signals.

    </div>

</div>

<div class="explainer">

    <strong>MATCH</strong> measures relevance.
    <strong>ELIGIBILITY</strong> checks mandatory rules.
    <strong>READINESS</strong> checks whether the documents
    needed to apply are already available.

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
            "Full Name",
            value=(
                saved_profile.get("full_name")
                or ""
            ),
            placeholder="Your full name",
        )

        date_of_birth = st.date_input(
            "Date of Birth",
            value=saved_dob,
            min_value=date(1940, 1, 1),
            max_value=date.today(),
        )

        if date_of_birth:

            st.caption(
                f"Age used for matching: "
                f"{calculate_age(date_of_birth)}"
            )

        nationality = st.text_input(
            "Nationality",
            value=(
                saved_profile.get("nationality")
                or ""
            ),
            placeholder="Example: Iraqi",
        )

        country_of_residence = st.text_input(
            "Country of Residence",
            value=(
                saved_profile.get("country_of_residence")
                or ""
            ),
            placeholder="Example: Iraq",
        )

        city = st.selectbox(
            "City / Residence",
            city_options,
            index=safe_index(
                city_options,
                saved_profile.get("city"),
                0,
            ),
        )

        education = st.selectbox(
            "Highest Education Level",
            education_options,
            index=safe_index(
                education_options,
                saved_profile.get("education"),
                0,
            ),
        )

        field_of_study = st.text_input(
            "Field of Study",
            value=(
                saved_profile.get("field_of_study")
                or ""
            ),
            placeholder="Example: Computer Science",
        )

        grade = st.number_input(
            "Graduation Average / Percentage",
            min_value=0.0,
            max_value=100.0,
            value=float(
                saved_profile.get("grade")
                or 0.0
            ),
            step=0.1,
        )

        work_experience_years = st.number_input(
            "Years of Work Experience",
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
            "Languages",
            language_options,
            default=safe_multiselect_defaults(
                language_options,
                saved_profile.get("languages"),
            ),
        )

        skills = st.multiselect(
            "Skills",
            skill_options,
            default=safe_multiselect_defaults(
                skill_options,
                saved_profile.get("skills"),
            ),
        )

        interests = st.multiselect(
            "Areas of Interest",
            interest_options,
            default=safe_multiselect_defaults(
                interest_options,
                saved_profile.get("interests"),
            ),
        )

        opportunity_types = st.multiselect(
            "Opportunity Types",
            opportunity_type_options,
            default=safe_multiselect_defaults(
                opportunity_type_options,
                saved_profile.get(
                    "opportunity_types"
                ),
            ),
        )

        preferred_language = st.selectbox(
            "Preferred HelAI Language",
            preferred_language_options,
            index=safe_index(
                preferred_language_options,
                saved_profile.get(
                    "preferred_language"
                ),
                0,
            ),
        )

        email_notifications = st.checkbox(
            "Email me when HelAI finds relevant opportunities",
            value=bool(
                saved_profile.get(
                    "email_notifications",
                    True,
                )
            ),
        )

        st.markdown(
            "### DOCUMENTS"
        )

        has_passport = st.checkbox(
            "I have a valid passport",
            value=bool(
                saved_profile.get(
                    "has_passport",
                    False,
                )
            ),
        )

        has_ielts = st.checkbox(
            "I have IELTS / English certificate",
            value=bool(
                saved_profile.get(
                    "has_ielts",
                    False,
                )
            ),
        )

        has_portfolio = st.checkbox(
            "I have a portfolio",
            value=bool(
                saved_profile.get(
                    "has_portfolio",
                    False,
                )
            ),
        )

        has_cv = st.checkbox(
            "I have a CV",
            value=bool(
                saved_profile.get(
                    "has_cv",
                    False,
                )
            ),
        )


    submitted = st.form_submit_button(
        "SAVE PROFILE + ANALYZE →",
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
            "Please enter your full name."
        )

    elif date_of_birth is None:

        st.warning(
            "Please enter your date of birth."
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
            "Saving your HelAI cloud profile..."
        ):

            save_result = update_profile(
                access_token=st.session_state.access_token,
                refresh_token=st.session_state.refresh_token,
                profile_data=cloud_profile_data,
            )


        if not save_result["success"]:

            st.error(
                "HelAI could not save your profile: "
                f"{save_result['message']}"
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
                "Profile saved to Supabase successfully."
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
                "applicant_type": APPLICANT_INDIVIDUAL,
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
                ] = "AI imported announcement"

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
                    normalize_status(
                        item[0].get(
                            "status"
                        )
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
        03 / OPPORTUNITY MAP
    </div>

    <div class="section-title">
        YOUR BEST<br>
        OPTIONS.
    </div>

    <div class="section-copy">

        The system separates relevance from qualification.
        A highly relevant opportunity can still show as
        not eligible when a mandatory requirement is missing.

    </div>

</div>
"""
    )


    open_count = sum(
        1
        for opportunity, result in results
        if normalize_status(
            opportunity.get("status")
        ) == "Open"
    )


    eligible_count = sum(
        1
        for opportunity, result in results
        if (
            normalize_status(
                opportunity.get("status")
            ) == "Open"
            and result["eligible"]
        )
    )


    ready_count = sum(
        1
        for opportunity, result in results
        if (
            normalize_status(
                opportunity.get("status")
            ) == "Open"
            and result["eligible"]
            and result["readiness"] == 100
        )
    )


    best_score = max(
        (
            result["score"]
            for opportunity, result in results
            if normalize_status(
                opportunity.get("status")
            ) == "Open"
        ),
        default=0
    )


    m1, m2, m3, m4 = st.columns(4)


    with m1:

        st.metric(
            "Open Opportunities",
            open_count
        )


    with m2:

        st.metric(
            "Eligible Now",
            eligible_count
        )


    with m3:

        st.metric(
            "Ready to Apply",
            ready_count
        )


    with m4:

        st.metric(
            "Best Match",
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
                    "Untitled Opportunity"
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


        source_name = (
            opportunity.get("source_name")
            or opportunity.get("source")
            or "Unknown source"
        )

        source_url = (
            opportunity.get("source_url")
            or ""
        )

        source_name_safe = html.escape(
            str(source_name)
        )


        opportunity_status = normalize_status(
            opportunity.get("status")
        )

        if opportunity_status == "Closed":

            card_class = "card card-red"


        elif (
            opportunity_status == "Open"
            and
            result["eligible"]
            and result["readiness"] == 100
        ):

            card_class = "card card-green"


        elif (
            opportunity_status == "Open"
            and result["eligible"]
        ):

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
                'AI IMPORTED'
                '</div>'
            )


        st.html(
            f"""
<div class="{card_class}">

    <div class="card-number">
        {index:02d} / OPPORTUNITY
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


        source_html = f"""
<div class="chips" style="margin-top: 12px;">
    <span class="chip chip-blue">
        SOURCE: {source_name_safe}
    </span>
</div>
"""

        st.html(source_html)

        if source_url:
            st.link_button(
                "VIEW ORIGINAL SOURCE",
                source_url,
                use_container_width=False,
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
                "#### ABOUT THIS OPPORTUNITY"
            )


            st.write(
                summary_text
            )


        c1, c2, c3, c4 = st.columns(4)


        with c1:

            st.metric(
                "Match",
                f"{result['score']}%"
            )


        with c2:

            st.metric(
                "Eligibility",
                (
                    "Eligible"
                    if result["eligible"]
                    else "Not Eligible"
                )
            )


        with c3:

            st.metric(
                "Readiness",
                f"{result['readiness']}%"
            )


        with c4:

            st.metric(
                "Deadline",
                opportunity.get(
                    "deadline",
                    ""
                ) or "Not stated"
            )


        st.progress(
            result["score"] / 100,
            text=(
                f"Match relevance · "
                f"{result['score']}%"
            )
        )


        st.progress(
            result["readiness"] / 100,
            text=(
                f"Application readiness · "
                f"{result['readiness']}%"
            )
        )


        status = opportunity.get(
            "status",
            ""
        )


        normalized_status = normalize_status(status)

        status_class = (
            "chip-green"
            if normalized_status == "Open"
            else (
                "chip-yellow"
                if normalized_status == "Upcoming"
                else "chip-red"
            )
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
        {html.escape(str(normalized_status))}
    </span>

    <span class="chip {eligibility_class}">
        {"ELIGIBLE" if result["eligible"] else "NOT ELIGIBLE"}
    </span>

    <span class="chip {readiness_class}">
        READY {result["readiness"]}%
    </span>

</div>
"""
        )


        if (
            result["eligible"]
            and result["readiness"] == 100
        ):

            st.success(
                "You appear eligible and ready to apply."
            )


        elif result["eligible"]:

            st.info(
                "You appear eligible, but there are "
                "application-readiness tasks remaining."
            )


        else:

            st.warning(
                "This opportunity may be relevant, "
                "but you currently miss one or more "
                "mandatory eligibility requirements."
            )


        why_col, eligibility_col, readiness_col = (
            st.columns(
                3,
                gap="large"
            )
        )


        with why_col:

            st.markdown(
                "### WHY IT FITS"
            )

            if result["reasons"]:

                for reason in result["reasons"]:

                    st.write(
                        f"＋ {reason}"
                    )

            else:

                st.caption(
                    "No positive matching signals."
                )


        with eligibility_col:

            st.markdown(
                "### ELIGIBILITY"
            )

            if result["eligibility_gaps"]:

                for issue in result[
                    "eligibility_gaps"
                ]:

                    st.write(
                        f"— {issue}"
                    )

            else:

                st.success(
                    "No mandatory eligibility gaps."
                )


        with readiness_col:

            st.markdown(
                "### READINESS"
            )

            if result["readiness_gaps"]:

                for issue in result[
                    "readiness_gaps"
                ]:

                    st.write(
                        f"— {issue}"
                    )

            else:

                st.success(
                    "No tracked document gaps."
                )


        with st.expander(
            "VIEW OPPORTUNITY DETAILS"
        ):

            st.write(
                "**Type:**",
                opportunity.get(
                    "type",
                    ""
                )
            )

            st.write(
                "**Location:**",
                opportunity.get(
                    "location",
                    ""
                )
            )

            st.write(
                "**Education:**",
                opportunity.get(
                    "education",
                    "Any"
                )
            )

            st.write(
                "**Education rule:**",
                opportunity.get(
                    "education_rule",
                    "minimum"
                )
            )

            residency = opportunity.get(
                "residency_requirement",
                ""
            )

            st.write(
                "**Residency requirement:**",
                residency or "None specified"
            )

            notes = opportunity.get(
                "notes",
                ""
            )

            if notes:

                st.write(
                    "**Notes:**",
                    notes
                )

            source = opportunity.get(
                "source_name",
                ""
            ) or opportunity.get("source", "")

            if source:

                st.write(
                    "**Source:**",
                    source
                )

            if source_url:

                st.link_button(
                    "VIEW ORIGINAL SOURCE",
                    source_url,
                )


        st.markdown("---")


    # =====================================================
    # SECTION 04 — BOOSTER
    # =====================================================

    st.html(
        """
<div class="section">

    <div class="section-index">
        04 / OPPORTUNITY BOOSTER
    </div>

    <div class="section-title">
        UNLOCK<br>
        MORE.
    </div>

    <div class="section-copy">

        Opportunity Booster simulates improvements to your
        profile and identifies which actions could unlock
        more opportunities or increase application readiness.

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
                str(
                    label
                )
            )


            st.html(
                f"""
<div class="card">

    <div class="card-number">
        BOOST / {rank:02d}
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
                    "Unlocked",
                    data["unlocked"]
                )


            with b2:

                st.metric(
                    "Improved",
                    data["improved"]
                )


            with b3:

                st.metric(
                    "Match Gain",
                    f"+{data['score_gain']}"
                )


            with b4:

                st.metric(
                    "Readiness Gain",
                    f"+{data['readiness_gain']}"
                )


    else:

        st.success(
            "Your profile already covers all "
            "improvements tested by this prototype."
        )


# =========================================================
# FOOTER
# =========================================================

st.html(
    """
<div class="footer">

    <div>
        HELAI / PROTOTYPE
    </div>

    <div>
        AI OLYMPIAD KURDISTAN / 2026
    </div>

</div>
"""
)
