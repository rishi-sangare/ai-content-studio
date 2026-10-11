"""Cockpit API: everything the dashboard shows (read) and every button it has (act).

The dashboard and the chat share one truth: the Studio database plus the files under streams/.
Every action here logs an event, so Claude sees it on its next `studio status`.
Times from SQLite are UTC; they leave here as ISO strings ending in Z and the browser shows local time.
"""
import json
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from studio.core.db import ROOT, connect, log_event

IST = ZoneInfo("Asia/Kolkata")
CAMPAIGNS = ROOT / "streams" / "clipping" / "campaigns"
SLOTS_IST = ["01:00", "02:30"]            # posting slots: US after-school (15:30 and 17:00 US Eastern in summer)
SUBMIT_MINUTES = 30
WARMUP_DAYS = 3
MEMES = ROOT / "studio" / "render" / "assets" / "sfx" / "memes"
MUSIC = ROOT / "studio" / "render" / "assets" / "music"
EMOJI = ROOT / "studio" / "render" / "assets" / "emoji"
BRIEF = ROOT / "studio" / "data" / "brief.json"


class ActionError(Exception):
    """A button press that can't be done; the message is shown to Rishi as-is."""


# ---- small helpers --------------------------------------------------------------------------------------
def iso(s: str | None) -> str | None:
    """SQLite 'YYYY-MM-DD HH:MM:SS' (UTC) -> ISO with Z."""
    return s.replace(" ", "T") + "Z" if s else None


