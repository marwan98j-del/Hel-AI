"""Telegram account linking shared by the app and the collector.

The app creates a short-lived code (with the user's own Supabase session) and
shows a t.me deep link. The user presses Start; while the profile is open the
app starts telegram_link_now.py every few seconds, which matches the code to
the profile and saves the chat id. Every collector run does the same check, as
a fallback. No bot token here: the check runs in its own process.
"""

import re
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from helai_config import TELEGRAM_BOT_USERNAME


# No 0/O or 1/I: codes may be read aloud or typed. 12 characters is about
# 60 bits, so guessing a live code within its lifetime is impractical.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 12
LINK_CODE_MINUTES = 30
# The app swaps in a new code after this, so the bot button never carries a
# code that runs out while the user is still in Telegram.
CODE_REUSE_MINUTES = 20

# How often an open profile checks the bot, across all sessions together.
LINK_CHECK_SECONDS = 4
LINK_NOW_SCRIPT = Path(__file__).with_name("telegram_link_now.py")

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


def code_is_fresh(created_at, now=None):
    """True while the app may keep showing this code in the bot button."""
    created = parse_timestamp(created_at)
    if created is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now < created + timedelta(minutes=CODE_REUSE_MINUTES)


class LinkCheckRunner:
    """Starts telegram_link_now.py: one at a time, at most every few seconds.

    The check needs the bot token and the service key, which never enter the
    web app's process; the child loads the collector's .env on its own. One
    runner serves every session, so many open profiles still mean one check.
    """

    def __init__(
        self,
        command=None,
        min_interval=LINK_CHECK_SECONDS,
        clock=time.monotonic,
        popen=subprocess.Popen,
    ):
        self.command = command or [sys.executable, str(LINK_NOW_SCRIPT)]
        self.min_interval = min_interval
        self.clock = clock
        self.popen = popen
        self.lock = threading.Lock()
        self.process = None
        self.started = None

    def request(self):
        """Start a check unless one is running or started moments ago."""
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                return False

            now = self.clock()
            if (
                self.started is not None
                and now - self.started < self.min_interval
            ):
                return False

            self.started = now
            self.process = self.popen(
                self.command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True


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
