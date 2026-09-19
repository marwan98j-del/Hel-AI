import time
from datetime import datetime, timedelta

from helai_config import HELAI_CHECK_INTERVAL_MINUTES
from helai_pipeline import run_full_cycle


def main():
    interval_seconds = max(
        15 * 60,
        HELAI_CHECK_INTERVAL_MINUTES * 60,
    )

    print()
    print("========================================")
    print("HELAI BACKGROUND AGENT STARTED")
    print(
        "Check interval:",
        f"{HELAI_CHECK_INTERVAL_MINUTES} minutes",
    )
    print("Press Ctrl+C to stop.")
    print("========================================")

    try:
        while True:
            print()
            print(
                "Starting scan:",
                datetime.now().isoformat(
                    timespec="seconds"
                ),
            )

            run_full_cycle()

            next_run = (
                datetime.now()
                + timedelta(seconds=interval_seconds)
            )

            print()
            print(
                "Next scan:",
                next_run.isoformat(
                    timespec="seconds"
                ),
            )

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print()
        print("HelAI background agent stopped.")


if __name__ == "__main__":
    main()
