#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta, timezone
import hashlib
import logging

import requests
from feedgen.feed import FeedGenerator

API_URL = "https://egyketto.ro/api/feed/getfeed"
SITE_URL = "https://egyketto.ro"

RSS_FILE = "feed.xml"

KEEP_DAYS = 7

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)


def parse_date(value: str) -> datetime | None:
    if not value:
        return None

    value = value.replace("Z", "")

    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def image_url(path: str | None) -> str | None:

    if not path:
        return None

    if path.startswith("http"):
        return path

    if not path.endswith(".webp"):
        path += ".webp"

    return SITE_URL + path


def article_guid(article):

    return article["id"]


logging.info("Downloading articles...")

response = requests.get(API_URL, timeout=30)

response.raise_for_status()

articles = response.json()

logging.info("Downloaded %d articles", len(articles))

limit = datetime.now() - timedelta(days=KEEP_DAYS)

recent = []

for article in articles:

    published = parse_date(article.get("pubDate"))

    if published is None:
        continue

    if published < limit:
        continue

    article["_published"] = published

    recent.append(article)

recent.sort(
    key=lambda x: x["_published"],
    reverse=True,
)

logging.info(
    "%d recent articles",
    len(recent),
)

fg = FeedGenerator()

fg.id(SITE_URL)
fg.title("Erdélyi hírek")
fg.description("RSS")
fg.language("hu")

fg.link(
    href=SITE_URL,
    rel="alternate",
)

for article in recent:

    title = (article.get("title") or "").strip()
    description = (article.get("description") or "").strip()
    link = (article.get("link") or "").strip()
    category = (article.get("category") or "").strip()
    source = (article.get("siteName") or "").strip()

    image = image_url(article.get("imageLink"))

    entry = fg.add_entry()

    entry.id(article_guid(article))
    entry.guid(article_guid(article), permalink=False)

    entry.title(f"[{source}] {title}" if source else title)

    entry.link(
        href=link,
        rel="alternate",
    )

    entry.pubDate(
        article["_published"].replace(
            tzinfo=timezone.utc
        )
    )

    if category:
        entry.category(term=category)

    if source:
        entry.author(name=source)

    html = []

    if image:
        html.append(
            f'<p><img src="{image}" alt="{title}" /></p>'
        )

    if description:
        html.append(
            f"<p>{description}</p>"
        )

    html.append("<hr>")

    if source:
        html.append(
            f"<p><strong>Forrás:</strong> {source}</p>"
        )

    if category:
        html.append(
            f"<p><strong>Kategória:</strong> {category}</p>"
        )

    html.append(
        f'<p><a href="{link}">Eredeti cikk</a></p>'
    )

    html = "\n".join(html)

    entry.description(html)

    entry.content(
        html,
        type="html",
    )

    entry.source(title=source, url=link)

    if image:

        try:

            entry.enclosure(
                image,
                "0",
                "image/webp",
            )

        except Exception as exc:

            logging.warning(
                "Unable to add image: %s",
                exc,
            )

logging.info("Generating RSS file...")

#
# Atom self link
#
fg.link(
    href=f"{SITE_URL}/feed.xml",
    rel="self",
)

#
# Last build date
#
fg.updated(
    datetime.now(timezone.utc)
)

#
# Generator
#
fg.generator(
    "Erdély RSS Generator"
)

#
# RSS kiírása
#
fg.rss_file(
    RSS_FILE,
    pretty=True,
)

logging.info("RSS written to %s", RSS_FILE)

logging.info(
    "Finished successfully (%d articles)",
    len(recent),
)
