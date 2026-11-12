#!/usr/bin/env python3
"""Outlier miner (upgrade 5). UNTESTED until a YouTube Data API key exists.

Finds recent GTA 6 videos/Shorts that beat their channel's norm, for hook and topic ideas.
Needs env YT_API_KEY (free key, YouTube Data API v3). Quota: videos.list/channels.list = 1 unit,
search.list is the expensive one, so this runs ONE search per query (verify cost in the Quotas page).

Usage: YT_API_KEY=... python scripts/yt_outliers.py "GTA 6" --days 7 --top 15 > qc/outliers.json
"""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

KEY = os.environ.get("YT_API_KEY")
API = "https://www.googleapis.com/youtube/v3/"


def get(ep, **p):
    p["key"] = KEY
    with urllib.request.urlopen(API + ep + "?" + urllib.parse.urlencode(p), timeout=30) as r:
        return json.load(r)


def main():
    if not KEY:
        sys.exit("YT_API_KEY not set")
    a = sys.argv[1:]
    q = a[0]
    days = int(a[a.index("--days") + 1]) if "--days" in a else 7
    top = int(a[a.index("--top") + 1]) if "--top" in a else 15
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    s = get("search", part="snippet", q=q, type="video", order="viewCount", maxResults=50,
            publishedAfter=since, videoDuration="short")
    ids = [i["id"]["videoId"] for i in s.get("items", [])]
    vids = get("videos", part="snippet,statistics", id=",".join(ids)).get("items", [])
    chans = {v["snippet"]["channelId"] for v in vids}
    cs = {c["id"]: c for c in get("channels", part="statistics", id=",".join(chans)).get("items", [])}
    out = []
    for v in vids:
        subs = int(cs[v["snippet"]["channelId"]]["statistics"].get("subscriberCount", 0) or 0)
        views = int(v["statistics"].get("viewCount", 0))
        out.append({"title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"], "views": views,
                    "subs": subs, "ratio": round(views / max(subs, 1), 1), "id": v["id"]})
    out.sort(key=lambda x: x["ratio"], reverse=True)
    print(json.dumps(out[:top], indent=1))


if __name__ == "__main__":
    main()
