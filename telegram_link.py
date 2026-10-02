"""Telegram account linking shared by the app and the collector.

The app creates a short-lived code (with the user's own Supabase session) and
shows a t.me deep link. The user presses Start, and the next collector run
matches the code to the profile and saves the chat id. No bot token here.
"""

import re
import secrets
from datetime import datetime, timedelta, timezone

from helai_config import TELEGRAM_BOT_USERNAME


# No 0/O or 1/I: codes may be read aloud or typed. 12 characters is about
# 60 bits, so guessing a live code within its lifetime is impractical.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 12
LINK_CODE_MINUTES = 30

START_PATTERN = re.compile(
    r"^/start(?:@\w+)?(?:\s+(\S+))?\s*$",
    re.IGNORECASE,
)


def generate_code():
    return "".join(
        secrets.choice(CODE_ALPHABET)
        for _ in range(CODE_LENGTH)
    )


def is_valid_code_format(code):
    return (
        isinstance(code, str)
        and len(code) == CODE_LENGTH
        and all(char in CODE_ALPHABET for char in code)
    )


def bot_link(code):
    return f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={code}"


def parse_start(text):
    """(is_start, code) for '/start CODE'; the code is None when missing."""
    match = START_PATTERN.match(str(text or "").strip())
    if not match:
        return False, None

    code = (match.group(1) or "").strip().upper()
    return True, code or None


def parse_timestamp(value):
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, (int, float)):
        moment = datetime.fromtimestamp(value, timezone.utc)
    elif isinstance(value, str) and value.strip():
        moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        return None

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def code_is_usable(code_row, pressed_at):
    """Unused and not expired when the user pressed Start.

    Expiry is judged by the Telegram message time, not by when the collector
    runs, because the collector may only run every few hours.
    """
    if not code_row or code_row.get("used_at"):
        return False

    expires_at = parse_timestamp(code_row.get("expires_at"))
    pressed = parse_timestamp(pressed_at)
    if expires_at is None or pressed is None:
        return False

    return pressed <= expires_at


def code_is_pending(created_at, now=None):
    """True while a code shown in the app can still be used."""
    created = parse_timestamp(created_at)
    if created is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now < created + timedelta(minutes=LINK_CODE_MINUTES)


# =========================================================
# APP SIDE (the user's own authenticated Supabase client)
# Row-level security limits these calls to the user's rows.
# =========================================================

def create_link_code(client, user_id):
    """Insert a new code; the database sets expires_at to now + 30 minutes."""
    code = generate_code()
    (
        client
        .table("telegram_link_codes")
        .insert({"code": code, "user_id": user_id})
        .execute()
    )
    return code


def load_connection(client, user_id):
    response = (
        client
        .table("telegram_connections")
        .select("user_id,connected_at")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def disconnect(client, user_id):
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
