import time

from collector_client import collector_supabase
from collector_service import analyze_and_save
from opportunity_desk_article import extract_article
from opportunity_desk_discovery import discover_opportunities


# =========================================================
# CONFIGURATION
# =========================================================

MAX_NEW_IMPORTS = 3

ARTICLE_CHARACTER_LIMIT = 12000

DELAY_BETWEEN_ARTICLES = 1


# =========================================================
# CHECK DATABASE
# =========================================================

def already_imported(source_url):

    response = (
        collector_supabase
        .table("opportunities")
        .select("id,title")
        .eq("source_url", source_url)
        .limit(1)
        .execute()
    )

    return bool(response.data)


# =========================================================
# AUTOMATIC COLLECTION
# =========================================================

def run_collector():

    print()
    print("====================================")
    print("       HelAI Automatic Collector")
    print("====================================")
    print()

    print("Discovering opportunities...")
    print()

    discovered = discover_opportunities(
        limit=10
    )

    print(
        "Discovered:",
        len(discovered)
    )

    print()

    imported_count = 0
    skipped_count = 0
    failed_count = 0

    for item in discovered:

        if imported_count >= MAX_NEW_IMPORTS:
            break

        title = item["title"]
        url = item["url"]

        print("------------------------------------")
        print("Candidate:", title)
        print("URL:", url)

        # -------------------------------------------------
        # SKIP EXISTING OPPORTUNITIES
        # -------------------------------------------------

        try:

            if already_imported(url):

                print(
                    "Result: Already in Supabase. Skipped."
                )

                skipped_count += 1

                print()

                continue

        except Exception as error:

            print(
                "Database check failed:",
                error
            )

            failed_count += 1

            print()

            continue

        # -------------------------------------------------
        # READ ARTICLE
        # -------------------------------------------------

        try:

            print(
                "Reading article..."
            )

            article = extract_article(
                url
            )

        except Exception as error:

            print(
                "Article reading failed:",
                error
            )

            failed_count += 1

            print()

            continue

        # -------------------------------------------------
        # PREPARE TEXT FOR AI
        # -------------------------------------------------

        announcement_text = (
            article["title"]
            + "\n\n"
            + article["text"]
        )

        announcement_text = (
            announcement_text[
                :ARTICLE_CHARACTER_LIMIT
            ]
        )

        # -------------------------------------------------
        # AI + SUPABASE
        # -------------------------------------------------

        try:

            print(
                "AI is understanding the opportunity..."
            )

            result = analyze_and_save(
                announcement_text=announcement_text,
                source_name="Opportunity Desk",
                source_url=url
            )

            opportunity = result[
                "opportunity"
            ]

            print(
                "Result:",
                result["action"]
            )

            print(
                "AI title:",
                opportunity.get("title")
            )

            print(
                "Type:",
                opportunity.get("type")
            )

            print(
                "Deadline:",
                opportunity.get("deadline")
            )

            imported_count += 1

        except Exception as error:

            print(
                "AI import failed:",
                error
            )

            failed_count += 1

        print()

        time.sleep(
            DELAY_BETWEEN_ARTICLES
        )

    # =====================================================
    # SUMMARY
    # =====================================================

    print()
    print("====================================")
    print("            RUN SUMMARY")
    print("====================================")
    print(
        "New opportunities imported:",
        imported_count
    )
    print(
        "Existing opportunities skipped:",
        skipped_count
    )
    print(
        "Failures:",
        failed_count
    )
    print("====================================")
    print()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    run_collector()