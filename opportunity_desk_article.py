from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# =========================================================
# CONFIGURATION
# =========================================================

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


# =========================================================
# HELPERS
# =========================================================

def clean_text(value):
    return " ".join(
        value.split()
    ).strip()


def validate_url(url):
    parsed = urlparse(url)

    return parsed.netloc in {
        "opportunitydesk.org",
        "www.opportunitydesk.org"
    }


# =========================================================
# EXTRACT ARTICLE
# =========================================================

def extract_article(url):

    if not validate_url(url):
        raise ValueError(
            "This test only accepts Opportunity Desk URLs."
        )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    # Remove page elements that are not part of the article.
    for unwanted in soup.select(
        "script, style, nav, footer, header, "
        "aside, form, noscript"
    ):
        unwanted.decompose()

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    title = ""

    title_element = soup.find("h1")

    if title_element:
        title = clean_text(
            title_element.get_text(
                " ",
                strip=True
            )
        )

    # -----------------------------------------------------
    # ARTICLE CONTENT
    # -----------------------------------------------------

    content = None

    selectors = [
        ".entry-content",
        ".post-content",
        ".td-post-content",
        ".single-post-content",
        "article",
        "main"
    ]

    for selector in selectors:

        candidate = soup.select_one(
            selector
        )

        if candidate:
            content = candidate
            break

    if content is None:
        raise RuntimeError(
            "Could not locate the article content."
        )

    text_parts = []

    for element in content.find_all(
        [
            "p",
            "li",
            "h2",
            "h3",
            "h4"
        ]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True
            )
        )

        if not text:
            continue

        if len(text) < 3:
            continue

        if (
            text_parts
            and text == text_parts[-1]
        ):
            continue

        text_parts.append(text)

    article_text = "\n".join(
        text_parts
    )

    if len(article_text) < 100:
        raise RuntimeError(
            "The extracted article text was too short."
        )

    return {
        "title": title,
        "url": url,
        "text": article_text
    }


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    print()
    print("====================================")
    print("      HelAI Article Reader")
    print("====================================")
    print()

    url = input(
        "Paste Opportunity Desk URL: "
    ).strip()

    print()
    print("Reading article...")
    print()

    try:

        article = extract_article(
            url
        )

        print(
            "Title:",
            article["title"]
        )

        print(
            "Characters extracted:",
            len(article["text"])
        )

        print()
        print(
            "------------- ARTICLE PREVIEW -------------"
        )

        print(
            article["text"][:3000]
        )

        print(
            "-------------------------------------------"
        )

        print()

    except Exception as error:

        print(
            "Article extraction failed:",
            error
        )

        print()