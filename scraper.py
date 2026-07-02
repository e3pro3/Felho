# EgyKettő RSS scraper
# GitHub Actions kompatibilis
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import logging
from datetime import datetime, timedelta, timezone

import requests
from feedgen.feed import FeedGenerator

API_URL = "https://egyketto.ro/api/feed/getfeed"
OUTPUT_FILE = "feed.xml"

FEED_TITLE = "EgyKettő"
FEED_DESCRIPTION = "Erdély magyar hírportáljai egy helyen"
FEED_LINK = "https://egyketto.ro/"

KEEP_DAYS = 5

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


def parse_date(value):
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


def image_url(path):
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


def guid(article):
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


def download_articles():

    logging.info("Downloading feed...")

    r = session.get(
        API_URL,
        timeout=30,
    )

    r.raise_for_status()

    data = r.json()

    logging.info(
        "Downloaded %d articles",
        len(data),
    )

    return data


def recent_articles(articles):

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

def create_feed(articles):

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

        entry.title(title)

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
                term=category
            )

        html = ""

        if image:

            html += (
                '<p>'
                f'<img src="{image}" '
                f'alt="{title}" '
                'style="max-width:100%;" />'
                '</p>'
            )

        if description:

            html += (
                f"<p>{description}</p>"
            )

        html += "<hr>"

        if source:

            html += (
                f"<p><b>Forrás:</b> "
                f"{source}</p>"
            )

        if category:

            html += (
                f"<p><b>Kategória:</b> "
                f"{category}</p>"
            )

        html += (
            f'<p><a href="{link}">'
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

            #
            # Egyes feedgen verziókban
            # működik a media extension,
            # másokban nem.
            #

    return fg

def main():

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
