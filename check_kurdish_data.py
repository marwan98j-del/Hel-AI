from opportunity_service import load_opportunities


def main():
    opportunities = load_opportunities()

    for opportunity in opportunities:
        if opportunity.get("title") == "AI Olympiad Kurdistan 2026":

            print()
            print("========================================")
            print("       HELAI KURDISH DATA CHECK")
            print("========================================")
            print()

            print(
                "Title:",
                opportunity.get("title")
            )

            print(
                "Has summary_ku:",
                bool(
                    opportunity.get("summary_ku")
                )
            )

            print()
            print("summary_ku:")
            print(
                opportunity.get("summary_ku")
            )

            print()
            print(
                "Available fields:"
            )

            print(
                sorted(
                    opportunity.keys()
                )
            )

            print()

            return

    print(
        "AI Olympiad Kurdistan 2026 was not found."
    )


if __name__ == "__main__":
    main()