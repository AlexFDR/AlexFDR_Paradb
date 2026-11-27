#!/usr/bin/env python3
"""Fetch public ParaDB charts and publish uploader U9EAF8A's YouTube previews.

ParaCommsDB is used only as a fallback for charts that ParaDB does not provide.
Both sources are deduplicated by normalized artist/title and by YouTube video ID.
"""
import gzip
import html
import json
import math
import os
import re
import time
import unicodedata
from datetime import datetime
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
KITS_OUT = DATA_DIR / "kits.json"
THUNDERSTORE_API = "https://thunderstore.io/c/paradiddle/api/v1/package/"
PRICES = DATA_DIR / "pricing.json"
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

COMMS_BASE = "https://paracommsdb.fencil.xyz"
COMMS_USER = "AlexFDR"
COMMS_CACHE = Path(os.environ.get("PARACOMMS_CACHE_DIR") or (DATA_DIR / ".cache" / "paracommsdb"))
CACHE_TTL = 7 * 24 * 60 * 60

COMMS_CHART_LINK_RE = re.compile(r'<a href="(/chart/(\d+)/)"><b>(.*?)</b></a>', re.I | re.S)
COMMS_VIDEO_RE = re.compile(r'data-video="([\w-]+)"')
COMMS_ALBUM_RE = re.compile(r"Album:\s*([^<\r\n]+)", re.I)
COMMS_DATE_RE = re.compile(r"·\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})")
COMMS_DIFF_RE = re.compile(r'class="diff\s+([^"]+)"', re.I)
COMMS_KIND_RE = re.compile(r"ctag ctag-([a-z]+)", re.I)
COMMS_OG_IMAGE_RE = re.compile(r'<meta property="og:image" content="([^"]+)"', re.I)
COMMS_KIT_LINK_RE = re.compile(r'<a class="poster-link" href="(/kit/(\d+)/)">', re.I)
COMMS_KIT_NAME_RE = re.compile(r'<b class="t" title="([^"]+)">', re.I)
COMMS_KIT_HEADING_RE = re.compile(r'<h2 class="flush">\s*(?:🥁\s*)?(.*?)</h2>', re.I | re.S)
COMMS_KIT_IMAGE_RE = re.compile(r'src="(/kit/\d+/(?:image|pic/\d+)/[^"]*)"', re.I)
COMMS_CARD_RE = re.compile(r'<div class="card">(.*?)</div>', re.I | re.S)


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


