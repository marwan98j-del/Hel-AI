import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape

import requests
from bs4 import BeautifulSoup

from helai_config import (
    HELAI_REQUEST_DELAY_SECONDS,
    HELAI_REQUEST_TIMEOUT_SECONDS,
)
from opportunity_desk_article import extract_article
from opportunity_desk_discovery import discover_opportunities
from opportunity_rules import normalize_url
from ukri_article import read_ukri_opportunity
from ukri_discovery import discover_ukri_opportunities


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0 Safari/537.36 HelAI/1.0"
    )
}


@dataclass(frozen=True)
class SourceAdapter:
    key: str
    source_name: str
    source: str
    active: bool = True

    def discover(self, limit):
        raise NotImplementedError

    def read(self, candidate):
        raise NotImplementedError


def clean_text(value):
    if value is None:
        return ""

    return " ".join(
        unescape(str(value)).split()
    ).strip()


def strip_html(value):
    soup = BeautifulSoup(
        value or "",
        "html.parser",
    )

    return clean_text(
        soup.get_text(" ", strip=True)
    )


def request_with_retries(
    method,
    url,
    *,
    retries=2,
    **kwargs,
):
    last_error = None
    headers = kwargs.pop("headers", HEADERS)
    timeout = kwargs.pop(
        "timeout",
        HELAI_REQUEST_TIMEOUT_SECONDS,
    )

    for attempt in range(retries + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
            response.raise_for_status()
            return response

        except Exception as error:
            last_error = error
            if attempt < retries:
                time.sleep(
                    HELAI_REQUEST_DELAY_SECONDS
                    * (attempt + 1)
                )

    raise last_error


def generic_page_text(url, summary=""):
    response = request_with_retries(
        "GET",
        url,
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    for unwanted in soup.select(
        "script, style, noscript, svg, nav, header, footer, form"
    ):
        unwanted.decompose()

    content = (
        soup.find("main")
        or soup.find("article")
        or soup.body
    )

    text = ""

    if content:
        text = clean_text(
            content.get_text(" ", strip=True)
        )

    if summary:
        text = summary + "\n\n" + text

    if len(text) < 120:
        raise ValueError(
            "Extracted source text was too short."
        )

    return text[:16000]


def parse_rss(feed_url, source, source_name, limit):
    response = request_with_retries(
        "GET",
        feed_url,
    )

    root = ET.fromstring(
        response.text
    )

    candidates = []

    for item in root.iter():
        tag = item.tag.split("}")[-1].lower()

        if tag not in {
            "item",
            "entry",
        }:
            continue

        title = ""
        link = ""
        summary = ""

        for child in item:
            child_tag = child.tag.split("}")[-1].lower()

            if child_tag == "title":
                title = clean_text(child.text)

            elif child_tag in {
                "description",
                "summary",
                "content",
            }:
                summary = strip_html(child.text or "")

            elif child_tag == "link":
                href = child.attrib.get("href")
                link = clean_text(href or child.text)

        if not title or not link:
            continue

        candidates.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "source_name": source_name,
                "summary": summary,
            }
        )

        if len(candidates) >= limit:
            break

    return candidates


class OpportunityDeskSource(SourceAdapter):
    def __init__(self):
        super().__init__(
            key="opportunity_desk",
            source="Opportunity Desk",
            source_name="Opportunity Desk",
        )

    def discover(self, limit):
        items = discover_opportunities(limit=limit)
        for item in items:
            item["source"] = self.source
            item["source_name"] = self.source_name
        return items

    def read(self, candidate):
        article = extract_article(candidate["url"])
        return article["title"] + "\n\n" + article["text"]


class UKRISource(SourceAdapter):
    def __init__(self):
        super().__init__(
            key="ukri",
            source="UKRI",
            source_name="UK Research and Innovation (UKRI)",
        )

    def discover(self, limit):
        items = discover_ukri_opportunities(limit=limit)
        for item in items:
            item["source"] = self.source
            item["source_name"] = self.source_name
        return items

    def read(self, candidate):
        return read_ukri_opportunity(candidate["url"])


class GrantsGovSource(SourceAdapter):
    API_URL = "https://api.grants.gov/v1/api/search2"
    DETAIL_BASE = "https://www.grants.gov/search-results-detail/"

    def __init__(self):
        super().__init__(
            key="grants_gov",
            source="Grants.gov",
            source_name="Grants.gov",
        )

    def discover(self, limit):
        response = request_with_retries(
            "POST",
            self.API_URL,
            json={
                "rows": limit,
                "oppStatuses": "posted|forecasted",
                "sortBy": "openDate|desc",
            },
        )

        payload = response.json()
        hits = (
            payload.get("data", {})
            .get("oppHits", [])
        )

        candidates = []

        for hit in hits:
            title = clean_text(hit.get("title"))
            opportunity_id = clean_text(hit.get("id"))

            if not title or not opportunity_id:
                continue

            url = self.DETAIL_BASE + opportunity_id

            summary = "\n".join(
                part
                for part in [
                    f"Title: {title}",
                    f"Agency: {clean_text(hit.get('agencyName'))}",
                    f"Opportunity number: {clean_text(hit.get('number'))}",
                    f"Status: {clean_text(hit.get('oppStatus'))}",
                    f"Open date: {clean_text(hit.get('openDate'))}",
                    f"Close date: {clean_text(hit.get('closeDate'))}",
                ]
                if part.split(": ", 1)[-1]
            )

            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "source": self.source,
                    "source_name": self.source_name,
                    "external_id": opportunity_id,
                    "summary": summary,
                }
            )

        return candidates

    def read(self, candidate):
        return generic_page_text(
            candidate["url"],
            candidate.get("summary", ""),
        )


class NSFSource(SourceAdapter):
    FEED_URL = "https://www.nsf.gov/rss/rss_www_funding_pgm_annc_inf.xml"

    def __init__(self):
        super().__init__(
            key="nsf",
            source="NSF",
            source_name="U.S. National Science Foundation (NSF)",
        )

    def discover(self, limit):
        return parse_rss(
            self.FEED_URL,
            self.source,
            self.source_name,
            limit,
        )

    def read(self, candidate):
        return generic_page_text(
            candidate["url"],
            candidate.get("summary", ""),
        )


def get_source_adapters():
    return [
        OpportunityDeskSource(),
        UKRISource(),
        GrantsGovSource(),
        NSFSource(),
    ]


def get_source_catalog():
    return [
        {
            "key": source.key,
            "source": source.source,
            "source_name": source.source_name,
            "active": source.active,
        }
        for source in get_source_adapters()
    ]


def normalize_candidate_url(candidate):
    return normalize_url(
        candidate.get("url")
    )
