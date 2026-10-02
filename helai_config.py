import os

from dotenv import load_dotenv


load_dotenv(override=True)


def get_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_int(name, default):
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(str(value).strip())
    except ValueError:
        return default


def get_float(name, default):
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return float(str(value).strip())
    except ValueError:
        return default


def get_str(name, default=""):
    value = os.getenv(name)

    if value is None:
        return default

    return str(value).strip()


HELAI_CHECK_INTERVAL_MINUTES = get_int(
    "HELAI_CHECK_INTERVAL_MINUTES",
    180,
)

HELAI_MATCH_THRESHOLD = get_int(
    "HELAI_MATCH_THRESHOLD",
    70,
)

HELAI_SOURCE_LIMIT = get_int(
    "HELAI_SOURCE_LIMIT",
    10,
)

HELAI_MAX_NEW_PER_SOURCE = get_int(
    "HELAI_MAX_NEW_PER_SOURCE",
    3,
)

HELAI_REQUEST_TIMEOUT_SECONDS = get_int(
    "HELAI_REQUEST_TIMEOUT_SECONDS",
    30,
)

HELAI_REQUEST_DELAY_SECONDS = get_float(
    "HELAI_REQUEST_DELAY_SECONDS",
    1.0,
)

EMAIL_TEST_MODE = get_bool(
    "EMAIL_TEST_MODE",
    True,
)

EMAIL_TEST_RECIPIENT = get_str(
    "EMAIL_TEST_RECIPIENT",
    "",
)

HELAI_APP_URL = get_str(
    "HELAI_APP_URL",
    "http://localhost:8501",
).rstrip("/")

EMAIL_FROM = get_str(
    "EMAIL_FROM",
    "HelAI <onboarding@resend.dev>",
)

HELAI_IMPORT_MAX_CHARS = get_int(
    "HELAI_IMPORT_MAX_CHARS",
    12000,
)

HELAI_IMPORT_RUNS_PER_HOUR = get_int(
    "HELAI_IMPORT_RUNS_PER_HOUR",
    5,
)

TELEGRAM_TEST_MODE = get_bool(
    "TELEGRAM_TEST_MODE",
    True,
)

TELEGRAM_TEST_CHAT_ID = get_str(
    "TELEGRAM_TEST_CHAT_ID",
    "",
)

TELEGRAM_BOT_USERNAME = get_str(
    "TELEGRAM_BOT_USERNAME",
    "HelAIOpportunityBot",
).lstrip("@")
