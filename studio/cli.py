"""`studio` command — how Claude (and you) operate the Studio from chat.

  studio status                      one-screen overview of every campaign + what needs Rishi
  studio requests [room]             messages Rishi sent from the dashboard; `requests done <id>` closes one
  studio ask "question" --options "A|B" [--room id]   one-tap question in Rishi's dashboard inbox
  studio brief "text"                Claude's brief on the Today page (18 h)
  studio notes <clip> [--resolve]    notes Rishi left at moments while reviewing
  studio campaign add <campaign.json> score a campaign brief and store it
  studio campaign list               all campaigns, best first
  studio campaign show <id>          score card + clip checklist
  studio clip approve <id>           mark a clip approved (only on Rishi's say-so)
  studio publish setup|connect|post|stats   YouTube upload + stats (see studio/core/publisher.py)
  studio find add|list                      ideas Rishi spots online, kept for later (dashboard: Finds)
"""
import argparse
import json
import sys
from pathlib import Path

from studio.core.db import connect, log_event
from streams.clipping import campaigns as cr


def campaign_add(path: str):
    b = json.loads(Path(path).read_text())
    v = cr.score(b)
    con = connect()
    con.execute(
        """INSERT INTO campaigns (id, name, source_url, verdict, score, data) VALUES (?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET name=excluded.name, source_url=excluded.source_url,
             verdict=excluded.verdict, score=excluded.score, data=excluded.data""",
        (b["id"], b["name"], b.get("url"), v.verdict, v.score, json.dumps(b)),
    )
    log_event(con, "campaign.scored", b["id"], {"verdict": v.verdict, "score": v.score}, "clipping")
    con.commit()
    print(cr.format_card(b, v))


def campaign_list():
    con = connect()
    rows = con.execute(
        "SELECT id, name, verdict, score, status FROM campaigns "
        "ORDER BY CASE verdict WHEN 'TAKE' THEN 0 WHEN 'MAYBE' THEN 1 ELSE 2 END, score DESC"
    ).fetchall()
    for r in rows:
        print(f"{r['verdict']:<6} {r['score']:>3}  {r['status']:<9} {r['id']:<28} {r['name']}")
    if not rows:
        print("No campaigns yet. Paste a brief into chat and Claude adds it.")


def campaign_show(cid: str):
    con = connect()
    r = con.execute("SELECT data FROM campaigns WHERE id = ?", (cid,)).fetchone()
    if not r:
        sys.exit(f"No campaign '{cid}'.")
    b = json.loads(r["data"])
    print(cr.format_card(b, cr.score(b)))
    print("\n   Clip checklist:")
    for item in cr.checklist(b):
        print(f"   [ ] ({item['when']}) {item['rule']}")


def clip_prep(video: str):
    """Transcribe + face-track a source video; print the readable transcript for moment picking."""
    from studio.render import reframe, transcribe
    w = transcribe.transcribe(Path(video))
    f = reframe.track(Path(video))
    faces = json.loads(f.read_text())
    print(f"words: {w}\nfaces: {f}  ({faces['faces_found']}/{faces['samples']} samples had a face)\n")
    print(transcribe.readable(w))


def clip_render(recipe_path: str, out: str | None):
    """Render a recipe; fills in crop_x from the face track when a segment doesn't set it."""
    from studio.render import checks, reframe, render
    rp = Path(recipe_path)
    recipe = json.loads(rp.read_text())
    for sg in recipe["segments"]:
        faces = Path(sg.get("src") or recipe["source"]).with_suffix(".faces.json")
        if sg.get("crop_x") is None and faces.exists():
            sg["crop_x"] = round(reframe.centre_for(faces, sg["in"], sg["out"]), 4)
    out_path = Path(out) if out else rp.with_suffix(".mp4")
    if recipe.get("mode") == "camera":
        from studio.render import camera
        camera.render(recipe, out_path)
    elif recipe.get("mode") == "montage":
        render.render_montage(recipe, out_path)
    else:
        render.render(recipe, out_path)
    results = checks.run(out_path, recipe)
    print(f"rendered {out_path}")
    print(checks.format_results(results))
    # register in the Studio so the dashboard shows it
    con = connect()
    cid = recipe.get("clip_id") or rp.stem
    passed = all(r["ok"] for r in results)
    data = {"video": str(out_path), "recipe": str(rp), "checks": results, "hook": (recipe.get("hook") or {}).get("text")}
    con.execute(
        """INSERT INTO clips (id, stream, campaign_id, status, data) VALUES (?, 'clipping', ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET status=excluded.status, data=excluded.data, updated_at=datetime('now')""",
        (cid, recipe.get("campaign_id"), "needs_review" if passed else "checks", json.dumps(data)))
    log_event(con, "clip.rendered", cid, {"passed": passed}, "clipping")
    con.commit()


