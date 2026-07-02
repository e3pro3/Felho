# EgyKettő RSS scraper
# GitHub Actions kompatibilis
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

import requests
from feedgen.feed import FeedGenerator

API_URL = "https://egyketto.ro/api/feed/getfeed"
OUTPUT_FILE = "feed.xml"

FEED_TITLE = "EgyKettő"
FEED_DESCRIPTION = "Erdély magyar hírportáljai egy helyen"
FEED_LINK = "https://egyketto.ro/"

KEEP_DAYS = 5
API_TIMEOUT = 30
API_RETRIES = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

session = requests.Session()

session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; EgyKettoRSS/1.0; "
            "+https://github.com/)"
        ),
        "Accept": "application/json",
    }
)


def parse_date(value: Optional[str]) -> Optional[datetime]:
    """
    API dátum -> datetime
    """

    if not value:
        return None

    value = value.replace("Z", "")

    try:
        return datetime.fromisoformat(value)
    except Exception:
        pass

    formats = (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue

    return None


def image_url(path: Optional[str]) -> Optional[str]:
    """
    API imageLink -> teljes URL
    """

    if not path:
        return None

    if path.startswith("http"):
        return path

    if not path.endswith(".webp"):
        path += ".webp"

    return "https://egyketto.ro" + path


def guid(article: dict) -> str:
    """
    Stabil GUID az RSS számára
    """

    text = (
        article.get("id")
        or article.get("link")
        or article.get("title")
        or ""
    )

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def sanitize_html(text: str) -> str:
    """
    Alapvető HTML sanitizáció - XSS védekezés
    """
    return escape(text) if text else ""


def download_articles(retries: int = API_RETRIES) -> list:
    """
    API lekérés exponenciális backoff-al
    """

    logging.info("Downloading feed...")

    for attempt in range(retries):
        try:
            r = session.get(
                API_URL,
                timeout=API_TIMEOUT,
            )

            r.raise_for_status()

            data = r.json()

            logging.info(
                "Downloaded %d articles",
                len(data),
            )

            return data

        except requests.RequestException as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                logging.warning(
                    "API error (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1,
                    retries,
                    wait,
                    e,
                )
                import time
                time.sleep(wait)
            else:
                logging.error(
                    "API failed after %d attempts",
                    retries,
                )
                raise


def recent_articles(articles: list) -> list:
    """
    Szűrés - csak az elmúlt KEEP_DAYS napos cikkek
    """

    limit = datetime.now() - timedelta(days=KEEP_DAYS)

    result = []

    for article in articles:

        published = parse_date(
            article.get("pubDate")
        )

        if published is None:
            continue

        if published < limit:
            continue

        article["_published"] = published

        result.append(article)

    result.sort(
        key=lambda x: x["_published"],
        reverse=True,
    )

    logging.info(
        "%d recent articles",
        len(result),
    )

    return result


def create_feed(articles: list) -> FeedGenerator:
    """
    RSS feed generálás
    """

    fg = FeedGenerator()

    fg.id(FEED_LINK)
    fg.title(FEED_TITLE)
    fg.description(FEED_DESCRIPTION)
    fg.language("hu")
    fg.link(
        href=FEED_LINK,
        rel="alternate",
    )

    fg.link(
        href=FEED_LINK,
        rel="self",
    )

    for article in articles:

        entry = fg.add_entry()

        title = (article.get("title") or "").strip()

        description = (
            article.get("description") or ""
        ).strip()

        link = (
            article.get("link") or ""
        ).strip()

        category = (
            article.get("category") or ""
        ).strip()

        source = (
            article.get("siteName") or ""
        ).strip()

        published = article["_published"]

        image = image_url(
            article.get("imageLink")
        )

        entry.guid(
            guid(article),
            permalink=False,
        )

        entry.id(
            guid(article)
        )

        entry.title(sanitize_html(title))

        entry.link(
            href=link,
            rel="alternate",
        )

        entry.pubDate(
            published.replace(
                tzinfo=timezone.utc
            )
        )

        if category:
            entry.category(
                term=sanitize_html(category)
            )

        html = ""

        if image:

            html += (
                '<p>'
                f'<img src="{escape(image)}" '
                f'alt="{escape(title)}" '
                'style="max-width:100%;" />'
                '</p>'
            )

        if description:

            html += (
                f"<p>{sanitize_html(description)}</p>"
            )

        html += "<hr>"

        if source:

            html += (
                f"<p><b>Forrás:</b> "
                f"{sanitize_html(source)}</p>"
            )

        if category:

            html += (
                f"<p><b>Kategória:</b> "
                f"{sanitize_html(category)}</p>"
            )

        html += (
            f'<p><a href="{escape(link)}">'
            "Eredeti cikk →"
            "</a></p>"
        )

        entry.description(html)

        entry.content(
            html,
            type="CDATA",
        )

        if image:

            try:

                entry.enclosure(
                    image,
                    "0",
                    "image/webp",
                )

            except Exception:

                logging.exception(
                    "Unable to add enclosure"
                )


    return fg


def main():
    """
    Fő program
    """

    try:

        articles = download_articles()

        articles = recent_articles(
            articles
        )

        fg = create_feed(
            articles
        )

        logging.info(
            "Writing RSS..."
        )

        fg.rss_file(
            OUTPUT_FILE,
            pretty=True,
        )

        logging.info(
            "Done."
        )

        logging.info(
            "Generated %d articles",
            len(articles),
        )

    except Exception:

        logging.exception(
            "Fatal error"
        )

        raise


if __name__ == "__main__":
    main()
