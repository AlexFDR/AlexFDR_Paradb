#!/usr/bin/env python3
"""Fetch public ParaDB charts and publish YouTube previews from uploader U9EAF8A."""
import html
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://paradb.net/api/maps"
UPLOADER = "U9EAF8A"
LIMIT = 100
OUT = Path(__file__).resolve().parents[1] / "data" / "charts.json"
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


def get_page(offset):
    query = urlencode({"query": "", "limit": LIMIT, "offset": offset})
    request = Request(f"{API}?{query}", headers={"User-Agent": "AlexFDRParaDBGallery/1.0"})
    with urlopen(request, timeout=45) as response:
        return json.load(response)


def main():
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
            for video in videos:
                charts_by_id[f"{chart.get('id')}:{video['id']}"] = {
                    "id": chart.get("id"),
                    "title": chart.get("title", ""),
                    "artist": chart.get("artist", ""),
                    "author": chart.get("author"),
                    "submissionDate": chart.get("submissionDate"),
                    "video": video,
                }
        offset += len(maps)
        if not maps:
            break
        time.sleep(0.15)

    result = {
        "source": API,
        "uploader": UPLOADER,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "charts": sorted(charts_by_id.values(), key=lambda item: item.get("submissionDate") or "", reverse=True),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result['charts'])} videos from uploader {UPLOADER} (ParaDB reports {total} public charts).")


if __name__ == "__main__":
    try:
        main()
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
        raise SystemExit(f"ParaDB data refresh failed: {error}")
