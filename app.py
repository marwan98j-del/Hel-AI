import streamlit as st
import html
from datetime import date, datetime, timezone

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
from helai_i18n import (
    format_date,
    format_number,
    format_percent,
    select_language,
    t,
    t_value,
)
from helai_ui import (
    SUN_ICON,
    filter_results,
    inject_global_styles,
    language_switcher,
    latin,
    profile_completion,
    profile_group,
    render_alerts_card,
    render_booster_rail,
    render_deadlines_rail,
    render_empty_state,
    render_header,
    render_hero,
    result_kpis,
    result_sort_key,
    section_header,
    sign_in_intro_html,
    status_label,
    ticket_html,
)
from auth_service import (
    create_authenticated_client,
    sign_up_user,
    sign_in_user,
    get_profile,
    update_profile,
    sign_out_user,
)
from telegram_link import (
    LINK_CODE_MINUTES,
    bot_link,
    code_is_pending,
    create_link_code,
    disconnect as disconnect_telegram,
    load_connection as load_telegram_connection,
)

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="HelAI",
    page_icon="H",
    layout="wide",
    # "auto": expanded on desktop, collapsed on phones.
    initial_sidebar_state="auto"
)


# =========================================================
# LANGUAGE
# Order: session choice (switcher or ?lang=) -> saved profile
# preference (read only) -> Kurdish Sorani.
# =========================================================

