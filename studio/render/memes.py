"""Meme GIF library (Tenor, public pages, no API key): search → contact sheet to pick from → download as mp4/gif into
studio/render/assets/memes/<name>.<ext>. Renders use them as short "gif" events (a 1–2 s cut-in, no original audio).
  uv run python -m studio.render.memes search "nah id win" [--stickers]   → prints ids + writes a numbered contact sheet
  uv run python -m studio.render.memes get <tenor_id> <name> [--sticker]   → assets/memes/<name>.mp4 (or .gif for stickers: alpha)
"""
import io, re, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw
OUT = Path(__file__).resolve().parent / "assets" / "memes"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"}
SHEETS = Path("/tmp")

def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()

def search(q, stickers=False, n=24, sheet_dir=SHEETS):
    slug = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")
    html = _get(f"https://tenor.com/search/{slug}-{'stickers' if stickers else 'gifs'}").decode("utf8", "ignore")
    seen, hits = set(), []
    for m in re.finditer(r"https://media\.tenor\.com/([A-Za-z0-9_-]{11})AAAA[MN]/([^\"?]+?)\.(gif|webp|png)", html):
        tid, name = m.group(1), urllib.parse.unquote(m.group(2))
        if tid not in seen:
            seen.add(tid); hits.append((tid, name, m.group(0)))
    hits = hits[:n]
    tiles = []
    for k, (tid, name, url) in enumerate(hits):
        try:
            im = Image.open(io.BytesIO(_get(url))); im.seek(0); im = im.convert("RGBA")
        except Exception:
            continue
        im.thumbnail((220, 220)); bg = Image.new("RGB", (230, 250), (40, 40, 40) if not stickers else (90, 140, 90))
        bg.paste(im, ((230 - im.width) // 2, 24), im)
        ImageDraw.Draw(bg).text((4, 4), f"{k} {name[:28]}", fill=(255, 255, 0)); tiles.append(bg)
        print(f"{k:2d} {tid} {name}")
    if tiles:
        cols = 6; rows = (len(tiles) + cols - 1) // cols
        sh = Image.new("RGB", (cols * 230, rows * 250))
        for i, t in enumerate(tiles): sh.paste(t, ((i % cols) * 230, (i // cols) * 250))
        p = Path(sheet_dir) / f"memes_{slug}{'_st' if stickers else ''}.jpg"; sh.save(p, quality=85); print("sheet:", p)
    return hits

def get(tid, name, sticker=False):
    OUT.mkdir(parents=True, exist_ok=True)
    if sticker:                                    # stickers keep transparency: full-size gif
        p = OUT / f"{name}.gif"; p.write_bytes(_get(f"https://media.tenor.com/{tid}AAAAi/x.gif") if False else _get(f"https://media.tenor.com/{tid}AAAAC/x.gif"))
    else:
        p = OUT / f"{name}.mp4"; p.write_bytes(_get(f"https://media.tenor.com/{tid}AAAPo/x.mp4"))
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True).stdout.split()
    print(p, d, f"{p.stat().st_size // 1024} KB")
    return p

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "search": search(a[1], "--stickers" in a, sheet_dir=a[a.index("--dir") + 1] if "--dir" in a else SHEETS)
    elif a[0] == "get": get(a[1], a[2], "--sticker" in a)
