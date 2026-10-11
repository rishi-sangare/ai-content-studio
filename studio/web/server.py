"""Studio cockpit server: a local web app over the Studio database (stdlib only).

Run:  uv run studio web        → http://127.0.0.1:8787   (also opens in the Claude app's browser pane)

- GET  /                 the app (studio/web/static)
- GET  /api/state        Today, inbox, activity, accounts, campaigns
- GET  /api/campaign/<id>, /api/clip/<id>, /api/rooms, /api/memory/<room>, /api/library, /api/money
- GET  /api/stream       server-sent events: a new version string whenever anything changes
- POST /api/action       every button (approve, note, posted, submitted, warm-up, tell Claude…)
- GET  /files/<path>     videos/audio/images (Range requests for seeking), only from streams/ and assets
- GET  /thumb?src=&t=    cached video thumbnails

Listens on 127.0.0.1 only. POSTs need the X-Studio header, so other websites can't press buttons.
"""
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from studio.core.db import ROOT
from studio.web import api

STATIC = Path(__file__).resolve().parent / "static"
THUMBS = ROOT / "studio" / "data" / "cache" / "thumbs"
SERVABLE = [ROOT / "streams", ROOT / "studio" / "render" / "assets"]
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("audio/wav", ".wav")


def servable(p: Path) -> bool:
    p = p.resolve()
    return p.is_file() and any(base in p.parents for base in SERVABLE)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    # ---- responses ----
    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), extra={"Cache-Control": "no-store"})

    # ---- GET ----
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urlparse(self.path)
        path = unquote(u.path)
        try:
            if path == "/" or path == "/index.html":
                return self._static("index.html")
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])
            if path == "/api/stream":
                return self._stream()
            if path.startswith("/api/"):
                return self._api(path[5:], parse_qs(u.query))
            if path.startswith("/files/"):
                return self._file(ROOT / path[len("/files/"):])
            if path == "/thumb":
                q = parse_qs(u.query)
                return self._thumb(q.get("src", [""])[0], q.get("t", ["1"])[0])
            if path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            self._json({"error": "Not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except api.ActionError as e:
            self._json({"error": str(e)}, 404)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": f"Something broke on the server: {e}"}, 500)

    def _api(self, name, q):
        routes = {"state": api.state, "rooms": api.rooms, "library": api.library, "money": api.money, "analytics": api.analytics, "finds": api.finds, "schedule": api.schedule,
                  "version": lambda: {"version": api.version()}}
        if name in routes:
            return self._json(routes[name]())
        kind, _, arg = name.partition("/")
        if kind == "campaign" and arg:
            return self._json(api.campaign_detail(arg))
        if kind == "clip" and arg:
            return self._json(api.clip_detail(arg))
        if kind == "memory" and arg:
            return self._json(api.memory(arg))
        self._json({"error": "Not found"}, 404)

    def _static(self, name):
        p = (STATIC / name).resolve()
        if STATIC not in p.parents or not p.is_file():
            return self._json({"error": "Not found"}, 404)
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self._send(200, p.read_bytes(), ctype, {"Cache-Control": "no-cache"})

    def _file(self, p: Path):
        if not servable(p):
            return self._json({"error": "Not found"}, 404)
        p = p.resolve()
        size = p.stat().st_size
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):                 # video seeking
            a, _, b = rng[6:].split(",")[0].partition("-")
            try:
                if a:
                    start, end = int(a), (int(b) if b else size - 1)
                else:
                    start, end = max(0, size - int(b)), size - 1
            except ValueError:
                start, end = 0, size - 1
            end = min(end, size - 1)
            if start > end:
                return self._send(416, b"", ctype, {"Content-Range": f"bytes */{size}"})
        length = end - start + 1
        headers = {"Accept-Ranges": "bytes", "Cache-Control": "no-cache",
                   "Last-Modified": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(p.stat().st_mtime))}
        if rng:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(p, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def _thumb(self, src, t):
        p = (ROOT / src).resolve()
        if not servable(p):
            return self._json({"error": "Not found"}, 404)
        try:
            t = max(0.0, min(float(t), 3600))
        except ValueError:
            t = 1.0
        key = hashlib.sha1(f"{p}|{p.stat().st_mtime}|{t}".encode()).hexdigest()[:20]
        out = THUMBS / f"{key}.jpg"
        if not out.exists():
            THUMBS.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".tmp.jpg")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(p), "-frames:v", "1",
                            "-vf", "scale=360:-2", "-q:v", "4", str(tmp)], capture_output=True)
            if not tmp.exists():         # past the end of a short clip: use the first frame
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-frames:v", "1",
                                "-vf", "scale=360:-2", "-q:v", "4", str(tmp)], capture_output=True)
            if not tmp.exists():
                return self._json({"error": "No thumbnail"}, 404)
            tmp.replace(out)
        self._send(200, out.read_bytes(), "image/jpeg", {"Cache-Control": "max-age=86400"})

    def _stream(self):
        """Server-sent events: push the version whenever the Studio changes, a heartbeat otherwise."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last, beat = None, time.time()
        self.wfile.write(b"retry: 2000\n\n")
        while True:
            try:
                v = api.version()
            except Exception:
                v = last
            if v != last:
                self.wfile.write(f"data: {v}\n\n".encode())
                self.wfile.flush()
                last, beat = v, time.time()
            elif time.time() - beat > 15:
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
                beat = time.time()
            time.sleep(1)

    # ---- POST ----
    def do_POST(self):
        try:
            if urlparse(self.path).path != "/api/action":
                return self._json({"error": "Not found"}, 404)
            if self.headers.get("X-Studio") != "1" or not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._json({"error": "Forbidden"}, 403)
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 256 * 1024:
                return self._json({"error": "Bad request"}, 400)
            body = json.loads(self.rfile.read(n))
            if not isinstance(body, dict):
                return self._json({"error": "Bad request"}, 400)
            self._json(api.act(body))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except api.ActionError as e:
            self._json({"ok": False, "error": str(e)}, 400)
        except (KeyError, ValueError, TypeError) as e:
            self._json({"ok": False, "error": f"That button sent something unexpected ({e})."}, 400)
        except Exception as e:
            traceback.print_exc()
            self._json({"ok": False, "error": f"Something broke on the server: {e}"}, 500)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):
            return                              # the browser closed a connection: normal, not an error
        super().handle_error(request, client_address)


def serve(port=8787):
    os.chdir(ROOT)
    try:
        srv = Server(("127.0.0.1", port), Handler)
    except OSError:
        sys.exit(f"Port {port} is busy: the Studio may already be running at http://127.0.0.1:{port}")
    print(f"Studio cockpit: http://127.0.0.1:{port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