lang = select_language(
    st.session_state,
    st.query_params.get("lang"),
    st.session_state.get("cloud_profile"),
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
    st.error(t("app.load_error", error=error))
    st.stop()


# =========================================================
# VISUAL DESIGN
# =========================================================

inject_global_styles(lang)


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


def build_match_profile(saved):
    """Matcher input from a saved profile; None until it can be matched."""
    date_of_birth = parse_saved_date((saved or {}).get("date_of_birth"))
    if not saved or not saved.get("profile_complete") or not date_of_birth:
        return None

    return {
        "full_name": str(saved.get("full_name") or "").strip(),
        "city": saved.get("city") or "",
        "age": calculate_age(date_of_birth),
        "education": saved.get("education") or "Any",
        "field_of_study": str(saved.get("field_of_study") or "").strip(),
        "grade": float(saved.get("grade") or 0),
        "languages": list(saved.get("languages") or []),
        "skills": list(saved.get("skills") or []),
        "interests": list(saved.get("interests") or []),
        "opportunity_types": list(saved.get("opportunity_types") or []),
        "has_passport": bool(saved.get("has_passport")),
        "has_ielts": bool(saved.get("has_ielts")),
        "has_portfolio": bool(saved.get("has_portfolio")),
        "has_cv": bool(saved.get("has_cv")),
        "work_experience_years": float(saved.get("work_experience_years") or 0),
        "applicant_type": APPLICANT_INDIVIDUAL,
    }


def option_label(prefix):
    """format_func that translates a stored English option for display."""
    return lambda value: t_value(prefix, value, lang)


def esc(key, **kwargs):
    return html.escape(t(key, **kwargs))


def current_user_id():
    return (
        (st.session_state.auth_user or {}).get("id")
        or (st.session_state.cloud_profile or {}).get("id")
    )


def user_client():
    return create_authenticated_client(
        st.session_state.access_token,
        st.session_state.refresh_token,
    )


# =========================================================
# AUTHENTICATION GATE
# =========================================================

if not st.session_state.access_token:
    st.html('<div class="auth-page-marker"></div>')

    auth_intro, auth_panel = st.columns([1.18, 0.82], gap="large")

    with auth_intro:
        st.html(sign_in_intro_html(lang))

    with auth_panel:
        language_switcher("helai_lang_switch_auth")

        st.html(
            f"""
            <h2 class="auth-panel-title">{esc("auth.welcome")}</h2>
            <div class="auth-panel-copy">{esc("auth.welcome_copy")}</div>
            """
        )

        auth_mode = st.segmented_control(
            t("sidebar.account"),
            ["sign_in", "sign_up"],
            format_func=lambda mode: t("auth.tab_sign_in" if mode == "sign_in" else "auth.tab_sign_up"),
            default="sign_in",
            required=True,
            key="helai_auth_mode",
            label_visibility="collapsed",
            width="stretch",
        )

        if auth_mode != "sign_up":
            with st.form("helai_sign_in_form_v2"):
                login_email = st.text_input(
                    t("auth.email"),
                    placeholder="you@example.com",
                    key="login_email_v2",
                )
                login_password = st.text_input(
                    t("auth.password"),
                    type="password",
                    key="login_password_v2",
                )
                login_submitted = st.form_submit_button(
                    t("auth.sign_in_button"),
                    use_container_width=True,
                )

            if login_submitted:
                if not login_email.strip() or not login_password:
                    st.warning(t("auth.enter_email_password"))
                else:
                    with st.spinner(t("auth.signing_in")):
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
                        st.success(t("auth.signed_in"))
                        st.rerun()
                    else:
                        st.error(login_result["message"])

        else:
            with st.form("helai_sign_up_form_v2"):
                signup_name = st.text_input(
                    t("auth.full_name"),
                    placeholder=t("auth.full_name_placeholder"),
                    key="signup_name_v2",
                )
                signup_email = st.text_input(
                    t("auth.email"),
                    placeholder="you@example.com",
                    key="signup_email_v2",
                )
                signup_password = st.text_input(
                    t("auth.password"),
                    type="password",
                    key="signup_password_v2",
                    help=t("auth.password_help"),
                )
                signup_password_confirm = st.text_input(
                    t("auth.confirm_password"),
                    type="password",
                    key="signup_password_confirm_v2",
                )
                signup_submitted = st.form_submit_button(
                    t("auth.sign_up_button"),
                    use_container_width=True,
                )

            if signup_submitted:
                if not signup_name.strip():
                    st.warning(t("auth.enter_full_name"))
                elif not signup_email.strip():
                    st.warning(t("auth.enter_email"))
                elif len(signup_password) < 6:
                    st.warning(t("auth.password_too_short"))
                elif signup_password != signup_password_confirm:
                    st.warning(t("auth.password_mismatch"))
                else:
                    with st.spinner(t("auth.creating_account")):
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
                            st.success(t("auth.account_created"))
                            st.rerun()
                        else:
                            st.success(signup_result["message"])
                            st.info(t("auth.confirm_then_sign_in"))
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

        # The saved preference may now apply (no explicit choice yet);
        # rerun so styles and text use the same language.
        if select_language(
            st.session_state,
            st.query_params.get("lang"),
            st.session_state.cloud_profile,
        ) != lang:
            st.rerun()

    else:

        st.warning(t("auth.profile_load_failed"))


saved_profile = (
    st.session_state.cloud_profile
    or {}
)


# =========================================================
# MATCH RESULTS (in memory, from the saved profile)
# =========================================================

profile = build_match_profile(saved_profile)
matching_opportunities = list(opportunities)

if st.session_state.ai_imported_opportunity:

    ai_opportunity = dict(
        st.session_state.ai_imported_opportunity
    )
    ai_opportunity["source"] = "AI imported announcement"
    ai_opportunity["is_ai_imported"] = True
    matching_opportunities.append(ai_opportunity)

results = []
improvements = []

if profile:

    for opportunity in matching_opportunities:
        results.append(
            (
                opportunity,
                calculate_match(profile, opportunity),
            )
        )

    results.sort(
        key=result_sort_key,
        reverse=True
    )

    improvements = analyze_improvements(
        profile,
        matching_opportunities
    )

kpis = result_kpis(results)


# =========================================================
# SIDEBAR
# =========================================================

account_email = ""
if st.session_state.auth_user:
    account_email = st.session_state.auth_user.get("email") or ""
if not account_email and saved_profile:
    account_email = saved_profile.get("email") or ""

account_name = saved_profile.get("full_name") or t("sidebar.default_user")
completion = profile_completion(saved_profile)

initials = "".join(
    part[0].upper() for part in account_name.split()[:2] if part
) or "HA"

source_status = load_source_status()
source_catalog = get_source_catalog()
source_rows = []
for source in source_catalog:
    status = source_status.get(source["key"], {})
    label = source["source_name"]
    last_status = str(status.get("last_status", "active")).lower()
    discovered = status.get("discovered")
    imported = status.get("imported")
    run_detail = t_value("source_status", last_status, lang)
    if run_detail == last_status:
        run_detail = last_status.replace("_", " ").title()
    if discovered is not None and imported is not None:
        run_detail = t(
            "sidebar.source_run",
            discovered=format_number(discovered),
            imported=format_number(imported),
        )
    source_health = "danger" if last_status in {"error", "failed"} else ""
    source_rows.append(
        f"""
        <div class="source-row">
            <span class="source-dot {source_health}"></span>
            <div><div class="source-name">{latin(label)}</div>
            <div class="source-meta">{html.escape(run_detail)}</div></div>
        </div>
        """
    )

with st.sidebar:

    st.html(
        f"""
        <div class="sidebar-brand">
            {SUN_ICON}
            <div><div class="brand-name">{latin("HelAI")}</div>
            <div class="brand-subtitle">{esc("common.opportunity_intelligence")}</div></div>
        </div>
        <div class="sidebar-label">{esc("sidebar.account")}</div>
        <div class="account-card">
            <div class="account-row">
                <div class="account-avatar">{html.escape(initials)}</div>
                <div><div class="account-name" dir="auto">{html.escape(account_name)}</div>
                <div class="account-email">{latin(account_email)}</div></div>
            </div>
            <div class="account-status">{esc("sidebar.profile_complete", pct=format_percent(completion))}</div>
            <div class="progress-track"><div class="progress-fill" style="width: {completion}%;"></div></div>
        </div>
        <div class="sidebar-label">{esc("sidebar.workspace")}</div>
        <nav class="side-nav">
            <a class="side-nav-row" href="#opportunity-map"><span class="side-nav-number">{format_number("01")}</span>{esc("nav.dashboard")}</a>
            <a class="side-nav-row" href="#opportunity-booster"><span class="side-nav-number">{format_number("02")}</span>{esc("nav.opportunity_booster")}</a>
            <a class="side-nav-row" href="#ai-import"><span class="side-nav-number">{format_number("03")}</span>{esc("nav.ai_import")}</a>
            <a class="side-nav-row" href="#cloud-profile"><span class="side-nav-number">{format_number("04")}</span>{esc("nav.cloud_profile")}</a>
        </nav>
        <div class="sidebar-label">{esc("sidebar.sources")}</div>
        <div class="source-list">{"".join(source_rows)}</div>
        """
    )

    st.html(
        f'<div class="source-meta" style="padding: 10px 4px 0;">{esc("sidebar.opportunities_loaded", count=format_number(len(opportunities)))}</div>'
    )

    if st.button(
        t("sidebar.sign_out"),
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
# HEADER AND HERO
# =========================================================

search_query = render_header(
    account_name,
    lang,
    "helai_search",
    "helai_lang_switch_header",
)

if st.session_state.pop("helai_profile_saved", False):
    st.success(t("profile.saved"))

render_hero(
    kpis,
    kpis["open"],
    [source["source"] for source in source_catalog],
    lang,
)


# =========================================================
# FEED AND RIGHT RAIL
# =========================================================

feed_column, rail_column = st.columns([2.4, 1], gap="large")

with feed_column:

    if not profile:
        render_empty_state(
            t("feed.complete_profile_title"),
            t("feed.complete_profile_copy"),
        )

    else:
        filter_mode = st.pills(
            t("filter.label"),
            ["all", "eligible", "closing", "funded"],
            format_func=lambda mode: t(f"filter.{mode}"),
            default="all",
            required=True,
            key="helai_filter",
            label_visibility="collapsed",
        )

        visible = filter_results(
            results,
            filter_mode or "all",
            search_query,
        )

        if visible:
            st.html(
                '<div class="feed">'
                + "".join(
                    ticket_html(opportunity, result, lang)
                    for opportunity, result in visible
                )
                + "</div>"
            )
        else:
            render_empty_state(
                t("feed.empty_filter"),
                t("map.empty_copy"),
            )

with rail_column:

    render_booster_rail(improvements, lang)
    render_alerts_card(
        bool(saved_profile.get("email_notifications", True)),
        lang,
    )
    render_deadlines_rail(results, lang)


# =========================================================
# SECTION 01 — AI IMPORT
# =========================================================

section_header(
    format_number("03"),
    t("nav.ai_import"),
    t("import.title"),
    t("import.description"),
    "ai-import",
)

with st.container(border=True):
    st.html(
        f"""
        <div class="workspace-heading"><span class="spark">✦</span>{esc("import.workspace_heading")}</div>
        <div class="workspace-copy">{esc("import.workspace_copy")}</div>
        """
    )
    announcement_text = st.text_area(
        t("import.announcement_label"),
        height=230,
        placeholder=t("import.announcement_placeholder"),
        help=t("import.announcement_help"),
    )
    analyze_requested = st.button(
        t("import.analyze_button"),
        use_container_width=True,
        type="primary",
    )


if analyze_requested:

    if not announcement_text.strip():

        st.warning(
            t("import.paste_first")
        )

    else:

        with st.spinner(
            t("import.analyzing")
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
                    t("import.success")
                )

            except Exception as error:

                st.error(
                    t("import.failed", error=error)
                )


if st.session_state.ai_imported_opportunity:

    extracted = (
        st.session_state.ai_imported_opportunity
    )

    title_safe = html.escape(
        str(
            extracted.get(
                "title",
                t("import.untitled")
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
    <div class="card-number">{esc("import.card_number")}</div>
    <div class="card-title" dir="auto">{title_safe}</div>
    <div class="card-org" dir="auto">{org_safe}</div>
    <div class="ai-tag">{esc("import.card_tag")}</div>
</div>
"""
    )

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        st.metric(
            t("field.type"),
            t_value("type", extracted.get("type", ""), lang),
        )

    with a2:
        st.metric(
            t("field.status"),
            status_label(extracted.get("status", ""), lang),
        )

    with a3:
        st.metric(
            t("field.location"),
            extracted.get("location", ""),
        )

    with a4:
        st.metric(
            t("field.deadline"),
            format_date(extracted.get("deadline", ""), lang),
        )

    ex1, ex2 = st.columns(
        2,
        gap="large"
    )

    with ex1:

        st.markdown(
            f"### {t('import.eligibility_data')}"
        )

        st.write(
            f"**{t('field.education')}:**",
            t_value("education", extracted.get("education", "Any"), lang),
        )

        education_rule = extracted.get(
            "education_rule",
            "minimum"
        )

        st.write(
            f"**{t('import.education_rule')}:**",
            (
                t("import.rule_exact")
                if education_rule == "exact"
                else t("import.rule_minimum")
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
                f"**{t('import.age')}:**",
                (
                    f"{format_number(minimum_age) if minimum_age is not None else t('import.no_minimum')}"
                    f" — "
                    f"{format_number(maximum_age) if maximum_age is not None else t('import.no_maximum')}"
                )
            )

        residency = extracted.get(
            "residency_requirement",
            ""
        )

        st.write(
            f"**{t('import.residency')}:**",
            t_value("city", residency, lang) if residency else t("common.none_detected")
        )

        applicant_types = extracted.get(
            "eligible_applicant_types",
            []
        )

        st.write(
            f"**{t('import.applicant_type')}:**",
            (
                ", ".join(applicant_types)
                if applicant_types
                else extracted.get(
                    "applicant_type",
                    ""
                )
                or t("common.not_stated")
            )
        )

        minimum_grade = extracted.get(
            "minimum_grade",
            0
        )

        if minimum_grade:

            st.write(
                f"**{t('import.minimum_grade')}:**",
                format_percent(minimum_grade)
            )

        required_work = extracted.get(
            "minimum_work_experience_years",
            0
        )

        if required_work:

            st.write(
                f"**{t('import.work_experience')}:**",
                t("import.years", years=format_number(required_work))
            )

    with ex2:

        st.markdown(
            f"### {t('import.profile_signals')}"
        )

        st.write(
            f"**{t('field.languages')}:**",
            ", ".join(
                t_value("language", value, lang)
                for value in extracted.get("languages", [])
            ) or t("common.none_specified")
        )

        st.write(
            f"**{t('field.interests')}:**",
            ", ".join(
                t_value("interest", value, lang)
                for value in extracted.get("interests", [])
            ) or t("common.none_specified")
        )

        st.write(
            f"**{t('field.skills')}:**",
            ", ".join(
                t_value("skill", value, lang)
                for value in extracted.get("skills", [])
            ) or t("common.none_specified")
        )

        required_docs = [
            t(label)
            for flag, label in (
                ("requires_passport", "doc.passport"),
                ("requires_ielts", "doc.ielts"),
                ("requires_portfolio", "doc.portfolio"),
                ("requires_cv", "doc.cv"),
            )
            if extracted.get(flag, False)
        ]

        st.write(
            f"**{t('import.required_documents')}:**",
            (
                ", ".join(required_docs)
                if required_docs
                else t("common.none_detected")
            )
        )

    with st.expander(
        t("import.raw_data")
    ):

        st.json(
            extracted
        )


# =========================================================
# SECTION 02 — PROFILE
# =========================================================

section_header(
    format_number("04"),
    t("nav.cloud_profile"),
    t("profile.title"),
    t("profile.description"),
    "cloud-profile",
)


# Option values stay English: they are stored in the profile and read by
# matching and email code. Only their display labels are translated.
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


# Telegram appears only once the profile has notify_telegram (the Telegram
# migration has run); until then the profile works exactly as before.
telegram_available = "notify_telegram" in saved_profile
telegram_connection = None

if telegram_available:
    try:
        telegram_connection = load_telegram_connection(
            user_client(),
            current_user_id(),
        )
    except Exception:
        telegram_available = False

st.html(
    f"""
    <div class="profile-callout">
        <span>◎</span>
        <span><strong>{esc("profile.callout_title")}</strong><br>{esc("profile.callout_body")}</span>
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
            t("profile.group_personal"),
            t("profile.group_personal_copy"),
        )

        full_name = st.text_input(
            t("profile.full_name"),
            value=(
                saved_profile.get("full_name")
                or ""
            ),
            placeholder=t("auth.full_name_placeholder"),
        )

        date_of_birth = st.date_input(
            t("profile.date_of_birth"),
            value=saved_dob,
            min_value=date(1940, 1, 1),
            max_value=date.today(),
        )

        if date_of_birth:

            st.caption(
                t(
                    "profile.age_used",
                    age=format_number(calculate_age(date_of_birth)),
                )
            )

        nationality = st.text_input(
            t("profile.nationality"),
            value=(
                saved_profile.get("nationality")
                or ""
            ),
            placeholder=t("profile.nationality_placeholder"),
        )

        country_of_residence = st.text_input(
            t("profile.country"),
            value=(
                saved_profile.get("country_of_residence")
                or ""
            ),
            placeholder=t("profile.country_placeholder"),
        )

        city = st.selectbox(
            t("profile.city"),
            city_options,
            index=safe_index(
                city_options,
                saved_profile.get("city"),
                0,
            ),
            format_func=option_label("city"),
        )

        profile_group(
            t("profile.group_education"),
            t("profile.group_education_copy"),
        )

        education = st.selectbox(
            t("profile.education_level"),
            education_options,
            index=safe_index(
                education_options,
                saved_profile.get("education"),
                0,
            ),
            format_func=option_label("education"),
        )

        field_of_study = st.text_input(
            t("profile.field_of_study"),
            value=(
                saved_profile.get("field_of_study")
                or ""
            ),
            placeholder=t("profile.field_of_study_placeholder"),
        )

        grade = st.number_input(
            t("profile.grade"),
            min_value=0.0,
            max_value=100.0,
            value=float(
                saved_profile.get("grade")
                or 0.0
            ),
            step=0.1,
        )

        profile_group(
            t("profile.group_professional"),
            t("profile.group_professional_copy"),
        )

        work_experience_years = st.number_input(
            t("profile.work_years"),
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
            t("profile.group_languages_skills"),
            t("profile.group_languages_skills_copy"),
        )

        languages = st.multiselect(
            t("field.languages"),
            language_options,
            default=safe_multiselect_defaults(
                language_options,
                saved_profile.get("languages"),
            ),
            format_func=option_label("language"),
            placeholder=t("profile.choose_options"),
        )

        skills = st.multiselect(
            t("field.skills"),
            skill_options,
            default=safe_multiselect_defaults(
                skill_options,
                saved_profile.get("skills"),
            ),
            format_func=option_label("skill"),
            placeholder=t("profile.choose_options"),
        )

        profile_group(
            t("profile.group_interests"),
            t("profile.group_interests_copy"),
        )

        interests = st.multiselect(
            t("profile.areas_of_interest"),
            interest_options,
            default=safe_multiselect_defaults(
                interest_options,
                saved_profile.get("interests"),
            ),
            format_func=option_label("interest"),
            placeholder=t("profile.choose_options"),
        )

        opportunity_types = st.multiselect(
            t("profile.opportunity_types"),
            opportunity_type_options,
            default=safe_multiselect_defaults(
                opportunity_type_options,
                saved_profile.get(
                    "opportunity_types"
                ),
            ),
            format_func=option_label("type"),
            placeholder=t("profile.choose_options"),
        )

        preferred_language = st.selectbox(
            t("profile.preferred_language"),
            preferred_language_options,
            index=safe_index(
                preferred_language_options,
                saved_profile.get(
                    "preferred_language"
                ),
                0,
            ),
            format_func=option_label("language"),
        )

        profile_group(
            t("profile.group_notifications"),
            t("profile.group_notifications_copy"),
        )

        email_notifications = st.checkbox(
            t("profile.email_notifications"),
            value=bool(
                saved_profile.get(
                    "email_notifications",
                    True,
                )
            ),
        )

        notify_telegram = False

        if telegram_available:
            notify_telegram = st.checkbox(
                t("profile.telegram_notifications"),
                value=(
                    bool(saved_profile.get("notify_telegram"))
                    and telegram_connection is not None
                ),
                disabled=telegram_connection is None,
                help=(
                    None
                    if telegram_connection
                    else t("profile.telegram_needs_connection")
                ),
            )

        profile_group(
            t("profile.group_documents"),
            t("profile.group_documents_copy"),
        )

        has_passport = st.checkbox(
            t("profile.has_passport"),
            value=bool(
                saved_profile.get(
                    "has_passport",
                    False,
                )
            ),
        )

        has_ielts = st.checkbox(
            t("profile.has_ielts"),
            value=bool(
                saved_profile.get(
                    "has_ielts",
                    False,
                )
            ),
        )

        has_portfolio = st.checkbox(
            t("profile.has_portfolio"),
            value=bool(
                saved_profile.get(
                    "has_portfolio",
                    False,
                )
            ),
        )

        has_cv = st.checkbox(
            t("profile.has_cv"),
            value=bool(
                saved_profile.get(
                    "has_cv",
                    False,
                )
            ),
        )

    submitted = st.form_submit_button(
        t("profile.save_button"),
        use_container_width=True,
    )


# =========================================================
# SAVE PROFILE
# The dashboard above re-matches from the saved profile on
# the rerun that follows a successful save.
# =========================================================

if submitted:

    if not full_name.strip():

        st.warning(
            t("profile.enter_full_name")
        )

    elif date_of_birth is None:

        st.warning(
            t("profile.enter_date_of_birth")
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

        if telegram_available:
            cloud_profile_data["notify_telegram"] = (
                bool(notify_telegram)
                and telegram_connection is not None
            )

        with st.spinner(
            t("profile.saving")
        ):

            save_result = update_profile(
                access_token=st.session_state.access_token,
                refresh_token=st.session_state.refresh_token,
                profile_data=cloud_profile_data,
            )

        if not save_result["success"]:

            st.error(
                t("profile.save_failed", message=save_result["message"])
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

            st.session_state.helai_profile_saved = True
            st.rerun()


# =========================================================
# TELEGRAM CONNECTION
# The app only creates a short-lived code; the collector run
# links the chat when the user presses Start in Telegram.
# =========================================================

if telegram_available:

    with st.container(border=True):

        profile_group(
            t("telegram.title"),
            t("telegram.copy"),
        )

        if st.session_state.pop("helai_telegram_disconnected", False):
            st.success(t("telegram.disconnected"))

        if telegram_connection:

            st.success(
                t(
                    "telegram.connected_since",
                    date=format_date(
                        str(telegram_connection.get("connected_at") or "")[:10],
                        lang,
                    ),
                )
            )

            if st.button(
                t("telegram.disconnect_button"),
                key="helai_telegram_disconnect",
                type="secondary",
            ):
                try:
                    disconnect_telegram(user_client(), current_user_id())
                except Exception as error:
                    st.error(t("telegram.error", message=error))
                else:
                    if st.session_state.cloud_profile:
                        st.session_state.cloud_profile["notify_telegram"] = False
                    st.session_state.pop("helai_telegram_code", None)
                    st.session_state.helai_telegram_disconnected = True
                    st.rerun()

        else:

            st.info(t("telegram.not_connected"))

            pending_code = st.session_state.get("helai_telegram_code")

            if pending_code and code_is_pending(pending_code["created_at"]):
                st.link_button(
                    t("telegram.open_bot"),
                    bot_link(pending_code["code"]),
                    type="primary",
                    use_container_width=True,
                )
                st.caption(
                    t(
                        "telegram.code_help",
                        minutes=format_number(LINK_CODE_MINUTES),
                        code=pending_code["code"],
                    )
                )
                st.caption(t("telegram.pending_help"))
            else:
                pending_code = None

            if st.button(
                t("telegram.connect_button"),
                key="helai_telegram_connect",
                type="secondary" if pending_code else "primary",
                use_container_width=True,
            ):
                try:
                    code = create_link_code(user_client(), current_user_id())
                except Exception as error:
                    st.error(t("telegram.error", message=error))
                else:
                    st.session_state.helai_telegram_code = {
                        "code": code,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    st.rerun()


# =========================================================
# FOOTER
# =========================================================

st.html(
    f"""
<div class="footer">
    <div>{esc("footer.prototype")}</div>
    <div>{esc("footer.event", year=format_number(2026))}</div>
</div>
"""
)
