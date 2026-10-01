import streamlit as st
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
from helai_ui import (
    inject_global_styles,
    profile_group,
    render_booster_card,
    render_booster_intro,
    render_empty_state,
    render_kpis,
    render_opportunity_card,
    result_kpis,
    result_sort_key,
    section_header,
)
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
    page_title="HelAI",
    page_icon="H",
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

inject_global_styles()


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
    st.html('<div class="auth-page-marker"></div>')

    auth_intro, auth_panel = st.columns([1.12, 0.88], gap="large")

    with auth_intro:
        st.html(
            """
            <section class="auth-shell">
                <div class="auth-wordmark">HELAI</div>
                <div class="auth-eyebrow">Opportunity intelligence</div>
                <h1 class="auth-title">Your AI agent for global opportunities.</h1>
                <div class="auth-copy">
                    Discover opportunities, understand eligibility, and prepare stronger
                    applications with one multilingual profile.
                </div>
                <div class="auth-features">
                    <span class="auth-feature">AI Opportunity Discovery</span>
                    <span class="auth-feature">Smart Eligibility</span>
                    <span class="auth-feature">Personalized Matching</span>
                    <span class="auth-feature">Kurdish / English</span>
                    <span class="auth-feature">Application Readiness</span>
                </div>
            </section>
            """
        )

    with auth_panel:
        st.html(
            """
            <div class="auth-panel-intro">
                <h2 class="auth-panel-title">Welcome to HelAI</h2>
                <div class="auth-panel-copy">Sign in to continue or create your secure cloud profile.</div>
            </div>
            """
        )

        sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create account"])

        with sign_in_tab:
            with st.form("helai_sign_in_form_v2"):
                login_email = st.text_input(
                    "Email address",
                    placeholder="you@example.com",
                    key="login_email_v2",
                )
                login_password = st.text_input(
                    "Password",
                    type="password",
                    key="login_password_v2",
                )
                login_submitted = st.form_submit_button(
                    "Sign in to HelAI",
                    use_container_width=True,
                )

            if login_submitted:
                if not login_email.strip() or not login_password:
                    st.warning("Enter your email and password.")
                else:
                    with st.spinner("Signing in securely..."):
                        login_result = sign_in_user(
                            email=login_email.strip(),
                            password=login_password,
                        )

                    if login_result["success"]:
                        st.session_state.access_token = login_result["access_token"]
                        st.session_state.refresh_token = login_result["refresh_token"]
                        st.session_state.auth_user = login_result["user"]
                        profile_result = get_profile(
                            access_token=login_result["access_token"],
                            refresh_token=login_result["refresh_token"],
                        )
                        if profile_result["success"]:
                            st.session_state.cloud_profile = profile_result["profile"]
                        st.success("Signed in successfully.")
                        st.rerun()
                    else:
                        st.error(login_result["message"])

        with sign_up_tab:
            with st.form("helai_sign_up_form_v2"):
                signup_name = st.text_input(
                    "Full name",
                    placeholder="Your full name",
                    key="signup_name_v2",
                )
                signup_email = st.text_input(
                    "Email address",
                    placeholder="you@example.com",
                    key="signup_email_v2",
                )
                signup_password = st.text_input(
                    "Password",
                    type="password",
                    key="signup_password_v2",
                    help="Use at least 6 characters.",
                )
                signup_password_confirm = st.text_input(
                    "Confirm password",
                    type="password",
                    key="signup_password_confirm_v2",
                )
                signup_submitted = st.form_submit_button(
                    "Create HelAI account",
                    use_container_width=True,
                )

            if signup_submitted:
                if not signup_name.strip():
                    st.warning("Enter your full name.")
                elif not signup_email.strip():
                    st.warning("Enter your email.")
                elif len(signup_password) < 6:
                    st.warning("Use a password with at least 6 characters.")
                elif signup_password != signup_password_confirm:
                    st.warning("The two passwords do not match.")
                else:
                    with st.spinner("Creating your secure HelAI account..."):
                        signup_result = sign_up_user(
                            email=signup_email.strip(),
                            password=signup_password,
                            full_name=signup_name.strip(),
                        )

                    if signup_result["success"]:
                        signup_session = signup_result.get("session")
                        if signup_session:
                            st.session_state.access_token = signup_session.access_token
                            st.session_state.refresh_token = signup_session.refresh_token
                            st.session_state.auth_user = {
                                "id": signup_result["user_id"],
                                "email": signup_result["email"],
                            }
                            load_cloud_profile()
                            st.success("Account created and signed in.")
                            st.rerun()
                        else:
                            st.success(signup_result["message"])
                            st.info(
                                "After confirming your email, return here and sign in."
                            )
                    else:
                        st.error(signup_result["message"])

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

