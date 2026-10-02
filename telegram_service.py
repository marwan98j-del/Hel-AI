"""HelAI Telegram channel: Bot API calls, account linking and delivery.

Delivery mirrors email_service.send_pending_notifications: it reads only
channel='telegram' rows from the shared notifications queue, applies the same
open/eligible checks, and records results with the same mark_sent/mark_failed.
"""

import os
import time
from datetime import datetime, timezone
from html import escape

import requests
from helai_env import load_env

from email_service import (
    MAX_ATTEMPTS,
    deadline_parts,
    email_language,
    get_one,
    get_supabase,
    isolate,
    mark_failed,
    mark_sent,
)
from helai_config import TELEGRAM_TEST_CHAT_ID, TELEGRAM_TEST_MODE
from helai_i18n import (
    RTL_LANGUAGES,
    format_percent,
    t,
    translate_match_message,
)
from opportunity_rules import effective_status
from telegram_link import (
    code_is_usable,
    is_valid_code_format,
    parse_start,
)


load_env()


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

TEST_MODE = TELEGRAM_TEST_MODE
TEST_CHAT_ID = TELEGRAM_TEST_CHAT_ID

API_BASE = "https://api.telegram.org"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRY_WAIT_SECONDS = 30
MAX_LIST_ITEMS = 3

# Error kinds. Blocked and bad-chat failures will never succeed on retry.
KIND_CONFIG = "config"
KIND_TRANSIENT = "transient"
KIND_RATE_LIMITED = "rate_limited"
KIND_BLOCKED = "blocked"
KIND_BAD_CHAT = "bad_chat"
KIND_ERROR = "error"
PERMANENT_KINDS = frozenset({KIND_BLOCKED, KIND_BAD_CHAT})

BAD_CHAT_MARKERS = (
    "chat not found",
    "user not found",
    "chat_id is empty",
    "peer_id_invalid",
    "user is deactivated",
)


# =========================================================
# BOT API
# =========================================================

def redact(value):
    """Never let the bot token reach logs or the notifications table."""
    text = str(value)
    if TELEGRAM_BOT_TOKEN:
        text = text.replace(TELEGRAM_BOT_TOKEN, "<token>")
    return text


def classify_error(status_code, description):
    description = str(description or "").lower()

    if status_code == 429:
        return KIND_RATE_LIMITED
    if status_code == 403:
        return KIND_BLOCKED
    if status_code == 400 and any(
        marker in description
        for marker in BAD_CHAT_MARKERS
    ):
        return KIND_BAD_CHAT
    if status_code >= 500:
        return KIND_TRANSIENT
    return KIND_ERROR


def _failure(kind, error, retry_after=None):
    return {
        "success": False,
        "kind": kind,
        "error": error,
        "retry_after": retry_after,
    }


def call_api(method, payload):
    if not TELEGRAM_BOT_TOKEN:
        return _failure(
            KIND_CONFIG,
            "TELEGRAM_BOT_TOKEN was not found in .env",
        )

    url = f"{API_BASE}/bot{TELEGRAM_BOT_TOKEN}/{method}"

    for attempt in range(2):
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            return _failure(
                KIND_TRANSIENT,
                f"Telegram request failed: {redact(error)}",
            )

        try:
            body = response.json()
        except ValueError:
            body = {}

        if response.status_code == 200 and body.get("ok"):
            return {
                "success": True,
                "data": body.get("result"),
            }

        description = redact(
            body.get("description")
            or response.text[:300]
        )
        kind = classify_error(response.status_code, description)
        retry_after = (body.get("parameters") or {}).get("retry_after")

        # Wait once for a short rate limit; longer ones fail and retry next run.
        if (
            kind == KIND_RATE_LIMITED
            and attempt == 0
            and isinstance(retry_after, (int, float))
            and retry_after <= MAX_RETRY_WAIT_SECONDS
        ):
            time.sleep(retry_after)
            continue

        return _failure(
            kind,
            f"Telegram API error {response.status_code}: {description}",
            retry_after,
        )


def send_message(chat_id, text, button_text=None, button_url=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }

    if (
        button_text
        and str(button_url or "").startswith(("https://", "http://"))
    ):
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": button_text, "url": button_url},
            ]]
        }

    return call_api("sendMessage", payload)


def get_updates(offset=None, limit=100):
    payload = {
        "timeout": 0,
        "limit": limit,
        "allowed_updates": ["message"],
    }
    if offset is not None:
        payload["offset"] = offset

    return call_api("getUpdates", payload)


# =========================================================
# MESSAGE CONTENT
# Same content as the email, in Telegram's basic HTML: no tables.
# =========================================================

def _text(value):
    return escape(str(value), quote=False)


def _bullets(items, lang):
    return [
        f"• {_text(translate_match_message(item, lang))}"
        for item in items[:MAX_LIST_ITEMS]
    ]