def parse_utc(s: str) -> datetime:
    return datetime.strptime(s[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def rel(p: Path) -> str:
    return str(Path(p).resolve().relative_to(ROOT))


def file_url(p) -> str | None:
    p = Path(p)
    p = p if p.is_absolute() else ROOT / p
    return "/files/" + quote(rel(p)) if p.exists() else None


def thumb_url(video, t: float = 1.0) -> str | None:
    p = Path(video)
    p = p if p.is_absolute() else ROOT / p
    return f"/thumb?src={quote(rel(p))}&t={t}" if p.exists() else None


@lru_cache(maxsize=512)
def _duration(path: str, mtime: float) -> float | None:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    try:
        return round(float(out), 2)
    except ValueError:
        return None


def duration(p: Path) -> float | None:
    return _duration(str(p), p.stat().st_mtime) if p.exists() else None


def jload(s, default=None):
    try:
        return json.loads(s) if s else default
    except (TypeError, ValueError):
        return default


# ---- clips ----------------------------------------------------------------------------------------------
def clip_dir(row) -> Path | None:
    d = jload(row["data"], {})
    r = d.get("recipe")
    return (ROOT / r).parent if r else None


def versions(row) -> list[dict]:
    """Every saved recipe version of a clip, with its video if it was rendered."""
    d = clip_dir(row)
    if not d or not d.exists():
        return []
    out = []
    for f in d.glob("v*.json"):
        m = re.fullmatch(r"v(\d+)\.json", f.name)
        if not m:
            continue
        n = int(m.group(1))
        vid = d / f"{row['id']}_v{n}.mp4"
        rec = jload(f.read_text(), {}) or {}
        out.append({"n": n, "recipe": rel(f), "video": file_url(vid), "rendered": vid.exists(),
                    "duration": duration(vid), "note": rec.get("version_note", ""),
                    "thumb": thumb_url(vid, 1.0)})
    return sorted(out, key=lambda v: v["n"])


def latest_version(vs: list[dict]) -> dict | None:
    done = [v for v in vs if v["rendered"]]
    return done[-1] if done else None


def beats(recipe_path: Path) -> list[dict]:
    """Meme beats (sound/sticker moments) of a montage recipe, for markers on the review timeline."""
    try:
        from studio.render.render import _resolve_events
        r = json.loads(recipe_path.read_text())
        if not r.get("events") or not r.get("voiceover_words"):
            return []
        words = json.loads((ROOT / r["voiceover_words"]).read_text())["words"]
        spans = json.loads((ROOT / r["voiceover_lines"]).read_text()) if r.get("voiceover_lines") else []
        out = []
        for e in _resolve_events(r["events"], words, spans):
            label = (e.get("sfx") or "").split("|")[0].replace("_", " ")
            if e.get("flash"):
                label = (label + " + flash").strip(" +")
            if e.get("shake"):
                label = (label + " + shake").strip(" +")
            if not label and e.get("sticker"):
                label = "sticker"
            if label:
                out.append({"t": round(e["t"], 2), "label": label})
        return out
    except Exception:
        return []


def post_kit(d: Path | None) -> dict | None:
    return jload((d / "post.json").read_text()) if d and (d / "post.json").exists() else None


def clip_summary(con, row) -> dict:
    vs = versions(row)
    lv = latest_version(vs)
    data = jload(row["data"], {})
    checks = data.get("checks") or []
    all_posts = [dict(x) | {"posted_at": iso(x["posted_at"]), "submitted_at": iso(x["submitted_at"]),
                            "platform": "instagram" if "instagram.com" in (x["url"] or "") else "youtube"}
                 for x in con.execute("SELECT * FROM posts WHERE clip_id=? ORDER BY posted_at", (row["id"],))]
    post = con.execute("SELECT * FROM posts WHERE clip_id=? ORDER BY posted_at DESC LIMIT 1", (row["id"],)).fetchone()
    kit = post_kit(clip_dir(row))
    return {
        "id": row["id"], "campaign": row["campaign_id"], "status": row["status"],
        "version": lv["n"] if lv else None, "versions": len(vs), "thumb": lv["thumb"] if lv else None,
        "duration": lv["duration"] if lv else None,
        "checks_passed": sum(1 for c in checks if c.get("ok")), "checks_total": len(checks),
        "style": (kit or {}).get("style") or style_of(lv["note"] if lv else ""),
        "title": (kit or {}).get("title"), "slot": data.get("slot"),
        "approved_version": data.get("approved_version"),
        "post": dict(post) | {"posted_at": iso(post["posted_at"]), "submitted_at": iso(post["submitted_at"])} if post else None,
        "posts": all_posts,
        "updated_at": iso(row["updated_at"]),
    }


def style_of(note: str) -> str:
    n = (note or "").lower()
    return "meme cut" if "meme" in n else "clean"


# ---- campaigns ------------------------------------------------------------------------------------------
def campaign_row(con, cid):
    r = con.execute("SELECT * FROM campaigns WHERE id=?", (cid,)).fetchone()
    if not r:
        raise ActionError(f"No campaign called {cid}.")
    return r


def short_name(c) -> str:
    n = re.sub(r"\s*[\[(].*?[\])]", "", c["name"]).strip()
    return re.sub(r"\s+clipping$", "", n, flags=re.I) or c["id"]


def campaign_money(con, cid, data) -> dict:
    cpm, cap = data.get("cpm_usd") or 0, data.get("max_payout_usd")
    views = est = 0
    for p in con.execute("""SELECT p.id FROM posts p JOIN clips k ON k.id=p.clip_id WHERE k.campaign_id=?""", (cid,)):
        m = con.execute("SELECT views FROM metrics WHERE post_id=? ORDER BY taken_at DESC LIMIT 1", (p["id"],)).fetchone()
        v = (m["views"] or 0) if m else 0
        views += v
        e = v / 1000 * cpm
        est += min(e, cap) if cap else e
    return {"views": views, "est": round(est, 2)}


def campaign_list(con) -> list[dict]:
    order = "CASE status WHEN 'joined' THEN 0 WHEN 'candidate' THEN 1 ELSE 2 END"
    out = []
    for c in con.execute(f"SELECT * FROM campaigns ORDER BY {order}, score DESC"):
        data = jload(c["data"], {})
        out.append({"id": c["id"], "name": short_name(c), "status": c["status"], "verdict": c["verdict"],
                    "score": c["score"], "cpm": data.get("cpm_usd"), **campaign_money(con, c["id"], data)})
    return out


def memory_path(room: str) -> Path | None:
    if room == "hq":
        return ROOT / "CLAUDE.md"
    if room == "lab":
        return ROOT / "studio" / "CLAUDE.md"
    if room == "influencer":
        return ROOT / "streams" / "influencer" / "CLAUDE.md"
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", room or "") and (CAMPAIGNS / room).is_dir():
        return CAMPAIGNS / room / "CLAUDE.md"
    return None


def next_step(md: Path | None) -> str:
    if not md or not md.exists():
        return ""
    t = md.read_text()
    if "## Next" not in t:
        return ""
    for line in t.split("## Next", 1)[1].strip().splitlines():
        line = re.sub(r"[`*]", "", line.strip().lstrip("-* ")).strip()
        if line:
            return line
    return ""


STAGES = [("ideas", "Ideas"), ("making", "Making"), ("review", "Review"), ("scheduled", "Approved"),
          ("live", "Live"), ("paid", "Paid")]


def stage_of(status: str) -> str:
    return {"planned": "making", "rendering": "making", "checks": "making", "changes_requested": "making",
            "needs_review": "review", "approved": "scheduled", "posted": "live", "submitted": "live",
            "paid": "paid"}.get(status, "review" if status == "rejected" else "making")


def ideas_from_memory(md: Path | None) -> list[str]:
    """Clip ideas listed in the campaign memory under '## Next' ('Next ideas: a, b')."""
    if not md or not md.exists() or "## Next" not in md.read_text():
        return []
    out = []
    for line in md.read_text().split("## Next", 1)[1].splitlines():
        if "idea" in line.lower() and ":" in line:
            out += [x.strip(" .\"'“”") for x in re.split(r",|;", line.split(":", 1)[1]) if x.strip()]
    return [re.sub(r"\s*[—-]\s*in the .*$", "", x).strip(" \"'“”") for x in out if x][:6]


def campaign_detail(cid: str) -> dict:
    con = connect()
    c = campaign_row(con, cid)
    data = jload(c["data"], {})
    md = memory_path(cid)
    clips = [clip_summary(con, r) for r in con.execute(
        "SELECT * FROM clips WHERE campaign_id=? AND status != 'archived' ORDER BY id", (cid,))]
    board = {k: [] for k, _ in STAGES}
    for cl in clips:
        board[stage_of(cl["status"])].append(cl)
    d = CAMPAIGNS / cid
    footage = sorted((d / "footage").glob("*.mp4")) if (d / "footage").exists() else []
    icon = d / "game_icon.png"
    return {
        "id": cid, "name": short_name(c), "full_name": c["name"], "status": c["status"], "verdict": c["verdict"],
        "score": c["score"], "cpm": data.get("cpm_usd"), "max_payout": data.get("max_payout_usd"),
        "owner": data.get("owner"), "url": data.get("url"), "platforms": data.get("platforms") or [],
        "requirements": data.get("requirements") or [],
        "brief": (d / "brief.txt").read_text() if (d / "brief.txt").exists() else "",
        "memory": md.read_text() if md and md.exists() else "", "memory_path": rel(md) if md else None,
        "next": next_step(md), "ideas": ideas_from_memory(md),
        "stages": [{"key": k, "label": lab, "clips": board[k]} for k, lab in STAGES],
        "clips": clips, "money": campaign_money(con, cid, data),
        "icon": file_url(icon) if icon.exists() else None,
        "footage": [{"name": f.stem, "video": file_url(f), "thumb": thumb_url(f, 0.8)} for f in footage],
    }


# ---- review -------------------------------------------------------------------------------------------
def clip_detail(clip_id: str) -> dict:
    con = connect()
    row = con.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
    if not row:
        raise ActionError(f"No clip called {clip_id}.")
    vs = versions(row)
    d = clip_dir(row)
    data = jload(row["data"], {})
    last_rendered = Path(data.get("video", "")).name
    for v in vs:
        v["beats"] = beats(ROOT / v["recipe"])
        v["checks"] = data.get("checks") if last_rendered == f"{clip_id}_v{v['n']}.mp4" else None
    notes = [dict(n) | {"created_at": iso(n["created_at"]), "resolved_at": iso(n["resolved_at"])}
             for n in con.execute("SELECT * FROM notes WHERE clip_id=? ORDER BY created_at", (clip_id,))]
    camp = con.execute("SELECT * FROM campaigns WHERE id=?", (row["campaign_id"],)).fetchone() if row["campaign_id"] else None
    return {
        **clip_summary(con, row), "versions_list": vs, "notes": notes, "kit": post_kit(d),
        "campaign_name": short_name(camp) if camp else None,
        "slots": free_slots(con, exclude=clip_id), "dir": rel(d) if d else None,
    }


# ---- slots ----------------------------------------------------------------------------------------------
def slot_label(s: str) -> str:
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    today = datetime.now(IST).date()
    day = "Today" if dt.date() == today else "Tomorrow" if dt.date() == today + timedelta(days=1) else dt.strftime("%a %d %b")
    et = dt.astimezone(ZoneInfo("America/New_York")).strftime("%H:%M")
    return f"{day} {dt.strftime('%H:%M')} IST · {et} ET"


def upcoming_slots(n: int = 6) -> list[str]:
    now = datetime.now(IST)
    out, day = [], now.date()
    while len(out) < n:
        for hm in SLOTS_IST:
            h, m = map(int, hm.split(":"))
            dt = datetime(day.year, day.month, day.day, h, m, tzinfo=IST)
            if dt > now + timedelta(minutes=10):
                out.append(dt.strftime("%Y-%m-%d %H:%M"))
        day += timedelta(days=1)
    return out[:n]


def taken_slots(con, exclude: str | None = None) -> dict:
    taken = {}
    for r in con.execute("SELECT id, data FROM clips WHERE status IN ('approved', 'posted', 'submitted')"):
        s = jload(r["data"], {}).get("slot")
        if s and r["id"] != exclude:
            taken[s] = r["id"]
    return taken


def free_slots(con, exclude: str | None = None) -> list[dict]:
    taken = taken_slots(con, exclude)
    return [{"value": s, "label": slot_label(s)} for s in upcoming_slots(8) if s not in taken][:5]


# ---- accounts / warm-up ---------------------------------------------------------------------------------
def warmup_state(con, acc) -> dict:
    ev = con.execute("SELECT at, detail FROM events WHERE kind='account.warmup' AND ref=? ORDER BY rowid DESC LIMIT 1",
                     (acc["id"],)).fetchone()
    day = (jload(ev["detail"], {}) or {}).get("day", 0) if ev else 0
    done_today = bool(ev) and parse_utc(ev["at"]).astimezone(IST).date() == datetime.now(IST).date()
    return {"days_logged": day, "done_today": done_today, "needed": WARMUP_DAYS}


_conn_cache: dict = {}


def keychain_connected(acc_id: str) -> bool:
    hit = _conn_cache.get(acc_id)
    if hit and time.time() - hit[1] < 60:
        return hit[0]
    ok = subprocess.run(["security", "find-generic-password", "-s", "studio.youtube.token", "-a", acc_id],
                        capture_output=True).returncode == 0      # existence only; the secret is never read here
    _conn_cache[acc_id] = (ok, time.time())
    return ok


def accounts(con) -> list[dict]:
    out = []
    for a in con.execute("SELECT * FROM accounts ORDER BY created_at"):
        data = jload(a["data"], {})
        out.append({"id": a["id"], "platform": a["platform"], "handle": a["handle"], "status": a["status"],
                    "stream": a["stream"], "channel": data.get("channel_title"),
                    "connected": keychain_connected(a["id"]) if a["platform"] == "youtube" else False,
                    "warmup": warmup_state(con, a)})
    return out


# ---- inbox ("needs you") --------------------------------------------------------------------------------
def inbox(con) -> list[dict]:
    items = []
    now = now_utc()
    for p in con.execute("SELECT * FROM posts WHERE submitted_at IS NULL AND posted_at IS NOT NULL ORDER BY posted_at"):
        deadline = parse_utc(p["posted_at"]) + timedelta(minutes=SUBMIT_MINUTES)
        items.append({"kind": "submit", "key": f"submit:{p['id']}", "urgent": True,
                      "title": f"Submit {p['clip_id']} ({'Instagram' if 'instagram.com' in (p['url'] or '') else 'YouTube'}) on Content Rewards",
                      "detail": "Content Rewards only counts it if you submit within 30 minutes of it going live.",
                      "deadline": deadline.strftime("%Y-%m-%dT%H:%M:%SZ"), "url": p["url"], "clip": p["clip_id"],
                      "actions": [{"label": "I submitted it", "primary": True, "do": {"type": "submitted", "post": p["id"]}}]})
    for a in con.execute("SELECT * FROM asks WHERE answered_at IS NULL ORDER BY created_at"):
        opts = jload(a["options"], []) or []
        items.append({"kind": "ask", "key": f"ask:{a['id']}", "title": a["question"],
                      "detail": f"Claude asked in {room_name(con, a['room'])}",
                      "actions": [{"label": o, "primary": i == 0, "do": {"type": "answer", "ask": a["id"], "answer": o}}
                                  for i, o in enumerate(opts)] or
                                 [{"label": "Answer in chat", "do": {"type": "noop"}}]})
    for r in con.execute("SELECT * FROM clips WHERE status='approved' AND campaign_id IS NOT NULL ORDER BY updated_at"):
        s = clip_summary(con, r)
        if s["post"]:
            continue
        when = slot_label(s["slot"]) if s["slot"] else "no slot picked"
        items.append({"kind": "post", "key": f"post:{r['id']}", "clip": r["id"], "thumb": s["thumb"],
                      "title": f"Post {r['id']} v{s['approved_version'] or s['version']}",
                      "detail": f"{when}. Upload it in YouTube Studio with its posting kit, then paste the link here.",
                      "link": f"#/review/{r['id']}",
                      "actions": [{"label": "Open posting kit", "primary": True, "href": f"#/review/{r['id']}"}]})
    for r in con.execute("SELECT * FROM clips WHERE status='needs_review' AND campaign_id IS NOT NULL ORDER BY updated_at DESC"):
        s = clip_summary(con, r)
        camp = con.execute("SELECT * FROM campaigns WHERE id=?", (r["campaign_id"],)).fetchone()
        cname = short_name(camp) if camp else ""
        dur = f"{s['duration']:.1f} s · " if s["duration"] else ""
        items.append({"kind": "review", "key": f"review:{r['id']}", "clip": r["id"], "thumb": s["thumb"],
                      "title": f"Review {r['id']} v{s['version']}" + (f" · {s['style']}" if s["style"] else ""),
                      "detail": f"{cname} · {dur}"
                                f"{s['checks_passed']} of {s['checks_total']} checks",
                      "link": f"#/review/{r['id']}",
                      "actions": [{"label": "Review", "primary": True, "href": f"#/review/{r['id']}"}]})
    for a in accounts(con):
        w = a["warmup"]
        if a["status"] == "warming" and not w["done_today"]:
            nxt = w["days_logged"] + 1
            items.append({"kind": "warmup", "key": f"warmup:{a['id']}", "account": a["id"],
                          "title": f"Warm-up day {nxt} of {w['needed']} · {a['handle']}",
                          "detail": "Watch and like Roblox Shorts for 15 minutes on the channel, by hand. "
                                    "Tap when today's session is done.",
                          "actions": [{"label": f"Day {nxt} done", "primary": False,
                                       "do": {"type": "warmup_done", "account": a["id"]}}]})
    for c in con.execute("SELECT * FROM campaigns WHERE status='candidate' ORDER BY score DESC"):
        data = jload(c["data"], {})
        bits = [f"{c['verdict']} {c['score']}/100"]
        if data.get("cpm_usd"):
            bits.append(f"${data['cpm_usd']:.2f} per 1K views")
        if data.get("participants"):
            bits.append(f"{data['participants']} clippers")
        items.append({"kind": "decide", "key": f"decide:{c['id']}", "campaign": c["id"],
                      "title": f"{short_name(c)}: join or skip?", "detail": " · ".join(bits),
                      "link": f"#/campaign/{c['id']}",
                      "actions": [{"label": "Skip", "do": {"type": "campaign_decide", "campaign": c["id"], "decision": "skip"}},
                                  {"label": "Join", "do": {"type": "campaign_decide", "campaign": c["id"], "decision": "join"}}]})
    return items


def room_name(con, room: str) -> str:
    if room in ("hq", "lab", "influencer"):
        return {"hq": "HQ", "lab": "Studio Lab", "influencer": "AI influencer"}[room]
    c = con.execute("SELECT name FROM campaigns WHERE id=?", (room,)).fetchone()
    return short_name(c) if c else room


# ---- activity feed --------------------------------------------------------------------------------------
def describe(e) -> str | None:
    d = jload(e["detail"], {}) or {}
    k, ref = e["kind"], e["ref"] or ""
    return {
        "clip.rendered": f"Rendered {ref}" + (" · all checks passed" if d.get("passed") else " · some checks failed"),
        "clip.approved": f"You approved {ref}" + (f" v{d['version']}" if d.get("version") else ""),
        "clip.changes_requested": f"You asked for changes on {ref}",
        "clip.rejected": f"You rejected {ref}",
        "clip.note": f"Note on {ref} at {d.get('t', 0):.1f}s",
        "clip.posted": f"{ref} went live",
        "post.submitted": f"Submitted {ref} on Content Rewards",
        "account.connected": f"Uploader connected to {d.get('channel', ref)}",
        "account.warmup": f"Warm-up day {d.get('day')} logged",
        "campaign.scored": f"Scored {ref}: {d.get('verdict', '')} {d.get('score', '')}".strip(),
        "campaign.joined": f"Joined {ref}",
        "campaign.skipped": f"Skipped {ref}",
        "request.created": f"You told Claude: {d.get('text', '')[:60]}",
        "request.done": f"Claude finished: {d.get('text', '')[:60]}",
        "ask.created": f"Claude asked: {d.get('question', '')[:60]}",
        "ask.answered": f"You answered: {d.get('answer', '')}",
        "memory.saved": f"You edited the {room_label(ref)} memory",
    }.get(k)


def room_label(room):
    return {"hq": "HQ", "lab": "Studio Lab", "influencer": "AI influencer"}.get(room or "hq", room)


def activity(con, limit=30) -> list[dict]:
    out, rendered = [], set()
    real = {r[0] for r in con.execute("SELECT id FROM clips WHERE campaign_id IS NOT NULL")}
    for e in con.execute("SELECT rowid, * FROM events ORDER BY rowid DESC LIMIT 200"):
        if e["kind"] == "clip.rendered":                          # only a clip's latest render matters
            if e["ref"] in rendered or e["ref"] not in real:      # (and never test renders)
                continue
            rendered.add(e["ref"])
        txt = describe(e)
        if txt and not (out and out[-1]["text"] == txt):
            out.append({"at": iso(e["at"]), "text": txt, "kind": e["kind"]})
        if len(out) >= limit:
            break
    return out


# ---- brief ----------------------------------------------------------------------------------------------
def brief(con, items) -> dict:
    if BRIEF.exists():
        b = jload(BRIEF.read_text(), {}) or {}
        if b.get("text") and b.get("at") and now_utc() - parse_utc(b["at"]) < timedelta(hours=18):
            return {"by": "claude", "text": b["text"], "at": b["at"]}
    parts = []
    sub = [i for i in items if i["kind"] == "submit"]
    if sub:
        parts.append(f"Submit {', '.join(i['clip'] for i in sub)} on Content Rewards before the 30 minutes run out.")
    rev = [i["clip"] for i in items if i["kind"] == "review"]
    if rev:
        parts.append(f"{len(rev)} clip{'s' if len(rev) > 1 else ''} waiting for your review ({', '.join(rev)}).")
    post = [i["clip"] for i in items if i["kind"] == "post"]
    if post:
        parts.append(f"{', '.join(post)} {'is' if len(post) == 1 else 'are'} approved and waiting to be posted.")
    for i in items:
        if i["kind"] == "warmup":
            parts.append(f"{i['title'].split(' · ')[1]} is still warming up; posting opens after day {WARMUP_DAYS}.")
    dec = [i["title"].split(":")[0] for i in items if i["kind"] == "decide"]
    if dec:
        parts.append(f"{' and '.join(dec)} {'is' if len(dec) == 1 else 'are'} waiting for a join-or-skip.")
    asks = [i for i in items if i["kind"] == "ask"]
    if asks:
        parts.append(f"Claude has {len(asks)} question{'s' if len(asks) > 1 else ''} for you.")
    return {"by": "studio", "text": " ".join(parts) or "All clear. Nothing needs you right now.",
            "at": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")}


# ---- today ----------------------------------------------------------------------------------------------
def today_slots(con) -> list[dict]:
    """The next two posting slots, each with the clip booked into it (and whether it already went live)."""
    taken = taken_slots(con)
    status = {r["id"]: r["status"] for r in con.execute("SELECT id, status FROM clips")}
    now = datetime.now(IST)
    out = []
    for hm in SLOTS_IST:                                  # today's slots, even if one just passed but was used
        s = now.strftime("%Y-%m-%d ") + hm
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        if dt > now + timedelta(minutes=10) or s in taken:
            out.append(s)
    for s in upcoming_slots(4):
        if s not in out:
            out.append(s)
    res = []
    for s in out[:2]:
        cid = taken.get(s)
        res.append({"value": s, "label": slot_label(s), "clip": cid, "clip_status": status.get(cid)})
    return res


def working_on(con) -> list[dict]:
    out = []
    for r in con.execute("SELECT * FROM requests WHERE done_at IS NULL ORDER BY created_at"):
        out.append({"kind": "request", "id": r["id"], "room": room_name(con, r["room"]), "text": r["text"],
                    "at": iso(r["created_at"])})
    for r in con.execute("SELECT id, updated_at FROM clips WHERE status='changes_requested'"):
        out.append({"kind": "changes", "id": r["id"], "text": f"Changes requested on {r['id']}", "at": iso(r["updated_at"])})
    return out


def state() -> dict:
    con = connect()
    items = inbox(con)
    camps = campaign_list(con)
    posts_week = con.execute("SELECT COUNT(*) n FROM posts WHERE posted_at >= datetime('now','-7 days')").fetchone()["n"]
    return {
        "now": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brief": brief(con, items), "inbox": items, "activity": activity(con), "working": working_on(con),
        "accounts": accounts(con), "campaigns": camps, "slots": today_slots(con),
        "clips": [{"id": r["id"], "campaign": r["campaign_id"], "status": r["status"]}
                  for r in con.execute("SELECT id, campaign_id, status FROM clips WHERE campaign_id IS NOT NULL "
                                       "AND status != 'archived' ORDER BY id")],
        "kpis": {"est": round(sum(c["est"] for c in camps), 2), "views": sum(c["views"] for c in camps),
                 "live_campaigns": sum(1 for c in camps if c["status"] == "joined"), "posts_week": posts_week},
        "version": version(),
    }


def version() -> str:
    """Changes whenever anything the dashboard shows changes (DB rows or memory files)."""
    con = connect()
    q = lambda sql: con.execute(sql).fetchone()[0]
    sig = [q("SELECT COALESCE(MAX(rowid),0) FROM events"), q("SELECT COALESCE(MAX(updated_at),'') FROM clips"),
           q("SELECT COUNT(*) || ':' || COALESCE(MAX(id),0) FROM notes WHERE resolved_at IS NULL"),
           q("SELECT COUNT(*) || ':' || COALESCE(MAX(id),0) FROM requests WHERE done_at IS NULL"),
           q("SELECT COUNT(*) || ':' || COALESCE(MAX(id),0) FROM asks WHERE answered_at IS NULL"),
           q("SELECT COUNT(*) || ':' || COALESCE(MAX(submitted_at),'') FROM posts"),
           q("SELECT COUNT(*) FROM metrics")]
    mt = [p.stat().st_mtime for p in [ROOT / "CLAUDE.md", BRIEF, *CAMPAIGNS.glob("*/CLAUDE.md")] if p.exists()]
    return f"{'|'.join(map(str, sig))}|{max(mt, default=0):.0f}"


# ---- rooms ----------------------------------------------------------------------------------------------
def rooms() -> list[dict]:
    con = connect()
    out = [{"id": "hq", "name": "HQ", "kind": "hq", "status": "home",
            "about": "Daily brief, new campaigns, money and strategy. Sees every room's one-line summary, never the details."},
           {"id": "lab", "name": "Studio Lab", "kind": "lab", "status": "building",
            "about": "Building the Studio itself: dashboard, renderer, uploader. Code talk stays here."}]
    for c in campaign_list(con):
        out.append({"id": c["id"], "name": c["name"], "kind": "campaign", "status": c["status"],
                    "about": f"Everything for this campaign and nothing else. {c['verdict']} {c['score']}/100."})
    out.append({"id": "influencer", "name": "AI influencer", "kind": "stream", "status": "paused",
                "about": "The Rishi Water reel work waits here until you restart it."})
    for r in out:
        p = memory_path(r["id"])
        text = p.read_text() if p and p.exists() else ""
        r.update(memory_path=rel(p) if p else None, memory_lines=len(text.splitlines()),
                 memory_updated=datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                 if p and p.exists() else None,
                 next=next_step(p), starter=starter(r, p))
        r["open_requests"] = con.execute("SELECT COUNT(*) FROM requests WHERE room=? AND done_at IS NULL",
                                         (r["id"],)).fetchone()[0]
    return out


def starter(room: dict, p: Path | None) -> str:
    """First message for a new chat session in this room."""
    if room["id"] == "hq":
        return ("This chat is HQ. Run `uv run studio status` first. Keep to the overview: daily brief, new campaigns, "
                "money and decisions; open a campaign's folder only when I ask about that campaign.")
    where = rel(p.parent) if p else ""
    return (f"This chat is the {room['name']} room. Work only inside {where}/ and read {rel(p) if p else 'its CLAUDE.md'} "
            f"first. Check `uv run studio requests {room['id']}` for anything I sent from the dashboard.")


def memory(room: str) -> dict:
    p = memory_path(room)
    if not p:
        raise ActionError("Unknown room.")
    return {"room": room, "path": rel(p), "text": p.read_text() if p.exists() else ""}


# ---- library / accounts / money -------------------------------------------------------------------------
def library() -> dict:
    def files(d: Path, exts):
        return sorted([f for f in d.glob("*") if f.suffix.lower() in exts], key=lambda f: f.name) if d.exists() else []
    return {
        "memes": [{"name": f.stem.replace("_", " "), "id": f.stem, "url": file_url(f), "duration": duration(f)}
                  for f in files(MEMES, {".wav", ".mp3"})],
        "music": [{"name": f.stem.replace("_", " ").title(), "url": file_url(f), "duration": duration(f),
                   "credit": "Kevin MacLeod (incompetech.com), CC BY 4.0"} for f in files(MUSIC, {".mp3"})],
        "emoji": [{"id": f.stem, "url": file_url(f), "char": chr(int(f.stem, 16))} for f in files(EMOJI, {".png"})],
        "voices": [{"name": "Cooked or Cracked narrator", "url": file_url(ROOT / "streams/clipping/brand/cooked-or-cracked/voice/reference.wav")}],
    }


def money() -> dict:
    con = connect()
    posts = []
    for p in con.execute("""SELECT p.*, k.campaign_id FROM posts p JOIN clips k ON k.id=p.clip_id ORDER BY p.posted_at DESC"""):
        m = con.execute("SELECT * FROM metrics WHERE post_id=? ORDER BY taken_at DESC LIMIT 1", (p["id"],)).fetchone()
        posts.append({"id": p["id"], "clip": p["clip_id"], "campaign": p["campaign_id"], "url": p["url"],
                      "posted_at": iso(p["posted_at"]), "submitted_at": iso(p["submitted_at"]),
                      "views": m["views"] if m else None, "likes": m["likes"] if m else None,
                      "comments": m["comments"] if m else None, "payout": p["payout_usd"]})
    return {"campaigns": campaign_list(con), "posts": posts}


# ---- finds (ideas Rishi spots online, kept for later) ---------------------------------------------------
def finds() -> dict:
    con = connect()
    rows = con.execute("SELECT * FROM finds WHERE archived_at IS NULL ORDER BY added_at DESC, id DESC").fetchall()
    return {"finds": [{"id": r["id"], "url": r["url"], "title": r["title"], "note": r["note"], "source": r["source"],
                       "tags": [t.strip() for t in (r["tags"] or "").split(",") if t.strip()], "added_at": iso(r["added_at"])}
                      for r in rows]}


# ---- analytics ------------------------------------------------------------------------------------------
import threading
_pull_lock = threading.Lock()
_pull_state = {"running": False, "error": None}


def _pull_bg():
    from studio.core import yt_analytics
    if not _pull_lock.acquire(blocking=False):
        return
    _pull_state.update(running=True, error=None)

    def run():
        try:
            yt_analytics.pull()
        except SystemExit as e:                     # e.g. the weekly Google sign-in expired
            _pull_state["error"] = str(e)
        except Exception as e:
            _pull_state["error"] = f"{type(e).__name__}: {e}"[:300]
        finally:
            _pull_state["running"] = False
            _pull_lock.release()
    threading.Thread(target=run, daemon=True).start()


# ---- posting schedule (studio/data/schedule.json, written by streams/clipping/schedule.py) ----------------------------
SCHEDULE = ROOT / "studio" / "data" / "schedule.json"


def schedule() -> dict:
    if not SCHEDULE.exists():
        return {"posts": [], "updated": None}
    d = json.loads(SCHEDULE.read_text())
    now = datetime.now(IST)
    for e in d["posts"]:
        at = datetime.strptime(e["at"], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        e["preview_url"] = file_url(e["preview"])
        e["thumb"] = thumb_url(e["preview"], 1.0)
        e["label"] = at.strftime("%-I:%M %p") + " IST"
        tonight = at.date() == (now + timedelta(days=1)).date() and at.hour < 8 and now.hour >= 8
        e["day"] = ("Tonight · " if tonight or (at.date() == now.date() and at > now) else "") + at.strftime("%a %d %b")
        e["live"] = at <= now
        e["mins_to_live"] = int((at - now).total_seconds() // 60)
        for f in ("yt_file", "ig_file"):
            e[f + "_ok"] = Path(e[f]).exists()
    return d


def _schedule_edit(post_id: str, plat: str, **kv):
    d = json.loads(SCHEDULE.read_text())
    e = next((x for x in d["posts"] if x["id"] == post_id), None)
    if not e or plat not in ("youtube", "instagram"):
        raise ActionError("That post isn't on the schedule.")
    e[plat].update(kv)
    SCHEDULE.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    return e


def analytics() -> dict:
    """Latest YouTube snapshot; starts a fresh pull in the background when it's older than 20 minutes."""
    from studio.core import yt_analytics
    snap = yt_analytics.latest()
    age = (now_utc() - parse_utc(snap["taken_at"].replace("T", " ").rstrip("Z"))).total_seconds() if snap else None
    if (age is None or age > 20 * 60) and not _pull_state["running"]:
        _pull_bg()
    return {"snapshot": snap, "refreshing": _pull_state["running"], "error": _pull_state["error"]}


# ---- actions --------------------------------------------------------------------------------------------
def act(a: dict) -> dict:
    t = a.get("type")
    con = connect()
    try:
        msg = _act(con, t, a)
        con.commit()
        return {"ok": True, "message": msg}
    finally:
        con.close()


def _clip(con, cid):
    r = con.execute("SELECT * FROM clips WHERE id=?", (cid,)).fetchone()
    if not r:
        raise ActionError(f"No clip called {cid}.")
    return r


def _set_clip(con, cid, status, **data):
    r = _clip(con, cid)
    d = jload(r["data"], {})
    d.update({k: v for k, v in data.items()})
    con.execute("UPDATE clips SET status=?, data=?, updated_at=datetime('now') WHERE id=?", (status, json.dumps(d), cid))


def _text(a, key, limit=2000, required=True):
    v = (a.get(key) or "").strip()
    if required and not v:
        raise ActionError("Write something first.")
    return v[:limit]


def _act(con, t, a) -> str:
    if t == "find_add":
        url = (a.get("url") or "").strip()[:500]
        note = _text(a, "note", 2000, required=not url)
        title = (a.get("title") or "").strip()[:200] or (url.split("//")[-1].split("?")[0].rstrip("/") if url else note[:80])
        cur = con.execute("INSERT INTO finds (url, title, note, source) VALUES (?,?,?,?)", (url or None, title, note, "dashboard"))
        log_event(con, "find.added", str(cur.lastrowid), {"title": title}, "studio")
        return "Saved to Finds. Claude can pick it up later."
    if t == "find_archive":
        con.execute("UPDATE finds SET archived_at=datetime('now') WHERE id=?", (int(a["find"]),))
        log_event(con, "find.archived", str(a["find"]), {}, "studio")
        return "Archived"
    if t == "analytics_refresh":
        _pull_bg()
        return "Pulling the latest numbers from YouTube…"
    if t == "approve":
        r = _clip(con, a["clip"])
        if r["status"] not in ("needs_review", "changes_requested", "rejected", "approved"):
            raise ActionError(f"{a['clip']} is already {r['status'].replace('_', ' ')}.")
        slot = a.get("slot") or None
        if slot and slot in taken_slots(con, exclude=a["clip"]):
            raise ActionError("That slot was just taken by another clip. Pick another.")
        ver = int(a["version"]) if a.get("version") else None
        _set_clip(con, a["clip"], "approved", slot=slot, approved_version=ver)
        log_event(con, "clip.approved", a["clip"], {"version": ver, "slot": slot}, "clipping")
        return f"Approved {a['clip']}" + (f" for {slot_label(slot)}" if slot else "")
    if t == "unapprove":
        _set_clip(con, a["clip"], "needs_review", slot=None)
        log_event(con, "clip.unapproved", a["clip"], {}, "clipping")
        return f"{a['clip']} is back in review"
    if t == "request_changes":
        text = _text(a, "text", required=False)
        r = _clip(con, a["clip"])
        _set_clip(con, a["clip"], "changes_requested", slot=None)
        notes = con.execute("SELECT COUNT(*) FROM notes WHERE clip_id=? AND resolved_at IS NULL", (a["clip"],)).fetchone()[0]
        body = f"Changes requested on {a['clip']}" + (f": {text}" if text else "") + (f" (+{notes} notes on the video)" if notes else "")
        con.execute("INSERT INTO requests (room, text) VALUES (?, ?)", (r["campaign_id"] or "hq", body))
        log_event(con, "clip.changes_requested", a["clip"], {"text": text}, "clipping")
        return "Sent to Claude. The clip moves back to Making."
    if t == "reject":
        _clip(con, a["clip"])
        _set_clip(con, a["clip"], "rejected", slot=None)
        log_event(con, "clip.rejected", a["clip"], {}, "clipping")
        return f"Rejected {a['clip']}"
    if t == "note":
        _clip(con, a["clip"])
        text = _text(a, "text", 500)
        tt = max(0.0, float(a.get("t") or 0))
        con.execute("INSERT INTO notes (clip_id, version, t, text) VALUES (?,?,?,?)",
                    (a["clip"], a.get("version"), round(tt, 2), text))
        log_event(con, "clip.note", a["clip"], {"t": round(tt, 2), "text": text}, "clipping")
        return f"Note saved at {int(tt // 60)}:{tt % 60:04.1f}"
    if t == "note_delete":
        con.execute("DELETE FROM notes WHERE id=? AND resolved_at IS NULL", (int(a["note"]),))
        return "Note removed"
    if t == "posted":
        r = _clip(con, a["clip"])
        url = _text(a, "url", 300)
        if not re.match(r"^https://(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com|instagram\.com)/", url):
            raise ActionError("Paste the full link to the live post (https://youtube.com/shorts/… or https://instagram.com/reel/…).")
        if r["status"] not in ("approved", "posted", "submitted"):
            raise ActionError(f"Approve {a['clip']} before marking it posted.")
        platform = "instagram" if "instagram.com" in url else "youtube"
        acc = a.get("account") or (con.execute("SELECT id FROM accounts WHERE platform=? ORDER BY created_at LIMIT 1",
                                               (platform,)).fetchone() or {"id": None})["id"]
        if not acc:
            raise ActionError(f"No {platform.title()} account in the Studio yet. Tell Claude your handle and it adds it.")
        pid = f"{a['clip']}@{acc}"
        con.execute("""INSERT INTO posts (id, clip_id, account_id, url, posted_at, data) VALUES (?,?,?,?,datetime('now'),'{}')
                       ON CONFLICT(id) DO UPDATE SET url=excluded.url, posted_at=excluded.posted_at""", (pid, a["clip"], acc, url))
        if r["status"] == "approved":
            _set_clip(con, a["clip"], "posted")
        else:
            con.execute("UPDATE clips SET updated_at=datetime('now') WHERE id=?", (a["clip"],))
        log_event(con, "clip.posted", a["clip"], {"url": url, "account": acc, "platform": platform}, "clipping")
        return f"Marked live on {platform.title()}. Your 30-minute submit timer has started."
    if t == "submitted":
        p = con.execute("SELECT * FROM posts WHERE id=?", (a["post"],)).fetchone()
        if not p:
            raise ActionError("That post isn't in the Studio.")
        con.execute("UPDATE posts SET submitted_at=datetime('now') WHERE id=?", (a["post"],))
        con.execute("UPDATE clips SET status='submitted', updated_at=datetime('now') WHERE id=?", (p["clip_id"],))
        log_event(con, "post.submitted", p["clip_id"], {"post": p["id"]}, "clipping")
        return "Submitted. Views will be tracked from here."
    if t == "warmup_done":
        acc = con.execute("SELECT * FROM accounts WHERE id=?", (a["account"],)).fetchone()
        if not acc:
            raise ActionError("Unknown account.")
        w = warmup_state(con, acc)
        if w["done_today"]:
            raise ActionError("Today's warm-up is already logged.")
        day = w["days_logged"] + 1
        log_event(con, "account.warmup", acc["id"], {"day": day, "note": "from dashboard"})
        if day >= WARMUP_DAYS:
            con.execute("UPDATE accounts SET status='active' WHERE id=?", (acc["id"],))
            return f"Day {day} logged. {acc['handle']} is ready to post."
        return f"Day {day} of {WARMUP_DAYS} logged"
    if t == "campaign_decide":
        c = campaign_row(con, a["campaign"])
        if a.get("decision") not in ("join", "skip"):
            raise ActionError("Pick join or skip.")
        status = "joined" if a["decision"] == "join" else "skipped"
        con.execute("UPDATE campaigns SET status=? WHERE id=?", (status, c["id"]))
        log_event(con, f"campaign.{status}", c["id"], {}, "clipping")
        if status == "joined":
            con.execute("INSERT INTO requests (room, text) VALUES (?, ?)",
                        (c["id"], f"Rishi joined {short_name(c)} from the dashboard. Set up its room and plan the first clip."))
        return f"{'Joined' if status == 'joined' else 'Skipped'} {short_name(c)}"
    if t == "answer":
        ask = con.execute("SELECT * FROM asks WHERE id=? AND answered_at IS NULL", (int(a["ask"]),)).fetchone()
        if not ask:
            raise ActionError("That question was already answered.")
        ans = _text(a, "answer", 300)
        con.execute("UPDATE asks SET answer=?, answered_at=datetime('now') WHERE id=?", (ans, ask["id"]))
        log_event(con, "ask.answered", ask["room"], {"question": ask["question"], "answer": ans})
        return "Answer sent to Claude"
    if t == "tell":
        room = a.get("room") or "hq"
        if not memory_path(room):
            raise ActionError("Unknown room.")
        text = _text(a, "text")
        con.execute("INSERT INTO requests (room, text) VALUES (?, ?)", (room, text))
        log_event(con, "request.created", room, {"room": room, "text": text})
        return f"Queued for Claude in {room_label(room) if room in ('hq', 'lab', 'influencer') else room_name(con, room)}"
    if t == "request_cancel":
        con.execute("DELETE FROM requests WHERE id=? AND done_at IS NULL", (int(a["request"]),))
        return "Removed"
    if t == "memory_save":
        p = memory_path(a.get("room", ""))
        if not p:
            raise ActionError("Unknown room.")
        text = a.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ActionError("Memory can't be empty.")
        if p.exists() and a.get("base") is not None and p.read_text() != a["base"]:
            raise ActionError("Claude changed this memory while you were editing. Reload it and edit again.")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if text.endswith("\n") else text + "\n")
        log_event(con, "memory.saved", a["room"], {})
        return "Memory saved"
    if t == "sched_link":
        url = _text(a, "url", 300, required=False).strip()
        if url and not re.match(r"^https://(www\.|m\.)?(youtube\.com|youtu\.be|instagram\.com)/", url):
            raise ActionError("Paste the full link (https://youtube.com/shorts/… or https://www.instagram.com/reel/…).")
        e = _schedule_edit(a["post"], a["platform"], link=url or None, scheduled=bool(url) or None)
        log_event(con, "schedule.link", e["clip"], {"platform": a["platform"], "url": url}, "clipping")
        return f"Saved the {'YouTube' if a['platform'] == 'youtube' else 'Instagram'} link for {e['clip']}." if url else "Link removed."
    if t == "sched_tick":
        e = _schedule_edit(a["post"], a["platform"], **{a["field"]: bool(a.get("value"))} if a.get("field") in ("scheduled", "submitted") else {})
        return f"{e['clip']} {'YouTube' if a['platform'] == 'youtube' else 'Instagram'}: {a['field']} {'✓' if a.get('value') else 'cleared'}."
    if t == "reveal":
        p = Path(a.get("path", "")).resolve()
        if ROOT not in p.parents or not p.exists():
            raise ActionError("That file isn't in the project anymore.")
        subprocess.run(["open", "-R", str(p)], check=False)
        return "Opened in Finder."
    if t == "noop":
        return "Answer this one in the chat"
    raise ActionError("Unknown action.")
