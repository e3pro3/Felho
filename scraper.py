#!/usr/bin/env python3

import json
import os
import hashlib
from datetime import datetime, timedelta, timezone

import requests
from dateutil import parser as dateparser
from feedgen.feed import FeedGenerator


API_URL = "https://egyketto.ro/api/feed/getfeed"

CACHE_FILE = "articles.json"
RSS_FILE = "feed.xml"

DAYS_LIMIT = 5

RSS_TITLE = "EgyKettő"
RSS_LINK = "https://egyketto.ro"
RSS_DESCRIPTION = "EgyKettő friss hírek"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; EgyKettoRSSBot/1.0)"
    )
}


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return []

    try:
        with open(
            CACHE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
        return []


def save_cache(items):
    with open(
        CACHE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            items,
            f,
            ensure_ascii=False,
            indent=2
        )


def article_id(article):
    """
    Stabil azonosító cím + link alapján
    """
    raw = (
        article.get("title", "")
        + article.get("link", "")
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def fetch_articles():
    response = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

print(data[0].keys() if isinstance(data, list) else data.keys())

    if isinstance(data, dict):

        for key in [
            "items",
            "articles",
            "data",
            "feed"
        ]:
            if key in data:
                return data[key]

    if isinstance(data, list):
        return data

    return []


def normalize(article):

    title = (
        article.get("title")
        or article.get("name")
        or ""
    )

    link = (
        article.get("url")
        or article.get("link")
        or ""
    )

    image = (
        article.get("image")
        or article.get("image_url")
        or article.get("thumbnail")
        or article.get("cover")
        or article.get("cover_image")
        or article.get("photo")
        or article.get("picture")
        or article.get("featured_image")
        or ""
    )

    description = (
        article.get("description")
        or article.get("summary")
        or ""
    )


    published = (
        article.get("published")
        or article.get("date")
        or article.get("created_at")
        or datetime.now(timezone.utc).isoformat()
    )


    return {
        "id": article_id(
            {
                "title": title,
                "link": link
            }
        ),
        "title": title,
        "link": link,
        "image": image,
        "description": description,
        "published": published,
    }


def parse_date(value):

    try:
        return dateparser.parse(value)

    except Exception:
        return datetime.now(timezone.utc)


def filter_recent(items):

    cutoff = datetime.now(
        timezone.utc
    ) - timedelta(
        days=DAYS_LIMIT
    )

    result = []

    for item in items:

        dt = parse_date(
            item["published"]
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        if dt >= cutoff:
            result.append(item)

    return result


def merge_articles(old, new):

    merged = {}

    for item in old + new:
        merged[item["id"]] = item

    return filter_recent(
        list(merged.values())
    )


def generate_rss(items):

    fg = FeedGenerator()

    fg.id(RSS_LINK)
    fg.title(RSS_TITLE)
    fg.link(
        href=RSS_LINK,
        rel="alternate"
    )
    fg.description(
        RSS_DESCRIPTION
    )

    fg.language("hu")


    items = sorted(
        items,
        key=lambda x: parse_date(
            x["published"]
        ),
        reverse=True
    )


    for item in items:

        fe = fg.add_entry()

        fe.id(
            item["id"]
        )

        fe.title(
            item["title"]
        )

        fe.link(
            href=item["link"]
        )

        fe.description(
            item["description"]
        )


        fe.pubDate(
            parse_date(
                item["published"]
            )
        )


        if item.get("image"):

            fe.enclosure(
                item["image"],
                0,
                "image/jpeg"
            )

            fe.content(
                f"""
                <img src="{item['image']}" />
                <p>{item['description']}</p>
                """,
                type="CDATA"
            )


    fg.rss_file(
        RSS_FILE,
        pretty=True
    )


def main():

    print(
        "EgyKettő scraper indul..."
    )

    old = load_cache()

    fresh = fetch_articles()

    normalized = [
        normalize(x)
        for x in fresh
    ]


    merged = merge_articles(
        old,
        normalized
    )


    save_cache(
        merged
    )

    generate_rss(
        merged
    )


    print(
        f"Kész: {len(merged)} cikk"
    )


if __name__ == "__main__":
    main()