def strip_html(value):
    text = re.sub(r"<br\s*/?>", " ", value or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_date(value):
    value = (value or "").strip()
    try:
        return datetime.strptime(value, "%d %b %Y").date().isoformat()
    except ValueError:
        return value


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


def fetch_html(url):
    request = Request(
        url,
        headers={
            "User-Agent": "AlexFDRParaDBGallery/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=45) as response:
        markup = response.read().decode("utf-8", "replace")
    time.sleep(0.15)
    return markup


def cache_path(kind, key):
    return COMMS_CACHE / kind / f"{key}.json"


def cache_read(kind, key):
    path = cache_path(kind, key)
    if not path.exists():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(envelope.get("fetchedAt", 0)) > CACHE_TTL:
            return None
        return envelope.get("data")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def cache_write(kind, key, data):
    path = cache_path(kind, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {"fetchedAt": time.time(), "data": data}
    path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")


def split_comms_title(value):
    text = html.unescape(value or "").strip()
    if " - " in text:
        artist, title = text.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", text


def comms_chart_list():
    charts = []
    seen = set()
    for page in range(1, 31):
        markup = fetch_html(f"{COMMS_BASE}/u/{COMMS_USER}/?page={page}")
        found = 0
        for href, chart_id, raw_title in COMMS_CHART_LINK_RE.findall(markup):
            if chart_id in seen:
                continue
            seen.add(chart_id)
            found += 1
            artist, title = split_comms_title(raw_title)
            charts.append({
                "id": chart_id,
                "artist": artist,
                "title": title,
                "chartUrl": urljoin(COMMS_BASE, href),
            })
        if not found:
            break
    return charts


def comms_chart_detail(chart):
    chart_id = chart["id"]
    cached = cache_read("charts", chart_id)
    if cached is not None:
        return cached

    markup = fetch_html(chart["chartUrl"])
    video_id = None
    match = COMMS_VIDEO_RE.search(markup)
    if match:
        video_id = match.group(1)

    video_url = None
    if not video_id:
        parser = Links()
        parser.feed(markup)
        candidates = parser.urls + URL_RE.findall(markup)
        for candidate in candidates:
            candidate = html.unescape(candidate).rstrip(".,);]")
            found = youtube_id(candidate)
            if found:
                video_id = found
                video_url = candidate
                break

    if video_url is None and video_id:
        video_url = f"https://www.youtube.com/watch?v={video_id}"

    album_match = COMMS_ALBUM_RE.search(markup)
    date_match = COMMS_DATE_RE.search(markup)
    image_match = COMMS_OG_IMAGE_RE.search(markup)
    kind_match = COMMS_KIND_RE.search(markup)
    kind = {"commission": "Commission", "personal": "Personal Project"}.get(
        (kind_match.group(1) if kind_match else "").casefold(), ""
    )
    data = {
        "videoId": video_id,
        "videoUrl": video_url,
        "album": html.unescape(album_match.group(1)).strip() if album_match else "",
        "submissionDate": parse_date(date_match.group(1)) if date_match else None,
        "coverUrl": html.unescape(image_match.group(1)) if image_match else None,
        "difficulties": sorted(set(item.strip() for item in COMMS_DIFF_RE.findall(markup) if item.strip())),
        "kind": kind,
    }
    cache_write("charts", chart_id, data)
    return data


def get_comms_charts(listings, charts_by_id, seen_songs, seen_videos, by_key, by_title):
    added = 0
    for chart in listings:
        try:
            detail = comms_chart_detail(chart)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            print(f"Warning: skipping ParaCommsDB chart {chart['id']}: {error}")
            continue

        video_id = detail.get("videoId")
        if not video_id:
            continue
        song_key = f"{normalize(chart['title'])}|{normalize(chart['artist'])}"
        if song_key in seen_songs or video_id in seen_videos:
            continue
        seen_songs.add(song_key)
        seen_videos.add(video_id)

        price_entry = find_price_entry(chart, by_key, by_title)
        charts_by_id[f"comms:{chart['id']}:{video_id}"] = {
            "id": chart["id"],
            "title": chart["title"],
            "artist": chart["artist"],
            "submissionDate": detail.get("submissionDate"),
            "video": {"id": video_id, "url": detail.get("videoUrl")},
            "coverUrl": detail.get("coverUrl"),
            "chartUrl": chart["chartUrl"],
            "_priceEntry": price_entry,
            "_album": detail.get("album", ""),
        }
        added += 1
    return added


def comms_kit_list():
    markup = fetch_html(f"{COMMS_BASE}/u/{COMMS_USER}/kits/")
    kits = []
    seen = set()
    for href, kit_id in COMMS_KIT_LINK_RE.findall(markup):
        if kit_id in seen:
            continue
        seen.add(kit_id)
        kits.append({"id": kit_id, "kitUrl": urljoin(COMMS_BASE, href)})
    return kits


def comms_kit_detail(kit):
    kit_id = kit["id"]
    cached = cache_read("kits", kit_id)
    if cached is not None:
        return cached

    markup = fetch_html(kit["kitUrl"])
    heading = COMMS_KIT_HEADING_RE.search(markup)
    pieces = re.search(r"(\d+)\s+pieces", markup, re.I)
    downloads = re.search(r"(\d+)\s+Downloads", markup, re.I)
    date_match = COMMS_DATE_RE.search(markup)
    description = ""
    for candidate in COMMS_CARD_RE.findall(markup):
        if "detail-head" in candidate or "Rating:" in candidate:
            continue
        description = strip_html(candidate)
        if description:
            break
    images = [
        urljoin(COMMS_BASE, html.unescape(src))
        for src in COMMS_KIT_IMAGE_RE.findall(markup)
    ]
    data = {
        "name": html.unescape(heading.group(1)).strip() if heading else f"Kit {kit_id}",
        "pieces": int(pieces.group(1)) if pieces else None,
        "downloads": int(downloads.group(1)) if downloads else 0,
        "uploadedAt": parse_date(date_match.group(1)) if date_match else None,
        "description": description,
        "images": list(dict.fromkeys(images)),
        "downloadUrl": f"{COMMS_BASE}/kit/{kit_id}/download/",
    }
    cache_write("kits", kit_id, data)
    return data


def get_comms_kits():
    try:
        listings = comms_kit_list()
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        print(f"Warning: ParaCommsDB kit list unavailable: {error}")
        return []

    kits = []
    seen_ids = set()
    seen_names = set()
    for listing in listings:
        try:
            detail = comms_kit_detail(listing)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            print(f"Warning: skipping ParaCommsDB kit {listing['id']}: {error}")
            continue
        name_key = normalize(detail.get("name"))
        if listing["id"] in seen_ids or (name_key and name_key in seen_names):
            continue
        seen_ids.add(listing["id"])
        seen_names.add(name_key)
        kits.append({
            "id": listing["id"],
            "name": detail.get("name", ""),
            "owner": COMMS_USER,
            "pieces": detail.get("pieces"),
            "downloads": detail.get("downloads", 0),
            "uploadedAt": detail.get("uploadedAt"),
            "description": detail.get("description", ""),
            "images": detail.get("images", []),
            "kitUrl": listing["kitUrl"],
            "downloadUrl": detail.get("downloadUrl", ""),
        })
    kits.sort(key=lambda item: item.get("uploadedAt") or "", reverse=True)
    return kits


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
    seen_songs = set()
    seen_videos = set()
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
            chart_url = f"https://paradb.net/map/{quote(str(chart.get('id', '')), safe='')}"
            song_key = f"{normalize(chart.get('title'))}|{normalize(chart.get('artist'))}"
            # A chart description can contain several videos for the same song.
            # Keep the first one so the gallery never shows the same song twice.
            for video in videos:
                if song_key in seen_songs:
                    break
                if video["id"] in seen_videos:
                    continue
                seen_songs.add(song_key)
                seen_videos.add(video["id"])
                charts_by_id[f"{chart.get('id')}:{video['id']}"] = {
                    "id": chart.get("id"),
                    "title": chart.get("title", ""),
                    "artist": chart.get("artist", ""),
                    "submissionDate": chart.get("submissionDate"),
                    "video": video,
                    "coverUrl": cover_url(chart),
                    "chartUrl": chart_url,
                    "_priceEntry": price_entry,
                }
        offset += len(maps)
        if not maps:
            break
        time.sleep(0.15)

    try:
        comms_listings = comms_chart_list()
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        print(f"Warning: ParaCommsDB chart list unavailable: {error}")
        comms_listings = []

    # Every card uses a ParaCommsDB chart page when the same song exists there.
    # Songs without a ParaCommsDB match keep their ParaDB chart URL.
    comms_chart_urls = {}
    for chart in comms_listings:
        song_key = f"{normalize(chart['title'])}|{normalize(chart['artist'])}"
        comms_chart_urls.setdefault(song_key, chart["chartUrl"])
    for chart in charts_by_id.values():
        song_key = f"{normalize(chart.get('title'))}|{normalize(chart.get('artist'))}"
        if song_key in comms_chart_urls:
            chart["chartUrl"] = comms_chart_urls[song_key]

    # ParaDB is the primary source. Its normalized song keys and video IDs are
    # reserved first so ParaCommsDB can only fill gaps.
    seen_songs = {
        f"{normalize(chart.get('title'))}|{normalize(chart.get('artist'))}"
        for chart in charts_by_id.values()
    }
    seen_videos = {chart["video"]["id"] for chart in charts_by_id.values()}
    comms_added = get_comms_charts(comms_listings, charts_by_id, seen_songs, seen_videos, by_key, by_title)

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
        chart.pop("_album", None)
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
    kits = get_comms_kits()

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
    kits_result = {
        "source": f"{COMMS_BASE}/u/{COMMS_USER}/kits/",
        "owner": COMMS_USER,
        "updatedAt": result["updatedAt"],
        "kits": kits,
    }
    KITS_OUT.write_text(json.dumps(kits_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(result['charts'])} videos ({comms_added} from ParaCommsDB), "
        f"{len(mods)} Thunderstore mods and {len(kits)} kits."
    )


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
        raise SystemExit(f"ParaDB data refresh failed: {error}")
