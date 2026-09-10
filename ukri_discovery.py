from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup


UKRI_OPPORTUNITIES_URL = (
    "https://www.ukri.org/opportunity/"
)

TIMEOUT = 30

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
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    return response.text


def find_rss_feed():
    html = get_page(
        UKRI_OPPORTUNITIES_URL
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    for link in soup.find_all(
        "a",
        href=True
    ):
        text = clean_text(
            link.get_text(" ")
        ).lower()

        href = link.get(
            "href",
            ""
        )

        if (
            "rss" in text
            or "rss" in href.lower()
            or "feed" in href.lower()
        ):
            possible_url = urljoin(
                UKRI_OPPORTUNITIES_URL,
                href
            )

            if (
                "ukri.org" in possible_url
                and (
                    "opportunity" in possible_url
                    or "feed" in possible_url
                    or "rss" in possible_url
                )
            ):
                return possible_url

    return None


def parse_rss_feed(feed_url):
    xml_text = get_page(
        feed_url
    )

    root = ET.fromstring(
        xml_text
    )

    discovered = []

    for item in root.iter():

        tag = item.tag.lower()

        if not tag.endswith(
            "item"
        ):
            continue

        title = ""
        link = ""
        published = ""
        description = ""

        for child in item:

            child_tag = (
                child.tag
                .split("}")[-1]
                .lower()
            )

            value = clean_text(
                child.text
            )

            if child_tag == "title":
                title = value

            elif child_tag == "link":
                link = value

            elif child_tag in [
                "pubdate",
                "published",
                "updated"
            ]:
                published = value

            elif child_tag in [
                "description",
                "summary"
            ]:
                description = value

        if not title:
            continue

        if not link:
            continue

        if "ukri.org" not in link:
            continue

        if "/opportunity/" not in link:
            continue

        if (
            link.rstrip("/")
            ==
            UKRI_OPPORTUNITIES_URL.rstrip("/")
        ):
            continue

        discovered.append(
            {
                "title": title,
                "url": link,
                "published": published,
                "description": description,
            }
        )

    return discovered


def discover_from_html():
    html = get_page(
        UKRI_OPPORTUNITIES_URL
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    results = []
    seen = set()

    for link in soup.find_all(
        "a",
        href=True
    ):
        href = urljoin(
            UKRI_OPPORTUNITIES_URL,
            link["href"]
        )

        title = clean_text(
            link.get_text(" ")
        )

        if not title:
            continue

        if "ukri.org" not in href:
            continue

        if "/opportunity/" not in href:
            continue

        normalized = (
            href
            .split("#")[0]
            .split("?")[0]
            .rstrip("/")
        )

        if (
            normalized
            ==
            UKRI_OPPORTUNITIES_URL.rstrip("/")
        ):
            continue

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        results.append(
            {
                "title": title,
                "url": normalized + "/",
                "published": "",
                "description": "",
            }
        )

    return results


def discover_ukri_opportunities(
    limit=10
):
    rss_url = None

    try:
        rss_url = find_rss_feed()

    except Exception as error:
        print(
            "RSS discovery warning:",
            str(error)
        )

    opportunities = []

    if rss_url:

        print(
            "RSS feed:",
            rss_url
        )

        try:
            opportunities = (
                parse_rss_feed(
                    rss_url
                )
            )

        except Exception as error:
            print(
                "RSS parse warning:",
                str(error)
            )

    if not opportunities:

        print(
            "Using UKRI HTML fallback..."
        )

        opportunities = (
            discover_from_html()
        )

    unique = []
    seen_urls = set()

    for opportunity in opportunities:

        url = opportunity[
            "url"
        ].rstrip("/")

        if url in seen_urls:
            continue

        seen_urls.add(url)

        unique.append(
            opportunity
        )

        if len(unique) >= limit:
            break

    return unique


def main():

    print()
    print(
        "========================================"
    )
    print(
        "       HELAI UKRI DISCOVERY TEST"
    )
    print(
        "========================================"
    )
    print()

    print(
        "Source:",
        UKRI_OPPORTUNITIES_URL
    )

    print()
    print(
        "Discovering official UKRI opportunities..."
    )
    print()

    try:
        opportunities = (
            discover_ukri_opportunities(
                limit=10
            )
        )

    except Exception as error:

        print(
            "Discovery failed:",
            str(error)
        )

        return

    print()
    print(
        "Discovered:",
        len(opportunities)
    )
    print()

    for index, opportunity in enumerate(
        opportunities,
        start=1
    ):

        print(
            "----------------------------------------"
        )

        print(
            f"{index}."
        )

        print(
            "Title:",
            opportunity["title"]
        )

        print(
            "URL:",
            opportunity["url"]
        )

        if opportunity.get(
            "published"
        ):
            print(
                "Published:",
                opportunity[
                    "published"
                ]
            )

        print()

    print(
        "========================================"
    )

    if opportunities:
        print(
            "UKRI discovery connection: SUCCESS"
        )
    else:
        print(
            "UKRI discovery connection: "
            "NO OPPORTUNITIES FOUND"
        )

    print(
        "========================================"
    )
    print()


if __name__ == "__main__":
    main()