account_email = ""
if st.session_state.auth_user:
    account_email = st.session_state.auth_user.get("email") or ""
if not account_email and st.session_state.cloud_profile:
    account_email = st.session_state.cloud_profile.get("email") or ""

account_name = "HelAI user"
profile_complete = False
if st.session_state.cloud_profile:
    account_name = st.session_state.cloud_profile.get("full_name") or account_name
    profile_complete = bool(st.session_state.cloud_profile.get("profile_complete", False))

initials = "".join(
    part[0].upper() for part in account_name.split()[:2] if part
) or "HA"

source_status = load_source_status()
source_rows = []
for source in get_source_catalog():
    status = source_status.get(source["key"], {})
    label = source["source_name"]
    last_status = status.get("last_status", "active")
    discovered = status.get("discovered")
    imported = status.get("imported")
    run_detail = str(last_status).replace("_", " ").title()
    if discovered is not None and imported is not None:
        run_detail = f"{discovered} found · {imported} imported"
    source_health = "danger" if str(last_status).lower() in {"error", "failed"} else ""
    source_rows.append(
        f"""
        <div class="source-row">
            <span class="source-dot {source_health}"></span>
            <div><div class="source-name">{html.escape(label)}</div>
            <div class="source-meta">{html.escape(run_detail)}</div></div>
        </div>
        """
    )

with st.sidebar:

    st.html(
        f"""
        <div class="sidebar-brand">
            <div class="brand-mark">H</div>
            <div><div class="brand-name">HelAI</div>
            <div class="brand-subtitle">Opportunity Intelligence</div></div>
        </div>
        <div class="sidebar-label">Account</div>
        <div class="account-card">
            <div class="account-avatar">{html.escape(initials)}</div>
            <div><div class="account-name">{html.escape(account_name)}</div>
            <div class="account-email">{html.escape(account_email)}</div>
            <div class="account-status">{"Cloud profile ready" if profile_complete else "Profile setup in progress"}</div></div>
        </div>
        <div class="sidebar-label">Workspace</div>
        <nav class="side-nav">
            <a class="side-nav-row" href="#ai-import"><span class="side-nav-number">01</span>AI Import</a>
            <a class="side-nav-row" href="#cloud-profile"><span class="side-nav-number">02</span>Cloud Profile</a>
            <a class="side-nav-row" href="#opportunity-map"><span class="side-nav-number">03</span>Opportunity Map</a>
            <a class="side-nav-row" href="#opportunity-booster"><span class="side-nav-number">04</span>Opportunity Booster</a>
        </nav>
        <div class="sidebar-label">Opportunity sources</div>
        <div class="source-list">{"".join(source_rows)}</div>
        """
    )

    st.html(
        f'<div class="source-meta" style="padding: 10px 4px 0;">{len(opportunities)} opportunities loaded</div>'
    )

    if st.button(
        "Sign out",
        use_container_width=True,
        key="helai_sign_out",
        type="secondary",
        icon=":material/logout:",
    ):
        sign_out_user(
            access_token=st.session_state.access_token,
            refresh_token=st.session_state.refresh_token,
        )
        clear_auth_state()
        st.rerun()


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
    """
    <section class="product-hero">
        <div class="section-eyebrow">AI-powered global opportunity intelligence</div>
        <h1 class="hero-title">Find opportunities<br><span class="gradient-word">built for you.</span></h1>
        <div class="hero-copy">
            HelAI discovers global opportunities, understands their requirements,
            and turns your profile into clear eligibility and readiness guidance.
        </div>
        <div class="hero-chips">
            <span class="hero-chip">Multilingual AI</span>
            <span class="hero-chip">Cloud Profile</span>
            <span class="hero-chip">Match Score</span>
            <span class="hero-chip">Eligibility</span>
            <span class="hero-chip">Readiness</span>
        </div>
    </section>
    """
)

