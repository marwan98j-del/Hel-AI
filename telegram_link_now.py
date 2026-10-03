"""Link Telegram accounts now: one check of the bot's updates.

The web app starts this while a user is connecting Telegram, in its own
process, so the bot token and the service key never enter the app. It loads
the collector's .env like any collector script. Collector runs do the same
check as a fallback.
"""

import contextlib
import io
import sys

from telegram_service import process_link_codes


def main():
    # The full report is for collector logs; here only results worth reading.
    report = io.StringIO()
    with contextlib.redirect_stdout(report):
        counts = process_link_codes()

    if counts.get("error") or counts.get("errors"):
        print(report.getvalue(), file=sys.stderr)
    elif counts.get("linked"):
        print("HelAI Telegram: linked", counts["linked"], file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
