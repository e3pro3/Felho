# EgyKettő RSS scraper
# GitHub Actions kompatibilis

import os
import json
import hashlib
import requests

from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urljoin

from dateutil import parser as dateparser
from feedgen.feed import FeedGenerator


API_URL = "https://egyketto.ro/api/feed/getfeed"

CACHE_FILE = "articles.json"
OUTPUT_FILE = "feed.xml"

DAYS_LIMIT = 5


HEADERS = {
    "User-Agent": "Mozilla/5.0 (RSS Bot)"
}


# -------------------------
# Segédfüggvények
# -------------------------

def sha256(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def article_id(article):
    raw = (
        article.get("title", "")
        + article.get("link", "")
    )

    return sha256(raw)


# -------------------------
# API lekérés
# -------------------------

def fetch_articles():

    print("EgyKettő scraper indul...")

    response = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()


    # API ellenőrzés
    if isinstance(data, dict):

        for key in [
            "items",
            "articles",
            "data",
            "feed"
        ]:
            if key in data:
                data = data[key]
                break


    if not isinstance(data, list):
        return []


    print(f"API cikkek: {len(data)}")

    return data


# -------------------------
# Cache kezelés
# -------------------------

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


# -------------------------
# Cikk normalizálás
# -------------------------

def normalize(article):

    title = (
        article.get("title")
        or ""
    )

    link = (
        article.get("link")
        or ""
    )


    # Kép kezelése
    image = (
        article.get("imageLink")
        or ""
    )


    # Relatív kép URL javítása
    if image.startswith("/"):

        parsed = urlparse(link)

        image = urljoin(
            f"{parsed.scheme}://{parsed.netloc}",
            image
        )


    description = (
        article.get("description")
        or ""
    )


    published = (
        article.get("pubDate")
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

        "published": published
    }


# -------------------------
# Dátum kezelés
# -------------------------

def parse_date(value):

    try:

        return dateparser.parse(value)

    except Exception:

        return datetime.now(
            timezone.utc
        )


# -------------------------
# 5 napos szűrés
# -------------------------

def filter_recent(items):

    limit = (
        datetime.now(timezone.utc)
        -
        timedelta(days=DAYS_LIMIT)
    )

    result = []

    for item in items:

        dt = parse_date(
            item.get("published")
        )

        if dt >= limit:
            result.append(item)

    return result


# -------------------------
# Duplikáció + cache
# -------------------------

def merge_articles(new_items):

    old_items = load_cache()


    combined = {}


    for item in old_items:

        combined[item["id"]] = item


    for item in new_items:

        clean = normalize(item)

        combined[clean["id"]] = clean


    result = list(
        combined.values()
    )


    result = filter_recent(result)


    # legfrissebb elöl

    result.sort(
        key=lambda x: parse_date(
            x["published"]
        ),
        reverse=True
    )


    save_cache(result)


    return result


# -------------------------
# RSS generálás
# -------------------------

def create_rss(items):

    fg = FeedGenerator()


    fg.title(
        "EgyKettő hírek"
    )

    fg.link(
        href="https://egyketto.ro",
        rel="alternate"
    )

    fg.description(
        "Automatikus EgyKettő RSS feed"
    )


    fg.language(
        "hu"
    )


    for item in items:

        entry = fg.add_entry()


        entry.title(
            item["title"]
        )


        entry.link(
            href=item["link"]
        )


        # Kép az RSS tartalomba
        content = ""


        if item.get("image"):

            content += f"""
            <p>
            <img src="{item['image']}"
            style="max-width:100%;height:auto;">
            </p>
            """


        content += (
            "<p>"
            + item.get(
                "description",
                ""
            )
            + "</p>"
        )


        entry.content(
            content,
            type="CDATA"
        )


        entry.description(
            content
        )


        if item.get("image"):

            entry.enclosure(
                item["image"],
                0,
                "image/jpeg"
            )


        entry.pubdate(
            parse_date(
                item["published"]
            )
        )


    fg.rss_file(
        OUTPUT_FILE
    )


    print(
        f"RSS elkészült: {len(items)} cikk"
    )


# -------------------------
# Fő program
# -------------------------

def main():

    articles = fetch_articles()


    merged = merge_articles(
        articles
    )


    create_rss(
        merged
    )


    print(
        f"Kész: {len(merged)} cikk"
    )



if __name__ == "__main__":

    main()