def build_message(profile, opportunity, match, lang="en", today=None):
    rtl = lang in RTL_LANGUAGES

    def latin(value):
        return isolate(value) if rtl else value

    title = str(opportunity.get("title") or t("card.opportunity", lang=lang))
    organization = str(
        opportunity.get("organization")
        or t("card.no_organization", lang=lang)
    )
    score = format_percent(int(match.get("match_score") or 0), lang)
    deadline, days_left = deadline_parts(opportunity.get("deadline"), lang, today)
    reasons = list(match.get("reasons") or [])
    missing = (
        list(match.get("eligibility_gaps") or [])
        + list(match.get("readiness_gaps") or [])
    )

    eligible_line = (
        f"✅ {_text(t('email.eligible', lang=lang))}"
        if match.get("eligible")
        else f"⚠️ {_text(t('email.not_eligible', lang=lang))}"
    )

    deadline_line = f"{_text(t('field.deadline', lang=lang))}: <b>{_text(deadline)}</b>"
    if days_left:
        deadline_line += f" · {_text(days_left)}"

    lines = [
        f"✨ <b>{_text(t('email.new_match', lang=lang))}</b> · {_text(latin('HelAI'))}",
        "",
        f"<b>{_text(title)}</b>",
        f"{_text(t('email.organization', lang=lang))}: {_text(latin(organization))}",
        f"{_text(t('field.match', lang=lang))}: <b>{_text(score)}</b>",
        eligible_line,
        "",
        f"<b>{_text(t('card.why_it_fits', lang=lang))}</b>",
        *(_bullets(reasons, lang) or [_text(t("card.why_empty", lang=lang))]),
        "",
        f"<b>{_text(t('email.still_missing', lang=lang))}</b>",
        *(_bullets(missing, lang) or [_text(t("email.nothing_missing", lang=lang))]),
        "",
        deadline_line,
        "",
        f"<i>{_text(t('telegram.footer', lang=lang))}</i>",
    ]

    return "\n".join(lines)


# =========================================================
# SAFETY SWITCH
# =========================================================

def recipient_chat_id(connection_chat_id):
    """Test mode routes everything to TELEGRAM_TEST_CHAT_ID, or nowhere."""
    if TEST_MODE:
        return TEST_CHAT_ID or None
    return connection_chat_id


def may_message_chat(chat_id):
    if TEST_MODE:
        return bool(TEST_CHAT_ID) and str(chat_id) == str(TEST_CHAT_ID)
    return True


# =========================================================
# ACCOUNT LINKING (/start CODE)
# =========================================================

def time_now_iso():
    return datetime.now(timezone.utc).isoformat()


def message_language(message):
    code = str((message.get("from") or {}).get("language_code") or "").lower()
    if code.startswith("ar"):
        return "ar"
    if code.startswith("en"):
        return "en"
    return "ckb"


def reply(chat_id, key, lang):
    if not may_message_chat(chat_id):
        return None
    return send_message(chat_id, _text(t(key, lang=lang)))


