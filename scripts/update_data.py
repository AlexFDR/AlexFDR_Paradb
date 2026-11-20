#!/usr/bin/env python3
"""Fetch public ParaDB charts and publish uploader U9EAF8A's YouTube previews."""
import gzip
import html
import json
import math
import re
import time
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen

API = "https://paradb.net/api/maps"
UPLOADER = "U9EAF8A"
LIMIT = 100
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUT = DATA_DIR / "charts.json"
MODS_OUT = DATA_DIR / "mods.json"
THUNDERSTORE_API = "https://thunderstore.io/c/paradiddle/api/v1/package/"
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
    seconds = entry.get("expertMappingTimeSeconds")
    if seconds is None:
        return None
    raw_minutes = max(0.0, float(seconds)) / 60.0
    rounded_minutes = math.floor(raw_minutes / 10.0 + 0.5) * 10
    expert_cost = max(2, int(rounded_minutes / 10))
    other_difficulties = sorted(entry.get("otherDifficulties", []))
    other_cost = len(other_difficulties) * 2
    if album_song_count >= 6:
        base = 10
        base_reason = "album rate: 6+ matched songs"
    elif raw_minutes < 45:
        base = 15
        base_reason = "Expert time under 45 minutes"
    else:
        base = 20
        base_reason = "standard base"
    return {
        "base": base,
        "baseReason": base_reason,
        "serviceFee": 2,
        "albumSongCount": album_song_count,
        "albumDiscountApplied": album_song_count >= 6,
        "expertMinutesRaw": round(raw_minutes, 1),
        "expertMinutesRounded": rounded_minutes,
        "expertCost": expert_cost,
        "otherDifficultyCount": len(other_difficulties),
        "otherDifficultyCost": other_cost,
        "total": base + 2 + expert_cost + other_cost,
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


def get_thunderstore_mods():
    packages = []
    next_url = THUNDERSTORE_API
    while next_url:
        request = Request(
            next_url,
            headers={
                "User-Agent": "AlexFDRParaDBGallery/1.0",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )
        with urlopen(request, timeout=45) as response:
            body = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                body = gzip.decompress(body)
            payload = json.loads(body.decode("utf-8"))
        if isinstance(payload, list):
            packages.extend(payload)
            next_url = None
        elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
            packages.extend(payload["results"])
            following = payload.get("next")
            next_url = urljoin(next_url, following) if following else None
        else:
            raise RuntimeError("Thunderstore returned an unexpected package list format")

    mods = []
    for package in packages:
        owner = str(package.get("owner") or "")
        if owner.casefold() != "alexfdr":
            continue
        versions = package.get("versions") or []
        active_versions = [version for version in versions if version.get("is_active", True)]
        version = active_versions[0] if active_versions else {}
        icon = version.get("icon")
        if isinstance(icon, str) and icon.startswith("/"):
            icon = "https://thunderstore.io" + icon
        package_name = package.get("name") or ""
        mods.append({
            "owner": owner,
            "name": package_name,
            "fullName": package.get("full_name") or f"{owner}-{package_name}",
            "packageUrl": package.get("package_url") or f"https://thunderstore.io/c/paradiddle/p/{quote(owner)}/{quote(package_name)}/",
            "iconUrl": icon if isinstance(icon, str) and icon.startswith("https://") else None,
            "description": version.get("description") or "",
            "version": version.get("version_number") or "",
            "updatedAt": package.get("date_updated") or version.get("date_created"),
            "downloads": int(version.get("downloads") or 0),
            "categories": sorted(package.get("categories") or []),
            "downloadUrl": version.get("download_url") or "",
        })
    mods.sort(key=lambda item: (item.get("name") or "").casefold())
    return mods


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
            estimate = estimate_price(entry, album_count)
            if estimate:
                chart["estimate"] = estimate
            else:
                chart["estimateUnavailableReason"] = "No Expert difficulty mapping time was found."
        result_charts.append(chart)

    mods = get_thunderstore_mods()

    result = {
        "source": API,
        "uploader": UPLOADER,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "charts": sorted(result_charts, key=lambda item: item.get("submissionDate") or "", reverse=True),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mods_result = {
        "source": THUNDERSTORE_API,
        "owner": "AlexFDR",
        "updatedAt": result["updatedAt"],
        "mods": mods,
    }
    MODS_OUT.write_text(json.dumps(mods_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result['charts'])} videos and {len(mods)} Thunderstore mods.")


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
        raise SystemExit(f"ParaDB data refresh failed: {error}")
