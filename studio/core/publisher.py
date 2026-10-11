"""Publisher: the only code that touches platform tokens. They live in the macOS Keychain, never in the db,
files or chat.

  studio publish setup <client_secret.json>       store the Google OAuth client (Desktop app) in the Keychain
  studio publish connect <account>                one-time Google sign-in for that channel (refresh token -> Keychain)
  studio publish post <clip> <account> [--at ..]  upload an APPROVED clip using <clip dir>/post.json
  studio publish stats                            pull views / likes / comments for every posted YouTube video

Uses the YouTube Data API v3 over plain HTTPS (stdlib only). Scopes: upload + read-only + YouTube Analytics (read-only). Nothing that can delete or edit.
"""
import base64
import hashlib
import json
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from studio.core.db import ROOT, connect as db, log_event

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]   # read-only: retention, countries, traffic sources
CLIENT_SVC, TOKEN_SVC = "studio.youtube.client", "studio.youtube.token"
APIKEY_SVC = "studio.youtube.apikey"     # public read-only key (comment text); OAuth stays read+upload only
IST = ZoneInfo("Asia/Kolkata")


# ---- Keychain -------------------------------------------------------------------------------------------
def _kc_set(service: str, account: str, secret: str):
    subprocess.run(["security", "add-generic-password", "-U", "-s", service, "-a", account, "-w", secret],
                   check=True, capture_output=True)