def status():
    """One screen for everything: accounts, every live campaign on one line, and what needs Rishi."""
    con = connect()
    root = Path(__file__).resolve().parent.parent
    print("ACCOUNTS")
    for a in con.execute("SELECT id, platform, handle, status FROM accounts"):
        print(f"  {a['id']:<22} {a['platform']:<9} {a['handle']:<18} {a['status']}")
    print("\nCAMPAIGNS (clips: review/approved/posted · views · est. $)")
    order = "CASE status WHEN 'joined' THEN 0 WHEN 'candidate' THEN 1 ELSE 2 END"
    for c in con.execute(f"SELECT id, name, status, verdict, data FROM campaigns ORDER BY {order}, score DESC"):
        if c["status"] in ("skipped", "ended"):
            continue
        cl = {r["status"]: r["n"] for r in con.execute(
            "SELECT status, COUNT(*) n FROM clips WHERE campaign_id=? GROUP BY status", (c["id"],))}
        views = con.execute("""SELECT COALESCE(SUM(m.views),0) v FROM posts p JOIN clips k ON k.id=p.clip_id
                               JOIN metrics m ON m.post_id=p.id WHERE k.campaign_id=? AND m.taken_at=(
                               SELECT MAX(taken_at) FROM metrics WHERE post_id=p.id)""", (c["id"],)).fetchone()["v"]
        cpm = json.loads(c["data"]).get("cpm_usd") or 0
        nxt = ""
        md = root / "streams" / "clipping" / "campaigns" / c["id"] / "CLAUDE.md"
        if md.exists() and "## Next" in md.read_text():
            nxt = md.read_text().split("## Next", 1)[1].strip().splitlines()[0].lstrip("- ")[:70]
        print(f"  {c['status']:<9} {c['id']:<24} {cl.get('needs_review', 0)}/{cl.get('approved', 0)}/{cl.get('posted', 0)}"
              f"  {views:>7,} views  ~${views / 1000 * cpm:,.2f}")
        if nxt:
            print(f"            next: {nxt}")
    reqs = con.execute("SELECT * FROM requests WHERE done_at IS NULL ORDER BY created_at").fetchall()
    notes = con.execute("SELECT clip_id, COUNT(*) n FROM notes WHERE resolved_at IS NULL GROUP BY clip_id").fetchall()
    answers = con.execute("SELECT * FROM asks WHERE answered_at IS NOT NULL AND answered_at >= datetime('now','-2 days') "
                          "ORDER BY answered_at DESC").fetchall()
    if reqs or notes or answers:
        print("\nFROM THE DASHBOARD")
        for r in reqs:
            print(f"  • [{r['room']}] #{r['id']} {r['text']}   (done: studio requests done {r['id']})")
        for n in notes:
            print(f"  • {n['n']} open note(s) on {n['clip_id']}: see `studio notes {n['clip_id']}`")
        for a in answers:
            print(f"  • answered: {a['question']} → {a['answer']}")
    print("\nNEEDS RISHI")
    todo = [f"review {r['id']} ({r['campaign_id']})" for r in
            con.execute("SELECT id, campaign_id FROM clips WHERE status='needs_review' AND campaign_id IS NOT NULL")]
    todo += [f"SUBMIT {r['url']} on Content Rewards (posted {r['posted_at']} UTC)" for r in
             con.execute("SELECT url, posted_at FROM posts WHERE submitted_at IS NULL")]
    todo += [f"post {r['id']} (approved)" for r in con.execute("SELECT id FROM clips WHERE status='approved'")]
    todo += [f"answer: {r['question']}" for r in con.execute("SELECT question FROM asks WHERE answered_at IS NULL")]
    for r in con.execute("SELECT id FROM accounts WHERE status='warming'"):
        ev = con.execute("SELECT detail FROM events WHERE kind='account.warmup' AND ref=? ORDER BY rowid DESC LIMIT 1",
                         (r["id"],)).fetchone()
        day = json.loads(ev["detail"]).get("day", 0) if ev and ev["detail"] else 0
        todo.append(f"warm-up {r['id']} ({day} of 3 days logged)")
    print("\n".join(f"  • {t}" for t in todo) or "  nothing")


