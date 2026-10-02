import os
from datetime import date, datetime, timezone
from html import escape

import requests
from helai_env import load_env
from supabase import create_client

from helai_config import (
    EMAIL_FROM,
    EMAIL_TEST_MODE,
    EMAIL_TEST_RECIPIENT,
    HELAI_APP_URL,
)
from helai_i18n import (
    RTL_LANGUAGES,
    format_date,
    format_number,
    format_percent,
    normalize_sorani_terms,
    t,
    t_value,
    translate_match_message,
)
from opportunity_rules import effective_status, has_document_requirements


load_env()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")


TEST_MODE = EMAIL_TEST_MODE
TEST_RECIPIENT = EMAIL_TEST_RECIPIENT

MAX_ATTEMPTS = 3


def get_supabase():
    if not SUPABASE_URL:
        raise ValueError("SUPABASE_URL was not found in .env")

    if not SUPABASE_SECRET_KEY:
        raise ValueError(
            "SUPABASE_SECRET_KEY was not found in .env"
        )

    return create_client(
        SUPABASE_URL,
        SUPABASE_SECRET_KEY
    )


def get_one(client, table_name, record_id):
    result = (
        client
        .table(table_name)
        .select("*")
        .eq("id", record_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


# =========================================================
# EMAIL CONTENT
# Email-safe markup: tables and inline styles only, system
# fonts (Tahoma/Arial for Kurdish and Arabic).
# =========================================================

FSI = "⁨"
PDI = "⁩"

GROUND = "#0E1014"
CARD = "#171A21"
BORDER = "#252A33"
TEXT = "#F3F1EC"
MUTED = "#B3B7C1"
SAFFRON = "#F4B740"
BUTTON_TEXT = "#16130B"
MINT = "#5FD8A4"

EMAIL_LANGUAGE_NAMES = {
    "ckb": "Kurdish Sorani",
    "en": "English",
    "ar": "Arabic",
}

MAX_LIST_ITEMS = 5


def isolate(text):
    """Unicode first-strong isolate so Latin text keeps its order in RTL."""
    return f"{FSI}{text}{PDI}"


def is_kurdish_sorani(profile):
    language = str(
        profile.get("preferred_language") or ""
    ).strip().lower()

    return language in [
        "kurdish sorani",
        "sorani",
        "کوردی",
        "کوردی سۆرانی"
    ]


def is_arabic(profile):
    language = str(
        profile.get("preferred_language") or ""
    ).strip().lower()

    return language in [
        "arabic",
        "العربية",
        "عربي",
    ]


def is_english_or_kurmanji(profile):
    language = str(
        profile.get("preferred_language") or ""
    ).strip().lower()

    # Kurmanji is written in Latin script, so it reads the English email.
    return language in [
        "english",
        "en",
        "kurdish kurmanji",
        "kurmanji",
    ]


def email_language(profile):
    """Sorani (and empty or unknown) -> ckb; Arabic -> ar; English and Kurmanji -> en."""
    if is_arabic(profile):
        return "ar"
    if is_english_or_kurmanji(profile):
        return "en"
    return "ckb"


def readiness_label(opportunity, match, lang):
    """Same rule as helai_ui.readiness_display: no tracked documents, no %."""
    if not has_document_requirements(opportunity):
        return t("card.no_document_requirements", lang=lang)
    return format_percent(int(match.get("readiness") or 0), lang)


def location_label(location, lang):
    location = str(location or "").strip()
    if not location:
        return t("common.not_stated", lang=lang)
    label = t_value("location", location, lang)
    if label == location:
        label = t_value("city", location, lang)
    return label


def deadline_parts(deadline, lang, today=None):
    """(formatted deadline, days-left text); unknown deadlines say so."""
    if not deadline:
        return t("email.no_deadline", lang=lang), ""
    try:
        due = date.fromisoformat(str(deadline).strip()[:10])
    except ValueError:
        return str(deadline), ""

    days = (due - (today or date.today())).days
    if days < 0:
        left = ""
    elif days == 0:
        left = t("email.closes_today", lang=lang)
    elif days == 1:
        left = t("email.one_day_left", lang=lang)
    else:
        left = t("email.days_left", lang=lang, days=format_number(days, lang))
    return format_date(due, lang), left


def build_subject(opportunity, match, lang):
    title = str(opportunity.get("title") or t("card.opportunity", lang=lang))
    score = format_percent(int(match.get("match_score") or 0), lang)

    if lang in RTL_LANGUAGES:
        # Isolating the Latin brand too makes the subject's first strong
        # character Kurdish/Arabic, so clients lay the line out right-to-left.
        return t(
            "email.subject",
            lang=lang,
            brand=isolate("HelAI"),
            score=score,
            title=isolate(title),
        )

    return t("email.subject", lang=lang, brand="HelAI", score=score, title=title)


def _list_rows(items, bullet_color, align, font, lang="en"):
    rows = "".join(
        f"""
        <tr>
            <td width="18" valign="top" style="padding: 4px 0; color: {bullet_color}; font-family: {font}; font-size: 14px; line-height: 22px;">&#8226;</td>
            <td style="padding: 4px 0; color: {TEXT}; font-family: {font}; font-size: 14px; line-height: 22px; text-align: {align};">{escape(translate_match_message(item, lang))}</td>
        </tr>
        """
        for item in items[:MAX_LIST_ITEMS]
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>'


def _section(title, body, align, font):
    return f"""
    <tr>
        <td style="padding: 22px 28px 0;">
            <div style="color: {MUTED}; font-family: {font}; font-size: 12px; font-weight: bold; text-align: {align}; padding-bottom: 6px;">{escape(title)}</div>
            {body}
        </td>
    </tr>
    """


def build_email(profile, opportunity, match, lang="en", today=None):
    rtl = lang in RTL_LANGUAGES
    direction = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"
    font = "Tahoma, Arial, sans-serif" if rtl else "Arial, Helvetica, sans-serif"

    def name_text(value):
        return isolate(value) if rtl else value

    full_name = str(profile.get("full_name") or t("sidebar.default_user", lang=lang))
    title = str(opportunity.get("title") or t("card.opportunity", lang=lang))
    organization = str(opportunity.get("organization") or t("card.no_organization", lang=lang))
    source_name = str(opportunity.get("source_name") or opportunity.get("source") or "")
    opportunity_type = str(opportunity.get("type") or "")
    type_label = (
        t_value("type", opportunity_type, lang)
        if opportunity_type
        else t("card.opportunity", lang=lang)
    )
    location = location_label(opportunity.get("location"), lang)
    deadline, days_left = deadline_parts(opportunity.get("deadline"), lang, today)
    score = format_percent(int(match.get("match_score") or 0), lang)
    readiness = readiness_label(opportunity, match, lang)
    eligible = bool(match.get("eligible"))
    reasons = list(match.get("reasons") or [])
    missing = list(match.get("eligibility_gaps") or []) + list(match.get("readiness_gaps") or [])
    source_url = str(opportunity.get("source_url") or "")
    alerts_url = f"{HELAI_APP_URL}/?lang={lang}#cloud-profile"

    summary_ku = normalize_sorani_terms(opportunity.get("summary_ku")).strip()
    summary_en = str(opportunity.get("summary_en") or opportunity.get("notes") or "").strip()
    if lang == "ckb" and summary_ku:
        summary_html = f'<div style="color: {TEXT}; font-family: {font}; font-size: 14px; line-height: 26px; text-align: {align};">{escape(summary_ku)}</div>'
    else:
        note = ""
        if rtl:
            note = f'<div style="color: {MUTED}; font-family: {font}; font-size: 12px; line-height: 20px; text-align: {align}; padding-bottom: 6px;">{escape(t(f"card.summary_missing_{lang}", lang=lang))}</div>'
        text = summary_en or t("email.summary_fallback", lang="en")
        summary_html = note + f'<div dir="ltr" style="color: {TEXT}; font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 23px; text-align: left;">{escape(text)}</div>'

    eligible_html = (
        f'<span style="color: {MINT};">&#10003;&nbsp;{escape(t("email.eligible", lang=lang))}</span>'
        if eligible
        else f'<span style="color: {SAFFRON};">{escape(t("email.not_eligible", lang=lang))}</span>'
    )

    days_html = (
        f'<div style="color: {SAFFRON}; font-family: {font}; font-size: 12px; padding-top: 3px;">{escape(days_left)}</div>'
        if days_left
        else ""
    )

    source_html = (
        f' &middot; <span dir="ltr">{escape(source_name)}</span>' if source_name else ""
    )

    why_html = (
        _list_rows(reasons, MINT, align, font, lang)
        if reasons
        else f'<div style="color: {MUTED}; font-family: {font}; font-size: 14px; text-align: {align};">{escape(t("card.why_empty", lang=lang))}</div>'
    )
    missing_html = (
        _list_rows(missing, SAFFRON, align, font, lang)
        if missing
        else f'<div style="color: {MUTED}; font-family: {font}; font-size: 14px; text-align: {align};">{escape(t("email.nothing_missing", lang=lang))}</div>'
    )

    button_html = ""
    if source_url:
        button_html = f"""
        <tr>
            <td align="{align}" style="padding: 26px 28px 4px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td bgcolor="{SAFFRON}" style="border-radius: 10px;">
                            <a href="{escape(source_url, quote=True)}" style="display: inline-block; padding: 14px 26px; font-family: {font}; font-size: 15px; font-weight: bold; color: {BUTTON_TEXT}; text-decoration: none; border-radius: 10px;">{escape(t("email.view", lang=lang))}</a>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        """

    def stub_cell(label, value, extra=""):
        return f"""
        <td valign="top" width="33%" style="padding: 18px 14px 20px;">
            <div style="color: {MUTED}; font-family: {font}; font-size: 12px; text-align: {align};">{escape(label)}</div>
            <div dir="auto" style="color: {TEXT}; font-family: {font}; font-size: 14px; font-weight: bold; padding-top: 4px; text-align: {align};">{escape(value)}</div>
            {extra}
        </td>
        """

    return f"""<!DOCTYPE html>
<html lang="{lang}" dir="{direction}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="supported-color-schemes" content="dark">
<title>{escape(build_subject(opportunity, match, lang))}</title>
</head>
<body dir="{direction}" style="margin: 0; padding: 0; background: {GROUND}; font-family: {font};">
<div style="display: none; max-height: 0; overflow: hidden; mso-hide: all;">{escape(t("email.preheader", lang=lang))}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{GROUND}" style="background: {GROUND};">
<tr>
<td align="center" style="padding: 28px 12px 36px;">
<table role="presentation" dir="{direction}" width="600" cellpadding="0" cellspacing="0" border="0" style="width: 100%; max-width: 600px;">

    <tr>
        <td style="padding: 4px 4px 22px; text-align: {align};">
            <span dir="ltr" style="color: {TEXT}; font-family: Arial, Helvetica, sans-serif; font-size: 22px; font-weight: bold;">HelAI<span style="color: {SAFFRON};">.</span></span>
            <div style="color: {MUTED}; font-family: {font}; font-size: 13px; padding-top: 4px;">{escape(t("email.tagline", lang=lang))}</div>
        </td>
    </tr>

    <tr>
        <td style="padding: 0 4px 18px; text-align: {align};">
            <div style="color: {TEXT}; font-family: {font}; font-size: 16px; line-height: 26px;">{escape(t("email.greeting", lang=lang, name=name_text(full_name)))}</div>
            <div style="color: {MUTED}; font-family: {font}; font-size: 14px; line-height: 24px;">{escape(t("email.intro", lang=lang))}</div>
        </td>
    </tr>

    <tr>
        <td>
            <table role="presentation" dir="{direction}" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{CARD}" style="background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px;">

                <tr>
                    <td style="padding: 24px 28px 18px;">
                        <table role="presentation" dir="{direction}" width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                                <td valign="top" style="text-align: {align};">
                                    <div style="color: {SAFFRON}; font-family: {font}; font-size: 12px; font-weight: bold;">{escape(t("email.new_match", lang=lang))} &middot; {escape(type_label)}{source_html}</div>
                                    <div dir="auto" style="color: {TEXT}; font-family: {font}; font-size: 21px; line-height: 29px; font-weight: bold; padding-top: 8px; text-align: {align};">{escape(title)}</div>
                                    <div style="color: {MUTED}; font-family: {font}; font-size: 13px; padding-top: 6px; text-align: {align};">{escape(t("email.organization", lang=lang))}: <span dir="auto">{escape(organization)}</span></div>
                                </td>
                                <td valign="top" width="120" style="padding-{"right" if rtl else "left"}: 16px; text-align: center;">
                                    <div style="color: {SAFFRON}; font-family: {font}; font-size: 40px; line-height: 44px; font-weight: bold; white-space: nowrap;">{escape(score)}</div>
                                    <div style="color: {MUTED}; font-family: {font}; font-size: 12px; padding-top: 2px;">{escape(t("field.match", lang=lang))}</div>
                                </td>
                            </tr>
                        </table>
                        <div style="font-family: {font}; font-size: 14px; line-height: 22px; font-weight: bold; padding-top: 16px; text-align: {align};">{eligible_html}</div>
                    </td>
                </tr>

                <tr>
                    <td>
                        <table role="presentation" dir="ltr" width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                                <td width="14" height="28" bgcolor="{GROUND}" style="background: {GROUND}; border-radius: 0 14px 14px 0; font-size: 0; line-height: 0;">&nbsp;</td>
                                <td valign="middle" style="padding: 0 8px;"><div style="border-top: 2px dashed {BORDER}; height: 0; font-size: 0; line-height: 0;">&nbsp;</div></td>
                                <td width="14" height="28" bgcolor="{GROUND}" style="background: {GROUND}; border-radius: 14px 0 0 14px; font-size: 0; line-height: 0;">&nbsp;</td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <tr>
                    <td style="padding: 0 14px;">
                        <table role="presentation" dir="{direction}" width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                                {stub_cell(t("field.deadline", lang=lang), deadline, days_html)}
                                {stub_cell(t("field.readiness", lang=lang), readiness)}
                                {stub_cell(t("field.location", lang=lang), location)}
                            </tr>
                        </table>
                    </td>
                </tr>

            </table>
        </td>
    </tr>

    <tr>
        <td>
            <table role="presentation" dir="{direction}" width="100%" cellpadding="0" cellspacing="0" border="0" style="padding-top: 6px;">
                {_section(t("card.why_it_fits", lang=lang), why_html, align, font)}
                {_section(t("email.still_missing", lang=lang), missing_html, align, font)}
                {_section(t("card.summary_kurdish", lang=lang) if lang == "ckb" and summary_ku else t("card.about", lang=lang), summary_html, align, font)}
                {button_html}
            </table>
        </td>
    </tr>

    <tr>
        <td style="padding: 34px 4px 0;">
            <div style="border-top: 1px solid {BORDER}; padding-top: 18px; text-align: {align}; font-family: {font}; font-size: 12px; line-height: 20px; color: {MUTED};">
                <a href="{escape(alerts_url, quote=True)}" style="color: {SAFFRON}; text-decoration: none; font-weight: bold;">{escape(t("email.manage_alerts", lang=lang))}</a>
                <div style="padding-top: 8px;">{escape(t("email.unsubscribe", lang=lang))} <a href="{escape(alerts_url, quote=True)}" style="color: {MUTED}; text-decoration: underline;">{escape(t("email.unsubscribe_link", lang=lang))}</a></div>
                <div style="padding-top: 8px;">{escape(t("email.footer_note", lang=lang))}</div>
            </div>
        </td>
    </tr>

</table>
</td>
</tr>
</table>
</body>
</html>
"""


def build_kurdish_email(profile, opportunity, match):
    return build_email(profile, opportunity, match, "ckb")


def build_english_email(profile, opportunity, match):
    return build_email(profile, opportunity, match, "en")


def send_resend_email(
    recipient,
    subject,
    html
):
    if not RESEND_API_KEY:
        return {
            "success": False,
            "error": (
                "RESEND_API_KEY was not found in .env"
            )
        }

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": (
                f"Bearer {RESEND_API_KEY}"
            ),
            "Content-Type": "application/json"
        },
        json={
            "from": EMAIL_FROM,
            "to": [recipient],
            "subject": subject,
            "html": html
        },
        timeout=30
    )

    if response.status_code in (
        200,
        201
    ):
        return {
            "success": True,
            "data": response.json()
        }

    return {
        "success": False,
        "error": (
            f"Resend API error "
            f"{response.status_code}: "
            f"{response.text}"
        )
    }


