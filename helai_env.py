"""Load HelAI's .env: everything for the collector, only what it needs for the app.

The web app calls use_app_secrets() before importing anything else from the
project. From then on, load_env() puts only the Supabase URL, the publishable
key, the OpenAI key and non-secret HELAI_* settings into the process, and
removes the collector's secrets (service key, Resend, Telegram) even when they
were inherited from the shell. Everything else keeps loading the whole file.
"""

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


ENV_FILE = Path(
    os.getenv("HELAI_ENV_FILE")
    or Path(__file__).with_name(".env")
)

# What the web app is allowed to see.
APP_SECRETS = frozenset({
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "OPENAI_API_KEY",
})
APP_SETTINGS = frozenset({
    "TELEGRAM_BOT_USERNAME",
})
APP_SETTING_PREFIX = "HELAI_"

# Collector-only secrets: never in the app's process.
COLLECTOR_SECRETS = frozenset({
    "SUPABASE_SECRET_KEY",
    "RESEND_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_TEST_CHAT_ID",
    "EMAIL_TEST_RECIPIENT",
})

_app_mode = False


def app_allows(name):
    if name in COLLECTOR_SECRETS:
        return False
    return (
        name in APP_SECRETS
        or name in APP_SETTINGS
        or name.startswith(APP_SETTING_PREFIX)
    )


def use_app_secrets():
    """Switch this process to app mode and load the app's subset now."""
    global _app_mode
    _app_mode = True
    load_env()


def load_env():
    if not _app_mode:
        load_dotenv(ENV_FILE, override=True)
        return

    values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}

    for name, value in values.items():
        if app_allows(name) and value is not None:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)

    for name in COLLECTOR_SECRETS:
        os.environ.pop(name, None)
