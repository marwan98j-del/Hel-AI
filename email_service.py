import os
from datetime import datetime, timezone
from html import escape

import requests
from dotenv import load_dotenv
from supabase import create_client

from helai_config import (
    EMAIL_FROM,
    EMAIL_TEST_MODE,
    EMAIL_TEST_RECIPIENT,
)
from opportunity_rules import effective_status


load_dotenv(override=True)


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


def format_deadline_english(deadline):
    if not deadline:
        return "Not specified"

    try:
        parsed = datetime.strptime(
            str(deadline),
            "%Y-%m-%d"
        )

        return parsed.strftime("%d %B %Y")

    except Exception:
        return str(deadline)


def format_deadline_kurdish(deadline):
    if not deadline:
        return "دیاری نەکراوە"

    return str(deadline)


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


def make_button(source_url, label):
    if not source_url:
        return ""

    safe_url = escape(
        str(source_url),
        quote=True
    )

    return f"""
    <p style="margin-top: 28px;">
        <a
            href="{safe_url}"
            style="
                display: inline-block;
                background: #5b5bf7;
                color: white;
                padding: 13px 22px;
                text-decoration: none;
                border-radius: 9px;
                font-weight: bold;
            "
        >
            {escape(label)}
        </a>
    </p>
    """


def build_kurdish_email(
    profile,
    opportunity,
    match
):
    full_name = (
        profile.get("full_name")
        or "بەکارهێنەری HelAI"
    )

    title = (
        opportunity.get("title")
        or "دەرفەت"
    )

    organization = (
        opportunity.get("organization")
        or "دیاری نەکراوە"
    )

    opportunity_type = (
        opportunity.get("type")
        or "دەرفەت"
    )

    location = (
        opportunity.get("location")
        or "دیاری نەکراوە"
    )

    deadline = format_deadline_kurdish(
        opportunity.get("deadline")
    )

    summary_ku = (
        opportunity.get("summary_ku")
        or
        "HelAI ئەم دەرفەتەی بە پڕۆفایلی تۆ گونجاو زانیوە."
    )

    source_url = opportunity.get("source_url")

    match_score = match.get(
        "match_score",
        0
    )

    readiness = match.get(
        "readiness",
        0
    )

    eligibility_gaps = (
        match.get("eligibility_gaps")
        or []
    )

    readiness_gaps = (
        match.get("readiness_gaps")
        or []
    )

    gaps_html = ""

    if eligibility_gaps or readiness_gaps:
        gaps_html = """
        <div
            style="
                margin-top: 24px;
                padding: 18px;
                background: #fff7ed;
                border-radius: 10px;
            "
        >
            <strong>
                خاڵەکانی پێویستی بە سەرنج:
            </strong>
        """

        all_gaps = (
            eligibility_gaps
            + readiness_gaps
        )

        gaps_html += "<ul>"

        for gap in all_gaps:
            gaps_html += (
                f"<li>{escape(str(gap))}</li>"
            )

        gaps_html += "</ul></div>"

    else:
        gaps_html = """
        <div
            style="
                margin-top: 24px;
                padding: 18px;
                background: #f0fdf4;
                border-radius: 10px;
            "
        >
            <strong>
                ئامادەیی:
            </strong>
            HelAI هیچ پێداویستییەکی گەورەی
            ونبووی نەدۆزیوەتەوە.
        </div>
        """

    button = make_button(
        source_url,
        "بینینی دەرفەت"
    )

    return f"""
    <!DOCTYPE html>

    <html lang="ckb" dir="rtl">

    <body
        dir="rtl"
        style="
            margin: 0;
            padding: 0;
            background: #f4f6f8;
            font-family:
                Tahoma,
                Arial,
                sans-serif;
            color: #172033;
            direction: rtl;
            text-align: right;
        "
    >

        <div
            style="
                max-width: 620px;
                margin: 30px auto;
                background: white;
                border-radius: 14px;
                overflow: hidden;
                border: 1px solid #e6e8ec;
            "
        >

            <div
                style="
                    background: #111827;
                    padding: 28px;
                    color: white;
                "
            >

                <div
                    dir="ltr"
                    style="
                        text-align: right;
                        font-size: 30px;
                        font-weight: bold;
                    "
                >
                    HelAI
                </div>

                <div
                    style="
                        margin-top: 7px;
                        color: #cbd5e1;
                    "
                >
                    ئەجێنتی زیرەکی دەستکردی
                    دۆزینەوەی دەرفەت
                </div>

            </div>


            <div style="padding: 30px;">

                <p>
                    سڵاو
                    <strong>
                        {escape(str(full_name))}
                    </strong>
                </p>

                <p>
                    HelAI دەرفەتێکی نوێی دۆزیوەتەوە
                    کە بە پڕۆفایلی تۆ گونجاوە.
                </p>


                <div
                    style="
                        background: #f7f7ff;
                        border: 1px solid #e2e2ff;
                        border-radius: 12px;
                        padding: 22px;
                        margin: 24px 0;
                    "
                >

                    <h2>
                        {escape(str(title))}
                    </h2>

                    <p>
                        <strong>
                            دامەزراوە:
                        </strong>
                        {escape(str(organization))}
                    </p>

                    <p>
                        <strong>
                            جۆری دەرفەت:
                        </strong>
                        {escape(str(opportunity_type))}
                    </p>

                    <p>
                        <strong>
                            شوێن:
                        </strong>
                        {escape(str(location))}
                    </p>

                    <p>
                        <strong>
                            دوا وادە:
                        </strong>
                        {escape(str(deadline))}
                    </p>

                </div>


                <table
                    width="100%"
                    cellspacing="0"
                    cellpadding="0"
                >
                    <tr>

                        <td
                            width="50%"
                            style="
                                padding: 8px;
                            "
                        >

                            <div
                                style="
                                    background: #eef2ff;
                                    padding: 18px;
                                    border-radius: 10px;
                                "
                            >

                                <div
                                    style="
                                        font-size: 13px;
                                        color: #64748b;
                                    "
                                >
                                    ڕێژەی گونجان
                                </div>

                                <div
                                    style="
                                        font-size: 28px;
                                        font-weight: bold;
                                    "
                                >
                                    {match_score}%
                                </div>

                            </div>

                        </td>


                        <td
                            width="50%"
                            style="
                                padding: 8px;
                            "
                        >

                            <div
                                style="
                                    background: #f0fdf4;
                                    padding: 18px;
                                    border-radius: 10px;
                                "
                            >

                                <div
                                    style="
                                        font-size: 13px;
                                        color: #64748b;
                                    "
                                >
                                    ئامادەیی
                                </div>

                                <div
                                    style="
                                        font-size: 28px;
                                        font-weight: bold;
                                    "
                                >
                                    {readiness}%
                                </div>

                            </div>

                        </td>

                    </tr>
                </table>


                <h3>
                    دەربارەی ئەم دەرفەتە
                </h3>

                <div
                    style="
                        line-height: 2;
                        white-space: pre-line;
                    "
                >
                    {escape(str(summary_ku))}
                </div>


                {gaps_html}

                {button}


                <hr
                    style="
                        border: none;
                        border-top: 1px solid #e5e7eb;
                        margin: 30px 0;
                    "
                >


                <p
                    style="
                        font-size: 12px;
                        color: #64748b;
                    "
                >
                    ئەم ئاگادارکردنەوەیە بە شێوەی
                    ئۆتۆماتیکی لەلایەن HelAI ـەوە
                    دروست کراوە، دوای بەراوردکردنی
                    پێداویستییەکانی دەرفەتەکە
                    لەگەڵ پڕۆفایلی تۆ.
                </p>

            </div>

        </div>

    </body>

    </html>
    """