def requests(room: str | None, done: int | None):
    """Messages Rishi sent from the dashboard. `studio requests done <id>` marks one handled."""
    con = connect()
    if done is not None:
        r = con.execute("SELECT * FROM requests WHERE id=?", (done,)).fetchone()
        if not r:
            sys.exit(f"No request {done}.")
        con.execute("UPDATE requests SET done_at=datetime('now') WHERE id=?", (done,))
        log_event(con, "request.done", r["room"], {"text": r["text"]})
        con.commit()
        return print(f"request {done} done")
    q = "SELECT * FROM requests WHERE done_at IS NULL" + (" AND room=?" if room else "") + " ORDER BY created_at"
    rows = con.execute(q, (room,) if room else ()).fetchall()
    for r in rows:
        print(f"  #{r['id']} [{r['room']}] {r['created_at']} UTC  {r['text']}")
    if not rows:
        print("  no open requests" + (f" for {room}" if room else ""))


def ask(question: str, options: str, room: str):
    """Leave Rishi a one-tap question in the dashboard inbox (options separated by |)."""
    con = connect()
    opts = [o.strip() for o in options.split("|") if o.strip()] if options else []
    cur = con.execute("INSERT INTO asks (room, question, options) VALUES (?,?,?)", (room, question, json.dumps(opts)))
    log_event(con, "ask.created", room, {"question": question})
    con.commit()
    print(f"ask #{cur.lastrowid} is in Rishi's inbox")


