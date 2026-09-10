from pathlib import Path
import shutil
import sys


APP_FILE = Path("app.py")
BACKUP_FILE = Path("app_before_kurdish_summaries.py")

MARKER = "# HELAI LOCALIZED OPPORTUNITY SUMMARY"


if not APP_FILE.exists():
    print("ERROR: app.py was not found.")
    print(
        "Run this script from the opportunity-ai "
        "project folder."
    )
    sys.exit(1)


text = APP_FILE.read_text(
    encoding="utf-8"
)


if MARKER in text:
    print()
    print("Kurdish summary support is already installed.")
    print()
    sys.exit(0)


if not BACKUP_FILE.exists():
    shutil.copy2(
        APP_FILE,
        BACKUP_FILE
    )


loop_anchor = """    for index, (
        opportunity,
        result
    ) in enumerate(
        results,
        start=1
    ):
"""


loop_position = text.find(
    loop_anchor
)


if loop_position == -1:
    print(
        "ERROR: Could not find the opportunity "
        "results loop."
    )
    sys.exit(1)


metrics_anchor = (
    "        c1, c2, c3, c4 = st.columns(4)"
)


metrics_position = text.find(
    metrics_anchor,
    loop_position
)


if metrics_position == -1:
    print(
        "ERROR: Could not find the opportunity "
        "metrics section."
    )
    sys.exit(1)


localized_summary_block = r'''
        # HELAI LOCALIZED OPPORTUNITY SUMMARY

        active_language = str(
            (
                st.session_state.cloud_profile
                or {}
            ).get(
                "preferred_language",
                "English"
            )
        ).strip()


        summary_ku = str(
            opportunity.get(
                "summary_ku"
            )
            or ""
        ).strip()


        summary_en = str(
            opportunity.get(
                "summary_en"
            )
            or ""
        ).strip()


        summary_notes = str(
            opportunity.get(
                "notes"
            )
            or ""
        ).strip()


        if (
            active_language
            == "Kurdish Sorani"
            and summary_ku
        ):

            summary_safe = (
                html.escape(
                    summary_ku
                )
                .replace(
                    "\n",
                    "<br>"
                )
            )


            st.html(
                f"""
<div
    dir="rtl"
    style="
        margin: 16px 0 24px 0;
        padding: 20px 22px;

        background:
            rgba(15, 23, 52, 0.78);

        border:
            1px solid
            rgba(130, 151, 255, 0.24);

        border-radius: 14px;

        direction: rtl;
        text-align: right;

        font-family:
            Tahoma,
            Arial,
            sans-serif;

        line-height: 2;

        color: #e9edfa;
    "
>

    <div
        style="
            margin-bottom: 10px;

            color: #42e5dd;

            font-size: 12px;
            font-weight: 700;

            letter-spacing: 0.4px;
        "
    >
        پوختەی کوردی
    </div>


    <div
        style="
            font-size: 16px;
        "
    >
        {summary_safe}
    </div>

</div>
"""
            )


        elif summary_en or summary_notes:

            summary_text = (
                summary_en
                or summary_notes
            )


            st.markdown(
                "#### ABOUT THIS OPPORTUNITY"
            )


            st.write(
                summary_text
            )


'''


updated_text = (
    text[:metrics_position]
    + localized_summary_block
    + text[metrics_position:]
)


APP_FILE.write_text(
    updated_text,
    encoding="utf-8"
)


print()
print("========================================")
print("     HELAI KURDISH APP UPDATE")
print("========================================")
print()
print("Updated: app.py")
print(
    "Backup:",
    BACKUP_FILE
)
print()
print(
    "Kurdish opportunity summaries "
    "were added successfully."
)
print()