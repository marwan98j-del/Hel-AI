import requests
from bs4 import BeautifulSoup

from ukri_discovery import discover_ukri_opportunities


TIMEOUT = 30
MAX_ARTICLE_CHARACTERS = 16000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/120 Safari/537.36 "
        "HelAI/1.0"
    )
}


def clean_text(value):
    if not value:
        return ""

    lines = []

    for raw_line in str(value).splitlines():
        line = " ".join(
            raw_line.split()
        ).strip()

        if not line:
            continue

        lines.append(line)

    return "\n".join(lines)


def read_ukri_opportunity(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    for unwanted in soup.select(
        (
            "script, "
            "style, "
            "noscript, "
            "svg, "
            "nav, "
            "header, "
            "footer, "
            "form"
        )
    ):
        unwanted.decompose()

    content = (
        soup.find("main")
        or soup.find("article")
        or soup.body
    )

    if not content:
        raise ValueError(
            "UKRI page content could not be found."
        )

    text = clean_text(
        content.get_text(
            "\n",
            strip=True
        )
    )

    if len(text) < 300:
        raise ValueError(
            "UKRI article text was unexpectedly short."
        )

    return text[:MAX_ARTICLE_CHARACTERS]


def choose_test_opportunity(opportunities):
    for opportunity in opportunities:
        title = (
            opportunity
            .get("title", "")
            .lower()
        )

        if "invite only" in title:
            continue

        if "pre-announcement" in title:
            continue

        return opportunity

    if opportunities:
        return opportunities[0]

    return None


def main():
    print()
    print("========================================")
    print("       HELAI UKRI ARTICLE TEST")
    print("========================================")
    print()

    print("Discovering UKRI opportunities...")

    opportunities = discover_ukri_opportunities(
        limit=10
    )

    test_opportunity = choose_test_opportunity(
        opportunities
    )

    if not test_opportunity:
        print()
        print("ERROR: No UKRI opportunity found.")
        return

    print()
    print(
        "Selected:",
        test_opportunity["title"]
    )

    print(
        "URL:",
        test_opportunity["url"]
    )

    print()
    print("Reading full UKRI page...")
    print()

    try:
        text = read_ukri_opportunity(
            test_opportunity["url"]
        )

    except Exception as error:
        print(
            "Reading failed:",
            str(error)
        )
        return

    print(
        "Characters read:",
        len(text)
    )

    print()
    print("========================================")
    print("             TEXT PREVIEW")
    print("========================================")
    print()

    print(
        text[:4000]
    )

    print()
    print("========================================")
    print("UKRI article reader: SUCCESS")
    print("========================================")
    print()


if __name__ == "__main__":
    main()