def brief(text: str):
    """Set Claude's brief shown on Today (shown for 18 hours)."""
    from datetime import datetime, timezone
    p = Path(__file__).resolve().parent / "data" / "brief.json"
    p.write_text(json.dumps({"text": text.strip(), "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}))
    print("brief updated")


def notes(clip_id: str, resolve: bool):
    """Notes Rishi left at moments of a clip; --resolve marks them handled after a new version."""
    con = connect()
    rows = con.execute("SELECT * FROM notes WHERE clip_id=? AND resolved_at IS NULL ORDER BY t", (clip_id,)).fetchall()
    for n in rows:
        print(f"  v{n['version']} @ {n['t']:.1f}s  {n['text']}")
    if not rows:
        print("  no open notes")
    if resolve and rows:
        con.execute("UPDATE notes SET resolved_at=datetime('now') WHERE clip_id=? AND resolved_at IS NULL", (clip_id,))
        con.commit()
        print(f"  {len(rows)} note(s) marked resolved")


def clip_approve(clip_id: str):
    """Only run when Rishi says so in chat (or taps approve on the dashboard/Telegram)."""
    con = connect()
    if not con.execute("SELECT 1 FROM clips WHERE id=?", (clip_id,)).fetchone():
        sys.exit(f"No clip '{clip_id}'.")
    con.execute("UPDATE clips SET status='approved', updated_at=datetime('now') WHERE id=?", (clip_id,))
    log_event(con, "clip.approved", clip_id, {}, "clipping")
    con.commit()
    print(f"{clip_id} approved")


def account_add(acc_id: str, platform: str, handle: str, stream: str):
    con = connect()
    con.execute("INSERT OR IGNORE INTO accounts (id, stream, platform, handle) VALUES (?,?,?,?)",
                (acc_id, stream, platform, handle))
    con.commit()
    print(f"account {acc_id} ({platform} {handle}) registered, status: warming")


def account_warmup(acc_id: str, day: int, note: str | None):
    con = connect()
    log_event(con, "account.warmup", acc_id, {"day": day, "note": note})
    if day >= 3:
        con.execute("UPDATE accounts SET status='active' WHERE id=?", (acc_id,))
    con.commit()
    print(f"{acc_id}: warm-up day {day} logged" + (" — ready to post" if day >= 3 else ""))


def web(port: int):
    from studio.web.server import serve
    serve(port)


def main():
    p = argparse.ArgumentParser(prog="studio")
    sub = p.add_subparsers(dest="area", required=True)
    c = sub.add_parser("campaign").add_subparsers(dest="cmd", required=True)
    c.add_parser("add").add_argument("path")
    c.add_parser("list")
    c.add_parser("show").add_argument("id")
    sub.add_parser("status")
    x = sub.add_parser("requests"); x.add_argument("room", nargs="?"); x.add_argument("id", nargs="?", type=int)
    x = sub.add_parser("ask"); x.add_argument("question"); x.add_argument("--options", default=""); x.add_argument("--room", default="hq")
    x = sub.add_parser("brief"); x.add_argument("text")
    x = sub.add_parser("notes"); x.add_argument("clip"); x.add_argument("--resolve", action="store_true")
    k = sub.add_parser("clip").add_subparsers(dest="cmd", required=True)
    k.add_parser("prep").add_argument("video")
    r = k.add_parser("render"); r.add_argument("recipe"); r.add_argument("-o", "--out")
    k.add_parser("approve").add_argument("id")
    pb = sub.add_parser("publish").add_subparsers(dest="cmd", required=True)
    pb.add_parser("setup").add_argument("client_file")
    pb.add_parser("connect").add_argument("account")
    x = pb.add_parser("post"); x.add_argument("clip"); x.add_argument("account")
    x.add_argument("--at", help='schedule, IST: "2026-09-30 21:30"')
    pb.add_parser("stats")
    pb.add_parser("apikey")
    pb.add_parser("analytics")
    ac = sub.add_parser("account").add_subparsers(dest="cmd", required=True)
    x = ac.add_parser("add"); x.add_argument("id"); x.add_argument("platform"); x.add_argument("handle")
    x.add_argument("--stream", default="clipping")
    x = ac.add_parser("warmup"); x.add_argument("id"); x.add_argument("day", type=int); x.add_argument("--note")
    fd = sub.add_parser("find").add_subparsers(dest="cmd", required=True)
    x = fd.add_parser("add"); x.add_argument("title"); x.add_argument("--url"); x.add_argument("--note")
    x.add_argument("--tags"); x.add_argument("--source")
    fd.add_parser("list")
    w = sub.add_parser("web"); w.add_argument("--port", type=int, default=8787)
    a = p.parse_args()
    if a.area == "status":
        status()
    elif a.area == "requests":
        if a.room == "done":
            if a.id is None:
                sys.exit("usage: studio requests done <id>")
            requests(None, a.id)
        else:
            requests(a.room, None)
    elif a.area == "ask":
        ask(a.question, a.options, a.room)
    elif a.area == "brief":
        brief(a.text)
    elif a.area == "notes":
        notes(a.clip, a.resolve)
    elif a.area == "campaign":
        {"add": lambda: campaign_add(a.path), "list": campaign_list, "show": lambda: campaign_show(a.id)}[a.cmd]()
    elif a.area == "clip":
        {"prep": lambda: clip_prep(a.video), "render": lambda: clip_render(a.recipe, a.out),
         "approve": lambda: clip_approve(a.id)}[a.cmd]()
    elif a.area == "publish":
        from studio.core import publisher as pub
        {"setup": lambda: pub.setup(a.client_file), "connect": lambda: pub.connect(a.account),
         "post": lambda: pub.post(a.clip, a.account, a.at), "stats": pub.stats,
         "apikey": pub.set_api_key,
         "analytics": lambda: print(__import__("studio.core.yt_analytics", fromlist=["x"]).report(
             __import__("studio.core.yt_analytics", fromlist=["x"]).pull()))}[a.cmd]()
    elif a.area == "account":
        {"add": lambda: account_add(a.id, a.platform, a.handle, a.stream),
         "warmup": lambda: account_warmup(a.id, a.day, a.note)}[a.cmd]()
    elif a.area == "find":
        con = connect()
        if a.cmd == "add":
            cur = con.execute("INSERT INTO finds (url, title, note, tags, source) VALUES (?,?,?,?,?)",
                              (a.url, a.title, a.note, a.tags, a.source))
            log_event(con, "find.added", str(cur.lastrowid), {"title": a.title}, "studio")
            con.commit()
            print(f"saved find #{cur.lastrowid}: {a.title}")
        else:
            for r in con.execute("SELECT * FROM finds WHERE archived_at IS NULL ORDER BY id DESC"):
                print(f"#{r['id']} {r['title']}  {r['url'] or ''}\n    {r['note'] or ''}  [{r['tags'] or ''}]")
    elif a.area == "web":
        web(a.port)


if __name__ == "__main__":
    main()
