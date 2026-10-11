"""YouTube analytics for the dashboard: who watched, how long, from where, and what they said.

One pull = one snapshot (JSON) in the db, read by the Analytics tab. Sources:
  - YouTube Data API (OAuth, read-only): the channel's uploads, live view/like/comment counts.
  - YouTube Analytics API (same OAuth): engaged views, % watched, countries, ages, traffic sources. Lags 1-3 days.
  - Comment text via the read-only API key (public data only; studio publish apikey).
Run: `studio publish analytics` (the dashboard also refreshes it when it's older than 20 minutes).
"""
import json
import urllib.request
from datetime import datetime, timedelta, timezone

from studio.core import publisher as pub
from studio.core.db import connect, log_event

AN = "https://youtubeanalytics.googleapis.com/v2/reports"
TIER1 = {"US", "GB", "CA", "AU"}                       # what Content Rewards briefs mean by tier 1
COUNTRY = {"US": "US", "GB": "UK", "CA": "Canada", "AU": "Australia", "IN": "India", "PH": "Philippines",
           "ID": "Indonesia", "MY": "Malaysia", "TH": "Thailand", "VN": "Vietnam", "ZA": "South Africa", "PK": "Pakistan",
           "BR": "Brazil", "MX": "Mexico", "DE": "Germany", "FR": "France", "NZ": "New Zealand", "SG": "Singapore",
           "AE": "UAE", "SA": "Saudi Arabia", "NG": "Nigeria", "BD": "Bangladesh", "EG": "Egypt", "TR": "Türkiye"}
SOURCE = {"SHORTS": "Shorts feed", "YT_SEARCH": "YouTube search", "YT_CHANNEL": "Your channel page", "SUBSCRIBER": "Subscribers",
          "EXT_URL": "Outside links", "YT_OTHER_PAGE": "Other YouTube pages", "RELATED_VIDEO": "Suggested videos",
          "NO_LINK_OTHER": "Direct / unknown", "SOUND_PAGE": "Sound page", "PLAYLIST": "Playlists", "NOTIFICATION": "Notifications",
          "HASHTAGS": "Hashtag pages", "SHORTS_CONTENT_LINKS": "Shorts links", "YT_PLAYLIST_PAGE": "Playlist page"}

_SCHEMA = """CREATE TABLE IF NOT EXISTS yt_snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    taken_at   TEXT NOT NULL DEFAULT (datetime('now')),
    data       TEXT NOT NULL
)"""


def _rows(token, start, end, metrics, dims=None, filt=None, sort=None, maxr=None):
    q = f"?ids=channel==MINE&startDate={start}&endDate={end}&metrics={metrics}"
    q += f"&dimensions={dims}" if dims else ""
    q += f"&filters={filt}" if filt else ""
    q += f"&sort={sort}" if sort else ""
    q += f"&maxResults={maxr}" if maxr else ""
    try:
        r, _ = pub._http("GET", AN + q, token)
    except RuntimeError:
        return []                                       # a report YouTube won't give for this video yet
    cols = [h["name"] for h in r.get("columnHeaders", [])]
    return [dict(zip(cols, row)) for row in r.get("rows", [])]


def _comments(vid, key, n=30):
    if not key:
        return []
    try:
        j = json.loads(urllib.request.urlopen(f"{pub.API}/commentThreads?part=snippet&order=time&maxResults={n}"
                                              f"&videoId={vid}&key={key}", timeout=20).read())
    except Exception:
        return []                                       # comments off / video private / quota: show none, never the key
    out = []
    for i in j.get("items", []):
        s = i["snippet"]["topLevelComment"]["snippet"]
        out.append({"author": s.get("authorDisplayName"), "text": s.get("textOriginal", ""), "likes": s.get("likeCount", 0),
                    "at": s.get("publishedAt"), "replies": i["snippet"].get("totalReplyCount", 0)})
    return out