def find_link_code(client, code):
    response = (
        client
        .table("telegram_link_codes")
        .select("*")
        .eq("code", code)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def claim_code(client, code, now):
    """Mark the code used; False when another run already used it."""
    response = (
        client
        .table("telegram_link_codes")
        .update({"used_at": now})
        .eq("code", code)
        .is_("used_at", "null")
        .execute()
    )
    return bool(response.data)


def save_connection(client, user_id, chat_id, now):
    (
        client
        .table("telegram_connections")
        .upsert(
            {
                "user_id": user_id,
                "chat_id": chat_id,
                "connected_at": now,
            },
            on_conflict="user_id",
        )
        .execute()
    )
    (
        client
        .table("profiles")
        .update({"notify_telegram": True})
        .eq("id", user_id)
        .execute()
    )


def remove_connection(client, user_id):
    (
        client
        .table("telegram_connections")
        .delete()
        .eq("user_id", user_id)
        .execute()
    )
    (
        client
        .table("profiles")
        .update({"notify_telegram": False})
        .eq("id", user_id)
        .execute()
    )


def load_chat_id(client, user_id):
    response = (
        client
        .table("telegram_connections")
        .select("chat_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return response.data[0]["chat_id"] if response.data else None


def handle_start(client, message, now):
    """Returns 'linked', 'invalid', 'hint' or 'ignored'."""
    chat = message.get("chat") or {}
    if chat.get("type") != "private":
        return "ignored"

    is_start, code = parse_start(message.get("text"))
    if not is_start:
        return "ignored"

    chat_id = chat.get("id")
    lang = message_language(message)

    if not code:
        reply(chat_id, "telegram.start_hint", lang)
        return "hint"

    code_row = (
        find_link_code(client, code)
        if is_valid_code_format(code)
        else None
    )

    if (
        not code_is_usable(code_row, message.get("date"))
        or not claim_code(client, code, now)
    ):
        reply(chat_id, "telegram.link_invalid", lang)
        return "invalid"

    user_id = code_row["user_id"]
    save_connection(client, user_id, chat_id, now)

    profile = get_one(client, "profiles", user_id)
    if profile:
        lang = email_language(profile)

    print("LINKED: user", user_id)
    reply(chat_id, "telegram.linked", lang)
    return "linked"


def process_link_codes(client=None, now=None):
    print()
    print("========================================")
    print("       HELAI TELEGRAM LINKING")
    print("========================================")

    counts = {"linked": 0, "invalid": 0, "hint": 0, "ignored": 0, "errors": 0}

    if not TELEGRAM_BOT_TOKEN:
        print("SKIPPED: TELEGRAM_BOT_TOKEN was not found in .env")
        return {**counts, "skipped": True}

    updates_result = get_updates()
    if not updates_result["success"]:
        print("ERROR:", updates_result["error"])
        return {**counts, "error": updates_result["error"]}

    updates = updates_result.get("data") or []
    print("Updates:", len(updates))

    if not updates:
        return counts

    client = client or get_supabase()
    now = now or time_now_iso()

    for update in updates:
        try:
            outcome = handle_start(
                client,
                update.get("message") or {},
                now,
            )
        except Exception as error:
            outcome = "errors"
            print("ERROR:", redact(error))
        counts[outcome] += 1

    # Confirm everything read so far, so the next run starts after it.
    last_update_id = max(update.get("update_id", 0) for update in updates)
    get_updates(offset=last_update_id + 1, limit=1)

    print("Linked:", counts["linked"])
    print("Invalid or expired:", counts["invalid"])
    print("Errors:", counts["errors"])
    return counts


# =========================================================
# DELIVERY
# =========================================================

def send_pending_telegram():
    print()
    print("========================================")
    print("       HELAI TELEGRAM DELIVERY")
    print("========================================")
    print()

    if not TELEGRAM_BOT_TOKEN:
        print("SKIPPED: TELEGRAM_BOT_TOKEN was not found in .env")
        return {
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "ready": 0,
            "test_mode": TEST_MODE,
        }

    client = get_supabase()

    result = (
        client
        .table("notifications")
        .select("*")
        .eq("channel", "telegram")
        .execute()
    )

    notifications = [
        item
        for item in (result.data or [])
        if item.get("status") in ["pending", "failed"]
        and (item.get("attempts") or 0) < MAX_ATTEMPTS
    ]

    print("Notifications ready:", len(notifications))
    print()

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for notification in notifications:
        print("----------------------------------------")

        profile = get_one(client, "profiles", notification["user_id"])
        opportunity = get_one(client, "opportunities", notification["opportunity_id"])
        match = get_one(client, "matches", notification["match_id"])

        skip_reason = None
        if not profile:
            skip_reason = "Profile not found"
        elif not opportunity:
            skip_reason = "Opportunity not found"
        elif not match:
            skip_reason = "Match not found"
        elif effective_status(opportunity) != "Open":
            skip_reason = "Opportunity is not open"
        elif not match.get("eligible", False):
            skip_reason = "Match is not eligible"
        elif not profile.get("notify_telegram", False):
            skip_reason = "Telegram notifications disabled"

        connection_chat_id = None
        if not skip_reason:
            connection_chat_id = load_chat_id(client, notification["user_id"])
            if not connection_chat_id:
                skip_reason = "Telegram not connected"

        chat_id = None
        if not skip_reason:
            chat_id = recipient_chat_id(connection_chat_id)
            if not chat_id:
                skip_reason = (
                    "TELEGRAM_TEST_MODE is true but "
                    "TELEGRAM_TEST_CHAT_ID is empty"
                )

        if skip_reason:
            print("SKIPPED:", skip_reason)
            skipped_count += 1
            continue

        lang = email_language(profile)
        text = build_message(profile, opportunity, match, lang)

        print("Opportunity:", opportunity.get("title") or "Opportunity")
        print("HelAI user:", notification["user_id"])
        print("Sending to:", "test chat" if TEST_MODE else "user chat")
        print("Match score:", f"{match.get('match_score', 0)}%")

        send_result = send_message(
            chat_id,
            text,
            button_text=t("email.view", lang=lang),
            button_url=opportunity.get("source_url"),
        )

        if send_result["success"]:
            mark_sent(client, notification, match)
            print("SENT: True")
            sent_count += 1
        else:
            # In test mode the failing chat is the test chat, not the user's.
            permanent = (
                send_result.get("kind") in PERMANENT_KINDS
                and not TEST_MODE
            )
            mark_failed(
                client,
                notification,
                send_result["error"],
                final=permanent,
            )
            if permanent:
                remove_connection(client, notification["user_id"])
                print("Telegram connection removed for this user.")
            print("SENT: False")
            print("ERROR:", send_result["error"])
            failed_count += 1

        print()

    print("========================================")
    print("Sent:", sent_count)
    print("Failed:", failed_count)
    print("Skipped:", skipped_count)
    print()

    return {
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "ready": len(notifications),
        "test_mode": TEST_MODE,
    }


if __name__ == "__main__":
    print("Run the full HelAI pipeline instead of this module.")