def _kc_get(service: str, account: str) -> str | None:
    r = subprocess.run(["security", "find-generic-password", "-s", service, "-a", account, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


# ---- HTTP -----------------------------------------------------------------------------------------------
def _http(method, url, token=None, body=None, form=None, headers=None, raw=None):
    h = dict(headers or {})
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json; charset=UTF-8"
    elif raw is not None:
        data = raw
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            txt = r.read().decode() or "{}"
            return json.loads(txt), dict(r.headers)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} from Google: {e.read().decode()[:800]}") from None


# ---- OAuth ----------------------------------------------------------------------------------------------
def setup(client_file: str):
    """Store the downloaded OAuth client JSON in the Keychain (it is not printed)."""
    c = json.loads(Path(client_file).expanduser().read_text())
    c = c.get("installed") or c.get("web")
    if not c or "client_id" not in c:
        sys.exit("That file isn't an OAuth client JSON (expected an 'installed' Desktop-app client).")
    _kc_set(CLIENT_SVC, "google", json.dumps({"client_id": c["client_id"], "client_secret": c["client_secret"]}))
    print("OAuth client saved to the Keychain. Move the downloaded JSON to the Trash now.")


def set_api_key():
    """Save a YouTube Data API key (restricted to read public data, e.g. comment text) in the Keychain.

    Typed at a hidden prompt, never printed, never in chat or the db."""
    import getpass
    key = getpass.getpass("Paste the API key (hidden), then Enter: ").strip()
    if not key.startswith("AIza") or len(key) < 30:
        sys.exit("That doesn't look like a Google API key (they start with 'AIza'). Nothing saved.")
    try:                                                   # (errors never echo the key)
        urllib.request.urlopen(f"{API}/videos?part=id&id=dQw4w9WgXcQ&key={key}", timeout=20)
    except Exception:
        sys.exit("Google didn't accept that key (is the YouTube Data API v3 allowed on it?). Nothing saved.")
    _kc_set(APIKEY_SVC, "google", key)
    print("API key checked and saved to the Keychain. You can close the Cloud tab.")


def _api_key() -> str | None:
    return _kc_get(APIKEY_SVC, "google")


def _client() -> dict:
    s = _kc_get(CLIENT_SVC, "google")
    if not s:
        sys.exit("No OAuth client yet: run `studio publish setup <client_secret.json>` first.")
    return json.loads(s)


def connect(acc_id: str):
    """Open Google sign-in in the browser; the user picks the channel and clicks Allow."""
    c = _client()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    got = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if "code" in q or "error" in q:
                got.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "Connected. You can close this tab." if "code" in q else f"Sign-in failed: {q.get('error', '?')}"
            self.wfile.write(f"<h2 style='font-family:sans-serif'>{msg}</h2>".encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    srv.timeout = 300
    redirect = f"http://127.0.0.1:{srv.server_port}"
    url = AUTH + "?" + urllib.parse.urlencode(dict(
        client_id=c["client_id"], redirect_uri=redirect, response_type="code", scope=" ".join(SCOPES),
        access_type="offline", prompt="consent", code_challenge=challenge, code_challenge_method="S256", state=state))
    print("Opening Google sign-in. Pick the Cooked or Cracked channel, then Allow.\n" + url)
    webbrowser.open(url)
    while not got:
        srv.handle_request()
        if not got:
            sys.exit("Timed out waiting for sign-in.")
    if got.get("state") != state or "code" not in got:
        sys.exit(f"Sign-in failed: {got.get('error', 'state mismatch')}")
    tok, _ = _http("POST", TOKEN, form=dict(
        code=got["code"], client_id=c["client_id"], client_secret=c["client_secret"], redirect_uri=redirect,
        grant_type="authorization_code", code_verifier=verifier))
    if "refresh_token" not in tok:
        sys.exit("Google returned no refresh token; remove the app at myaccount.google.com/permissions and retry.")
    _kc_set(TOKEN_SVC, acc_id, tok["refresh_token"])
    ch, _ = _http("GET", f"{API}/channels?part=snippet&mine=true", tok["access_token"])
    items = ch.get("items") or []
    if not items:
        sys.exit("Signed in, but that Google identity has no YouTube channel. Retry and pick the channel.")
    snip = items[0]["snippet"]
    con = db()
    row = con.execute("SELECT data FROM accounts WHERE id=?", (acc_id,)).fetchone()
    data = json.loads(row["data"]) if row else {}
    data.update(channel_id=items[0]["id"], channel_title=snip["title"])
    con.execute("UPDATE accounts SET data=? WHERE id=?", (json.dumps(data), acc_id))
    log_event(con, "account.connected", acc_id, {"channel": snip["title"]})
    con.commit()
    print(f"Connected {acc_id} -> {snip['title']} ({snip.get('customUrl', items[0]['id'])})")


def _access(acc_id: str) -> str:
    rt = _kc_get(TOKEN_SVC, acc_id)
    if not rt:
        sys.exit(f"{acc_id} isn't connected: run `studio publish connect {acc_id}`.")
    c = _client()
    try:
        tok, _ = _http("POST", TOKEN, form=dict(client_id=c["client_id"], client_secret=c["client_secret"],
                                                refresh_token=rt, grant_type="refresh_token"))
    except RuntimeError as e:
        if "invalid_grant" in str(e):
            # apps in 'Testing' status get 7-day sign-ins
            sys.exit(f"The weekly Google sign-in for {acc_id} expired: run `studio publish connect {acc_id}`.")
        raise
    return tok["access_token"]


# ---- Upload ---------------------------------------------------------------------------------------------
def post(clip_id: str, acc_id: str, at: str | None = None):
    """Upload an approved clip. --at "2026-09-30 21:30" (IST) schedules it; otherwise it goes public now."""
    con = db()
    clip = con.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
    acc = con.execute("SELECT * FROM accounts WHERE id=?", (acc_id,)).fetchone()
    if not clip or not acc:
        sys.exit("Unknown clip or account.")
    if clip["status"] != "approved":
        sys.exit(f"{clip_id} is '{clip['status']}'. Nothing is posted until Rishi approves it (studio clip approve).")
    if acc["status"] != "active":
        sys.exit(f"{acc_id} is still '{acc['status']}' (warm-up not finished).")
    video = ROOT / json.loads(clip["data"])["video"]
    kit = json.loads((video.parent / "post.json").read_text())

    status = {"selfDeclaredMadeForKids": False, "containsSyntheticMedia": bool(kit.get("synthetic_media", True)),
              "privacyStatus": "public", "embeddable": True}
    when = None
    if at:
        when = datetime.fromisoformat(at).replace(tzinfo=IST)
        status.update(privacyStatus="private", publishAt=when.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"))
    meta = {"snippet": {"title": kit["title"], "description": kit["description"], "tags": kit.get("tags", []),
                        "categoryId": "20", "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": status,
            "paidProductPlacementDetails": {"hasPaidProductPlacement": bool(kit.get("paid_promotion", False))}}
    token = _access(acc_id)
    size = video.stat().st_size
    hdr = {"X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)}
    parts, warn = "snippet,status,paidProductPlacementDetails", None
    try:
        _, h = _http("POST", f"{UPLOAD}?uploadType=resumable&part={parts}", token, body=meta, headers=hdr)
    except RuntimeError as e:
        if "paidProductPlacement" not in str(e):
            raise
        meta.pop("paidProductPlacementDetails")
        warn = "The API refused the paid-promotion flag: tick it in YouTube Studio."
        _, h = _http("POST", f"{UPLOAD}?uploadType=resumable&part=snippet,status", token, body=meta, headers=hdr)
    loc = h.get("Location") or h.get("location")
    print(f"uploading {video.name} ({size / 1e6:.1f} MB)...")
    res, _ = _http("PUT", loc, token, raw=video.read_bytes(), headers={"Content-Type": "video/mp4"})
    vid = res["id"]
    url = f"https://youtube.com/shorts/{vid}"
    got_privacy = res.get("status", {}).get("privacyStatus")

    con.execute("""INSERT INTO posts (id, clip_id, account_id, url, posted_at, data) VALUES (?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET url=excluded.url, posted_at=excluded.posted_at, data=excluded.data""",
                (f"{clip_id}@{acc_id}", clip_id, acc_id, url,
                 (when or datetime.now(IST)).astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S"),
                 json.dumps({"video_id": vid, "privacy": got_privacy, "scheduled": bool(when)})))
    con.execute("UPDATE clips SET status='posted', account_id=?, updated_at=datetime('now') WHERE id=?", (acc_id, clip_id))
    log_event(con, "clip.posted", clip_id, {"account": acc_id, "url": url, "privacy": got_privacy}, "clipping")
    con.commit()
    print(f"posted: {url}  (privacy: {got_privacy}{', goes live ' + at + ' IST' if when else ''})")
    if not when and got_privacy != "public":
        print("⚠️  YouTube kept it private. Unaudited API projects are locked to private until the audit passes.")
    if warn:
        print("⚠️  " + warn)
    if kit.get("pinned_comment"):
        print(f"📌 Pin this comment yourself (the API can't pin): {kit['pinned_comment']}")
    print("⏱  Submit the link on Content Rewards within 30 minutes of it going live.")


# ---- Stats ----------------------------------------------------------------------------------------------
def _video_id(url: str) -> str | None:
    """https://youtube.com/shorts/<id>, youtu.be/<id> or watch?v=<id> -> <id>."""
    import re
    m = re.search(r"(?:shorts/|youtu\.be/|[?&]v=)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def stats():
    con = db()
    rows = con.execute("SELECT p.id, p.account_id, p.url, p.data FROM posts p JOIN accounts a ON a.id=p.account_id "
                       "WHERE a.platform='youtube'").fetchall()
    by_acc = {}
    for r in rows:
        vid = (json.loads(r["data"] or "{}") or {}).get("video_id") or _video_id(r["url"] or "")
        if vid:                                   # posts marked live by hand only have their link
            by_acc.setdefault(r["account_id"], []).append((r["id"], vid))
    for acc_id, posts in by_acc.items():
        token = _access(acc_id)
        ids = ",".join(v for _, v in posts)
        res, _ = _http("GET", f"{API}/videos?part=statistics,status&id={ids}", token)
        found = {i["id"]: i for i in res.get("items", [])}
        for pid, vid in posts:
            s = found.get(vid, {}).get("statistics", {})
            views, likes, comments = (int(s.get(k, 0)) for k in ("viewCount", "likeCount", "commentCount"))
            con.execute("INSERT INTO metrics (post_id, views, likes, comments) VALUES (?,?,?,?)",
                        (pid, views, likes, comments))
            eng = (likes + comments) / views * 100 if views else 0
            print(f"{pid:<32} {views:>8} views  {likes:>6} likes  {comments:>5} comments  "
                  f"engagement {eng:.1f}%")
    con.commit()
    if not rows:
        print("No YouTube posts yet.")
