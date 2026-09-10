import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# =========================================================
# CONFIGURATION
# =========================================================

SOURCE_NAME = "Opportunity Desk"

SOURCE_URL = "https://opportunitydesk.org/"

MAX_RESULTS = 10

REQUEST_TIMEOUT = 20


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/130.0 Safari/537.36 "
        "HelAI/1.0"
    )
}


OPPORTUNITY_KEYWORDS = (
    "scholarship",
    "fellowship",
    "internship",
    "traineeship",
    "competition",
    "challenge",
    "grant",
    "award",
    "accelerator",
    "incubator",
    "programme",
    "program",
    "training",
    "exchange",
    "volunteer",
    "volunteering",
    "call for applications",
    "young professionals",
    "young leaders",
    "campus ambassador",
)


ARTICLE_PATH_PATTERN = re.compile(
    r"^/\d{4}/\d{2}/\d{2}/[^/]+/?$"
)


# =========================================================
# HELPERS
# =========================================================

def clean_text(value):
    return " ".join(
        value.split()
    ).strip()


def is_opportunity_title(title):
    title_lower = title.lower()

    return any(
        keyword in title_lower
        for keyword in OPPORTUNITY_KEYWORDS
    )


def is_article_url(url):
    parsed = urlparse(url)

    if parsed.netloc not in {
        "opportunitydesk.org",
        "www.opportunitydesk.org"
    }:
        return False

    return bool(
        ARTICLE_PATH_PATTERN.match(
            parsed.path
        )
    )


# =========================================================
# DISCOVER OPPORTUNITIES
# =========================================================

def discover_opportunities(
    limit=MAX_RESULTS
):
    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    results = []

    seen_urls = set()

    for link in soup.find_all(
        "a",
        href=True
    ):
        title = clean_text(
            link.get_text(
                " ",
                strip=True
            )
        )

        if not title:
            continue

        url = urljoin(
            SOURCE_URL,
            link["href"]
        )

        url = url.split("#")[0]

        if url in seen_urls:
            continue

        if not is_article_url(url):
            continue

        if not is_opportunity_title(title):
            continue

        seen_urls.add(url)

        results.append(
            {
                "title": title,
                "url": url,
                "source_name": SOURCE_NAME
            }
        )

        if len(results) >= limit:
            break

    return results


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    print()
    print("====================================")
    print("     HelAI Opportunity Discovery")
    print("====================================")
    print()

    try:
        opportunities = discover_opportunities()

        print(
            "Opportunities found:",
            len(opportunities)
        )
        print()

        for index, opportunity in enumerate(
            opportunities,
            start=1
        ):
            print(
                f"{index}. {opportunity['title']}"
            )

            print(
                f"   {opportunity['url']}"
            )

            print()

    except Exception as error:
        print(
            "Discovery failed:",
            error
        )
        print()