def _audience(token, start, end, filt=None):
    countries = _rows(token, start, end, "views", "country", filt, "-views", 25)
    ages = _rows(token, start, end, "viewerPercentage", "ageGroup,gender", filt)
    sources = _rows(token, start, end, "views", "insightTrafficSourceType", filt, "-views")
    total_c = sum(c["views"] for c in countries) or 0
    age = {}
    for a in ages:
        g = a["ageGroup"].replace("age", "")
        age[g] = round(age.get(g, 0) + a["viewerPercentage"], 1)
    male = round(sum(a["viewerPercentage"] for a in ages if a["gender"] == "male"), 1) if ages else None
    return {
        "countries": [{"code": c["country"], "name": COUNTRY.get(c["country"], c["country"]), "views": c["views"],
                       "pct": round(c["views"] / total_c * 100, 1) if total_c else 0} for c in countries[:8]],
        "tier1_pct": round(sum(c["views"] for c in countries if c["country"] in TIER1) / total_c * 100, 1) if total_c else None,
        "ages": [{"group": g, "pct": p} for g, p in sorted(age.items())],
        "teen_pct": age.get("13-17", 0) if age else None,
        "aged_pct": round(sum(p for g, p in age.items() if g not in ("13-17", "18-24")), 1) if age else None,
        "under25_pct": round(age.get("13-17", 0) + age.get("18-24", 0), 1) if age else None,
        "male_pct": male,
        "sources": [{"name": SOURCE.get(s["insightTrafficSourceType"], s["insightTrafficSourceType"].replace("_", " ").title()),
                     "views": s["views"]} for s in sources[:6]],
    }


def _flags(v):
    """Plain-words warnings, worst first. Only when there's enough data to mean something."""
    f, a = [], v.get("analytics") or {}
    views = v.get("views") or 0
    if views and (v.get("likes", 0) + v.get("comments", 0)) / views * 100 < 1:
        f.append(("red", "Under 1% engagement, the campaign minimum. Pin a question and reply to comments."))
    if a.get("views", 0) >= 100:
        if a.get("avg_pct") is not None and a["avg_pct"] < 60:
            f.append(("amber", f"Viewers watch {a['avg_pct']:.0f}% on average. Shorts that spread keep 70-90%: hook harder, cut sooner."))
        if a.get("engaged") is not None and a["views"] and a["engaged"] / a["views"] < 0.6:
            f.append(("amber", f"Only {a['engaged'] / a['views'] * 100:.0f}% of views are engaged views (most swiped quickly)."))
        if a.get("tier1_pct") is not None and a["tier1_pct"] < 30:
            f.append(("amber", f"Only {a['tier1_pct']:.0f}% of viewers are from the US, UK, Canada or Australia."))
        if a.get("under25_pct") is not None and a["under25_pct"] < 30:
            f.append(("amber", f"Shown mostly to adults: only {a['under25_pct']:.0f}% of viewers are under 25."))
    return [{"level": l, "text": t} for l, t in f]


