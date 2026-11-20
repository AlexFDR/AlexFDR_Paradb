#!/usr/bin/env python3
"""Fetch public ParaDB charts and publish uploader U9EAF8A's YouTube previews."""
import html
import json
import re
import time
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://paradb.net/api/maps"
UPLOADER = "U9EAF8A"
LIMIT = 100
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUT = DATA_DIR / "charts.json"
PRICES = DATA_DIR / "pricing.json"
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.urls.append(html.unescape(href))


def youtube_id(value):
    match = re.match(r"^https?://(?:www\.)?youtu\.be/([\w-]+)", value, re.I)
    if match:
        return match.group(1)
    match = re.match(r"^https?://(?:(?:www|m)\.)?youtube(?:-nocookie)?\.com/(?:watch\?.*?v=|embed/|shorts/|live/)([\w-]+)", value, re.I)
    return match.group(1) if match else None


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def load_price_catalog():
    catalog = json.loads(PRICES.read_text(encoding="utf-8"))
    by_key = {}
    by_title = {}
    for song in catalog.get("songs", []):
        key = f"{normalize(song.get('title'))}|{normalize(song.get('artist'))}"
        by_key[key] = song
        by_title.setdefault(normalize(song.get("title")), []).append(song)
    return by_key, by_title


def find_price_entry(chart, by_key, by_title):
    title_key = normalize(chart.get("title"))
    artist_key = normalize(chart.get("artist"))
    entry = by_key.get(f"{title_key}|{artist_key}")
    if entry:
        return entry
    # A few local files omit the artist. Only use the title fallback when it is unique.
    matches = by_title.get(title_key, [])
    return matches[0] if len(matches) == 1 else None


def estimate_price(entry, album_song_count):
    base = 10 if album_song_count >= 6 else 20
    difficulties = []
    for name, info in sorted(entry.get("difficulties", {}).items()):
        seconds = max(0.0, float(info.get("mappingTimeSeconds", 0)))
        raw_cost = seconds / 600.0
        cost = round(max(2.0, raw_cost), 2)
        difficulties.append({
            "name": name,
            "mappingTimeSeconds": round(seconds, 2),
            "cost": cost,
            "minimumApplied": raw_cost < 2.0,
        })
    total = round(base + 2.0 + sum(item["cost"] for item in difficulties), 2)
    return {
        "base": base,
        "serviceFee": 2,
        "albumSongCount": album_song_count,
        "albumDiscountApplied": album_song_count >= 6,
        "difficulties": difficulties,
        "total": total,
    }


def cover_url(chart):
    art = chart.get("albumArt")
    if not art:
        return None
    value = str(art)
    if value.startswith("https://"):
        return value
    filename = value.rsplit("/", 1)[-1]
    return f"https://paradb.net/covers/{quote(str(chart.get('id', '')), safe='')}/{quote(filename, safe='')}"


def get_page(offset):
    query = urlencode({"query": "", "limit": LIMIT, "offset": offset})
    request = Request(f"{API}?{query}", headers={"User-Agent": "AlexFDRParaDBGallery/1.0"})
    with urlopen(request, timeout=45) as response:
        return json.load(response)


def main():
    by_key, by_title = load_price_catalog()
    charts_by_id = {}
    offset = 0
    total = None
    while total is None or offset < total:
        payload = get_page(offset)
        if not payload.get("success"):
            raise RuntimeError(payload.get("errorMessage", "ParaDB API returned an unsuccessful response"))
        maps = payload.get("maps", [])
        total = int(payload.get("totalCount", 0))
        for chart in maps:
            if chart.get("uploader") != UPLOADER:
                continue
            description = chart.get("description") or ""
            parser = Links()
            parser.feed(description)
            candidates = parser.urls + URL_RE.findall(description)
            videos = []
            seen = set()
            for url in candidates:
                url = html.unescape(url).rstrip(".,);]")
                video_id = youtube_id(url)
                if video_id and video_id not in seen:
                    seen.add(video_id)
                    videos.append({"id": video_id, "url": url})
            price_entry = find_price_entry(chart, by_key, by_title)
            for video in videos:
                charts_by_id[f"{chart.get('id')}:{video['id']}"] = {
                    "id": chart.get("id"),
                    "title": chart.get("title", ""),
                    "artist": chart.get("artist", ""),
                    "submissionDate": chart.get("submissionDate"),
                    "video": video,
                    "coverUrl": cover_url(chart),
                    "_priceEntry": price_entry,
                }
        offset += len(maps)
        if not maps:
            break
        time.sleep(0.15)

    # Count unique matched songs per album, not preview videos, before applying the
    # $10-per-song base rate for albums represented by six or more gallery songs.
    matched_songs = {}
    for chart in charts_by_id.values():
        entry = chart.get("_priceEntry")
        if entry:
            matched_songs[chart["id"]] = entry
    album_songs = {}
    for entry in matched_songs.values():
        album_key = normalize(entry.get("album"))
        if album_key:
            album_songs.setdefault(album_key, set()).add(
                f"{normalize(entry.get('title'))}|{normalize(entry.get('artist'))}"
            )

    result_charts = []
    for chart in charts_by_id.values():
        entry = chart.pop("_priceEntry", None)
        if entry:
            album_key = normalize(entry.get("album"))
            album_count = len(album_songs.get(album_key, set())) if album_key else 0
            chart["estimate"] = estimate_price(entry, album_count)
        result_charts.append(chart)

    result = {
        "source": API,
        "uploader": UPLOADER,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "charts": sorted(result_charts, key=lambda item: item.get("submissionDate") or "", reverse=True),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result['charts'])} videos from uploader {UPLOADER} (ParaDB reports {total} public charts).")


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
        raise SystemExit(f"ParaDB data refresh failed: {error}")