def mark_sent(
    client,
    notification,
    match
):
    now = datetime.now(
        timezone.utc
    ).isoformat()

    attempts = (
        notification.get("attempts")
        or 0
    ) + 1

    (
        client
        .table("notifications")
        .update({
            "status": "sent",
            "attempts": attempts,
            "last_error": None,
            "sent_at": now,
            "updated_at": now
        })
        .eq(
            "id",
            notification["id"]
        )
        .execute()
    )

    (
        client
        .table("matches")
        .update({
            "notified": True,
            "notified_at": now,
            "updated_at": now
        })
        .eq(
            "id",
            match["id"]
        )
        .execute()
    )


def mark_failed(
    client,
    notification,
    error,
    final=False
):
    """Record a failed send; final=True uses up the attempts so it never retries."""
    now = datetime.now(
        timezone.utc
    ).isoformat()

    attempts = (
        notification.get("attempts")
        or 0
    ) + 1

    if final:
        attempts = max(attempts, MAX_ATTEMPTS)

    (
        client
        .table("notifications")
        .update({
            "status": "failed",
            "attempts": attempts,
            "last_error": str(error),
            "updated_at": now
        })
        .eq(
            "id",
            notification["id"]
        )
        .execute()
    )


def send_pending_notifications():
    client = get_supabase()

    result = (
        client
        .table("notifications")
        .select("*")
        .eq("channel", "email")
        .execute()
    )

    notifications = []

    for item in (
        result.data or []
    ):
        status = item.get("status")

        attempts = (
            item.get("attempts")
            or 0
        )

        if (
            status in [
                "pending",
                "failed"
            ]
            and attempts < MAX_ATTEMPTS
        ):
            notifications.append(
                item
            )


    print()
    print(
        "========================================"
    )
    print(
        "       HELAI EMAIL DELIVERY"
    )
    print(
        "========================================"
    )
    print()

    print(
        "Notifications ready:",
        len(notifications)
    )

    print()


    sent_count = 0
    failed_count = 0
    skipped_count = 0


    for notification in notifications:

        print(
            "----------------------------------------"
        )

        profile = get_one(
            client,
            "profiles",
            notification["user_id"]
        )

        opportunity = get_one(
            client,
            "opportunities",
            notification["opportunity_id"]
        )

        match = get_one(
            client,
            "matches",
            notification["match_id"]
        )


        if not profile:
            print(
                "SKIPPED: Profile not found"
            )

            skipped_count += 1
            continue


        if not opportunity:
            print(
                "SKIPPED: Opportunity not found"
            )

            skipped_count += 1
            continue


        if not match:
            print(
                "SKIPPED: Match not found"
            )

            skipped_count += 1
            continue

        if effective_status(opportunity) != "Open":
            print(
                "SKIPPED: Opportunity is not open"
            )

            skipped_count += 1
            continue

        if not match.get(
            "eligible",
            False
        ):
            print(
                "SKIPPED: Match is not eligible"
            )

            skipped_count += 1
            continue

        if not profile.get(
            "email_notifications",
            True
        ):
            print(
                "SKIPPED: Email notifications disabled"
            )

            skipped_count += 1
            continue


        title = (
            opportunity.get("title")
            or "Opportunity"
        )

        profile_email = (
            profile.get("email")
        )


        if TEST_MODE:
            if not TEST_RECIPIENT:
                print(
                    "SKIPPED: EMAIL_TEST_MODE is true "
                    "but EMAIL_TEST_RECIPIENT is empty"
                )

                skipped_count += 1
                continue

            recipient = (
                TEST_RECIPIENT
            )
        else:
            recipient = (
                profile_email
            )


        if not recipient:
            print(
                "SKIPPED: No recipient email"
            )

            skipped_count += 1
            continue


        match_score = match.get(
            "match_score",
            0
        )


        email_lang = email_language(
            profile
        )

        language = EMAIL_LANGUAGE_NAMES[
            email_lang
        ]

        subject = build_subject(
            opportunity,
            match,
            email_lang
        )

        html = build_email(
            profile,
            opportunity,
            match,
            email_lang
        )


        print(
            "Opportunity:",
            title
        )

        print(
            "HelAI user:",
            profile_email
        )

        print(
            "Preferred language:",
            language
        )

        print(
            "Sending to:",
            recipient
        )

        print(
            "Match score:",
            f"{match_score}%"
        )


        send_result = send_resend_email(
            recipient,
            subject,
            html
        )


        if send_result["success"]:

            mark_sent(
                client,
                notification,
                match
            )

            email_id = (
                send_result
                .get("data", {})
                .get("id")
            )

            print(
                "SENT: True"
            )

            print(
                "Resend ID:",
                email_id
            )

            sent_count += 1

        else:

            error = send_result.get(
                "error",
                "Unknown email error"
            )

            mark_failed(
                client,
                notification,
                error
            )

            print(
                "SENT: False"
            )

            print(
                "ERROR:",
                error
            )

            failed_count += 1

        print()


    print(
        "========================================"
    )
    print(
        "              SUMMARY"
    )
    print(
        "========================================"
    )

    print()
    print(
        "Sent:",
        sent_count
    )
    print(
        "Failed:",
        failed_count
    )
    print(
        "Skipped:",
        skipped_count
    )
    print()

    return {
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "ready": len(notifications),
        "test_mode": TEST_MODE,
    }


if __name__ == "__main__":
    send_pending_notifications()