def build_english_email(
    profile,
    opportunity,
    match
):
    full_name = (
        profile.get("full_name")
        or "HelAI user"
    )

    title = (
        opportunity.get("title")
        or "Opportunity"
    )

    organization = (
        opportunity.get("organization")
        or "Not specified"
    )

    opportunity_type = (
        opportunity.get("type")
        or "Opportunity"
    )

    location = (
        opportunity.get("location")
        or "Not specified"
    )

    deadline = format_deadline_english(
        opportunity.get("deadline")
    )

    source_url = opportunity.get("source_url")

    match_score = match.get(
        "match_score",
        0
    )

    readiness = match.get(
        "readiness",
        0
    )

    summary_en = (
        opportunity.get("summary_en")
        or opportunity.get("notes")
        or
        "HelAI found this opportunity relevant to your profile."
    )

    button = make_button(
        source_url,
        "View Opportunity"
    )

    return f"""
    <!DOCTYPE html>

    <html lang="en">

    <body
        style="
            margin: 0;
            padding: 0;
            background: #f4f6f8;
            font-family: Arial, Helvetica, sans-serif;
            color: #172033;
        "
    >

        <div
            style="
                max-width: 620px;
                margin: 30px auto;
                background: white;
                border-radius: 14px;
                overflow: hidden;
                border: 1px solid #e6e8ec;
            "
        >

            <div
                style="
                    background: #111827;
                    padding: 28px;
                    color: white;
                "
            >

                <div
                    style="
                        font-size: 30px;
                        font-weight: bold;
                    "
                >
                    HelAI
                </div>

                <div
                    style="
                        margin-top: 7px;
                        color: #cbd5e1;
                    "
                >
                    Your AI Opportunity Agent
                </div>

            </div>


            <div style="padding: 30px;">

                <p>
                    Hello
                    <strong>
                        {escape(str(full_name))}
                    </strong>,
                </p>

                <p>
                    HelAI found an opportunity
                    that matches your profile.
                </p>


                <div
                    style="
                        background: #f7f7ff;
                        border: 1px solid #e2e2ff;
                        border-radius: 12px;
                        padding: 22px;
                        margin: 24px 0;
                    "
                >

                    <h2>
                        {escape(str(title))}
                    </h2>

                    <p>
                        <strong>Organization:</strong>
                        {escape(str(organization))}
                    </p>

                    <p>
                        <strong>Type:</strong>
                        {escape(str(opportunity_type))}
                    </p>

                    <p>
                        <strong>Location:</strong>
                        {escape(str(location))}
                    </p>

                    <p>
                        <strong>Deadline:</strong>
                        {escape(str(deadline))}
                    </p>

                </div>


                <p>
                    <strong>Match score:</strong>
                    {match_score}%
                </p>

                <p>
                    <strong>Readiness:</strong>
                    {readiness}%
                </p>


                <h3>
                    About this opportunity
                </h3>

                <p style="line-height: 1.7;">
                    {escape(str(summary_en))}
                </p>

                {button}

            </div>

        </div>

    </body>

    </html>
    """


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
    error
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


        if is_kurdish_sorani(
            profile
        ):
            language = (
                "Kurdish Sorani"
            )

            subject = (
                f"HelAI: "
                f"دەرفەتێکی {match_score}% "
                f"بۆ تۆ — {title}"
            )

            html = build_kurdish_email(
                profile,
                opportunity,
                match
            )

        else:
            language = "English"

            subject = (
                f"HelAI: "
                f"{match_score}% match — "
                f"{title}"
            )

            html = build_english_email(
                profile,
                opportunity,
                match
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