def pull(acc_id: str = "yt-cookedorcracked") -> dict:
    token, key = pub._access(acc_id), pub._api_key()
    ch, _ = pub._http("GET", f"{pub.API}/channels?part=snippet,contentDetails,statistics&mine=true", token)
    c = ch["items"][0]
    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
    pl, _ = pub._http("GET", f"{pub.API}/playlistItems?part=contentDetails&maxResults=50&playlistId={uploads}", token)
    ids = [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
    vids = []
    if ids:
        vr, _ = pub._http("GET", f"{pub.API}/videos?part=snippet,statistics,status,contentDetails&id={','.join(ids)}", token)
        vids = vr.get("items", [])
    con = connect()
    con.execute(_SCHEMA)
    clip_of = {}
    for p in con.execute("SELECT id, clip_id, url, data FROM posts WHERE account_id=?", (acc_id,)):
        vid = (json.loads(p["data"] or "{}") or {}).get("video_id") or pub._video_id(p["url"] or "")
        if vid:
            clip_of[vid] = (p["clip_id"], p["id"])
    today = datetime.now(timezone.utc).date()
    end = today.isoformat()
    start_ch = (today - timedelta(days=27)).isoformat()
    days = _rows(token, start_ch, end, "views,engagedViews,likes,subscribersGained", "day", sort="day")
    data_through = days[-1]["day"] if days else None
    videos = []
    for v in vids:
        vid, s, st = v["id"], v.get("statistics", {}), v.get("status", {})
        published = v["snippet"].get("publishedAt")
        if st.get("privacyStatus") != "public":
            published = st.get("publishAt") or published
        item = {"id": vid, "title": v["snippet"]["title"], "url": f"https://youtube.com/shorts/{vid}",
                "thumb": (v["snippet"].get("thumbnails", {}).get("medium") or {}).get("url"),
                "privacy": st.get("privacyStatus"), "published_at": published,
                "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0)),
                "clip": clip_of.get(vid, (None, None))[0]}
        if st.get("privacyStatus") == "public":
            start = (published or end)[:10]
            m = _rows(token, start, end, "views,engagedViews,averageViewDuration,averageViewPercentage,likes,comments,shares,"
                      "subscribersGained", filt=f"video=={vid}")
            if m and m[0].get("views"):
                a = {"views": m[0]["views"], "engaged": m[0].get("engagedViews"), "avg_s": m[0].get("averageViewDuration"),
                     "avg_pct": round(m[0].get("averageViewPercentage") or 0, 1), "shares": m[0].get("shares"),
                     "subs": m[0].get("subscribersGained")}
                a.update(_audience(token, start, end, f"video=={vid}"))
                item["analytics"] = a
            item["comment_list"] = _comments(vid, key)
        item["flags"] = _flags(item)
        videos.append(item)
        if item["clip"]:
            a = item.get("analytics") or {}
            con.execute("INSERT INTO metrics (post_id, views, likes, comments, avg_view_pct, tier1_pct, data) VALUES (?,?,?,?,?,?,?)",
                        (clip_of[vid][1], item["views"], item["likes"], item["comments"], a.get("avg_pct"), a.get("tier1_pct"),
                         json.dumps({"engaged": a.get("engaged"), "under25_pct": a.get("under25_pct")})))
    videos.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    snap = {
        "account": acc_id, "channel": c["snippet"]["title"], "taken_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_through": data_through,
        "totals": {"views": int(c["statistics"].get("viewCount", 0)), "subs": int(c["statistics"].get("subscriberCount", 0)),
                   "videos": int(c["statistics"].get("videoCount", 0))},
        "days": days, "audience": _audience(token, start_ch, end), "videos": videos,
        "comments_enabled": bool(key),
    }
    con.execute("INSERT INTO yt_snapshots (account_id, data) VALUES (?, ?)", (acc_id, json.dumps(snap)))
    con.execute("DELETE FROM yt_snapshots WHERE id NOT IN (SELECT id FROM yt_snapshots ORDER BY id DESC LIMIT 200)")
    log_event(con, "analytics.pulled", acc_id, {"videos": len(videos), "data_through": data_through}, "clipping")
    con.commit()
    return snap


def latest(acc_id: str = "yt-cookedorcracked") -> dict | None:
    con = connect()
    con.execute(_SCHEMA)
    r = con.execute("SELECT data FROM yt_snapshots WHERE account_id=? ORDER BY id DESC LIMIT 1", (acc_id,)).fetchone()
    return json.loads(r["data"]) if r else None


def report(snap: dict) -> str:
    """Text version for the terminal / chat."""
    out = [f"{snap['channel']}: {snap['totals']['views']:,} views, {snap['totals']['subs']} subscribers "
           f"(analytics through {snap['data_through']})"]
    for v in snap["videos"]:
        a = v.get("analytics") or {}
        line = f"- {v['title'][:48]:<48} {v['views']:>7,} views {v['likes']:>4} likes {v['comments']:>3} comments"
        if a:
            line += (f" | engaged {a.get('engaged')} · watched {a.get('avg_pct')}% · tier-1 {a.get('tier1_pct')}% · "
                     f"13-17 {a.get('teen_pct')}%")
        out.append(line)
        out += [f"    ⚠ {f['text']}" for f in v["flags"]]
    return "\n".join(out)