# =========================================================
# SECTION 01 — AI IMPORT
# =========================================================

section_header(
    "01",
    "AI Import",
    "Paste any opportunity.",
    "Add an announcement in Kurdish, Arabic, English, or mixed text. HelAI turns it into structured requirements.",
    "ai-import",
)

with st.container(border=True):
    st.html(
        """
        <div class="workspace-heading"><span class="spark">✦</span>AI extraction workspace</div>
        <div class="workspace-copy">Paste the complete announcement for the most accurate eligibility and deadline extraction.</div>
        """
    )
    announcement_text = st.text_area(
        "Opportunity announcement",
        height=230,
        placeholder=(
            "Paste a scholarship, competition, training, "
            "internship, fellowship or grant announcement..."
        ),
        help="HelAI accepts Kurdish, Arabic, English, and mixed-language announcements.",
    )
    analyze_requested = st.button(
        "Analyze with AI",
        use_container_width=True,
        type="primary",
    )


if analyze_requested:

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

section_header(
    "02",
    "Cloud Profile",
    "Build your profile.",
    "Create one reusable profile for personalized matching, eligibility checks, and application readiness.",
    "cloud-profile",
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

st.html(
    """
    <div class="profile-callout">
        <span>◎</span>
        <span><strong>How HelAI uses your profile</strong><br>Match measures relevance, eligibility checks mandatory rules, and readiness tracks application documents.</span>
    </div>
    """
)


with st.form(
    "profile_form"
):

    left, right = st.columns(
        2,
        gap="large"
    )


    with left:

        profile_group(
            "Personal",
            "Basic identity and residence details used for eligibility checks.",
        )

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

        profile_group(
            "Education",
            "Your current academic level, subject area, and result.",
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

        profile_group(
            "Professional",
            "Experience information used when an opportunity sets a minimum.",
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

        profile_group(
            "Languages & Skills",
            "Add the capabilities HelAI should use as matching signals.",
        )

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

        profile_group(
            "Interests & Preferences",
            "Choose the themes and opportunity types you want to prioritize.",
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

        profile_group(
            "Notifications",
            "Control whether eligible high-quality matches may enter the email queue.",
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

        profile_group(
            "Documents",
            "Mark the application materials you already have ready.",
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
        "Save profile and analyze",
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
                key=result_sort_key,
                reverse=True
            )


            run_matching = True


if run_matching:

# =====================================================
    # SECTION 03
    # =====================================================

    st.markdown("---")

    section_header(
        "03",
        "Opportunity Map",
        "Your best options.",
        "Compare relevance, qualification, and readiness without mixing them into a single score.",
        "opportunity-map",
    )


    kpis = result_kpis(results)

    render_kpis(
        [
            ("Open opportunities", kpis["open"], "Currently actionable", "info"),
            ("Eligible now", kpis["eligible"], "Mandatory rules met", "success"),
            ("Ready to apply", kpis["ready"], "Documents complete", "violet"),
            ("Best match", f"{kpis['best_score']}%", "Highest relevance score", "accent"),
        ]
    )

    if not results:
        render_empty_state(
            "No matches yet",
            "Adjust your profile or import an opportunity to generate a new set of relevance, eligibility, and readiness results.",
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

        active_language = str(
            (st.session_state.cloud_profile or {}).get(
                "preferred_language",
                "English",
            )
        ).strip()
        render_opportunity_card(
            opportunity,
            result,
            index,
            active_language,
        )


    # =====================================================
    # SECTION 04 — BOOSTER
    # =====================================================

    section_header(
        "04",
        "Opportunity Booster",
        "Improve your readiness.",
        "See practical profile improvements and the matches or application readiness they may unlock.",
        "opportunity-booster",
    )

    improvements = analyze_improvements(
        profile,
        matching_opportunities
    )

    render_booster_intro()


    if improvements:

        for rank, (
            label,
            data
        ) in enumerate(
            improvements[:5],
            start=1
        ):

            render_booster_card(label, data, rank)


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
