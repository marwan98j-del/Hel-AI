"""Limits on the app's AI import, so one visitor can't run up the OpenAI bill.

Pure functions over a dict-like state (st.session_state in the app), so they
can be tested without Streamlit. The collector's own extraction is not limited.
"""

import math
import time

from helai_config import (
    HELAI_IMPORT_MAX_CHARS,
    HELAI_IMPORT_RUNS_PER_HOUR,
)


MAX_CHARS = HELAI_IMPORT_MAX_CHARS
RUNS_PER_HOUR = HELAI_IMPORT_RUNS_PER_HOUR
WINDOW_SECONDS = 60 * 60
RUNS_KEY = "helai_import_runs"


def recent_runs(state, now=None):
    """Run times within the last hour, oldest first."""
    now = time.time() if now is None else now
    return sorted(
        moment
        for moment in state.get(RUNS_KEY, [])
        if now - moment < WINDOW_SECONDS
    )


def import_block(state, text, now=None):
    """None when the import may run, else (translation key, values for it)."""
    now = time.time() if now is None else now

    if len(text) > MAX_CHARS:
        return "import.too_long", {"limit": MAX_CHARS}

    runs = recent_runs(state, now)
    if len(runs) >= RUNS_PER_HOUR:
        wait_seconds = runs[-RUNS_PER_HOUR] + WINDOW_SECONDS - now
        return "import.rate_limited", {
            "count": RUNS_PER_HOUR,
            "minutes": max(1, math.ceil(wait_seconds / 60)),
        }

    return None


def record_run(state, now=None):
    """Count a run before calling OpenAI, so failed calls count too."""
    now = time.time() if now is None else now
    state[RUNS_KEY] = recent_runs(state, now) + [now]
