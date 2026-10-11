"""Read the ForgeGUI prompts typed in a raw clip, with timings: frames at 4 fps → Apple Vision OCR (studio/render/bin/ocr) →
the prompt-box text per frame → one row per prompt (first seen, completed, final text) + other on-screen text (counters, popups).
Usage: uv run python streams/clipping/campaigns/forgegui/prompts.py "<footage file>" [fps]
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path
OCR = Path(__file__).resolve().parents[4] / "studio" / "render" / "bin" / "ocr"
UI = re.compile(r"^(attach|auto|create|code|connect(ed)?|unavailable|other chat|generate( image)?|sign in to send|what do you want to generate\??|"
                r"3d asset|image ready.*|describe what to make.*|annuler|clear|[\W\d_]{0,3})$", re.I)

def frames_text(src, fps=4):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), "-vf", f"fps={fps},scale=1080:-1", f"{td}/f%05d.png"], check=True)
        files = sorted(Path(td).glob("f*.png"))
        out = {}
        for k in range(0, len(files), 40):
            r = subprocess.run([str(OCR), *map(str, files[k:k + 40])], capture_output=True, text=True).stdout
            for line in r.splitlines():
                name, _, txt = line.partition("\t")
                out[(int(name[1:6]) - 1) / fps] = [t.strip() for t in txt.split(" | ") if t.strip()]
        return dict(sorted(out.items()))

def prompts(texts):
    # a prompt = a lowercase-ish sentence that grows frame to frame; take the longest non-UI line that looks typed
    rows, cur = [], None
    for t, lines in texts.items():
        cands = [l for l in lines if not UI.match(l) and len(l) >= 2 and re.search(r"[a-zA-Z]", l)]
        typed = next((l for l in cands if cur and (l.lower().startswith(cur["text"].lower()[:3]) or cur["text"].lower().startswith(l.lower()[:3]))), None)
        if cur and typed:
            if len(typed) >= len(cur["text"]): cur["text"], cur["end"] = typed, t
            continue
        if cur: rows.append(cur); cur = None
        start = next((l for l in cands if len(l) <= 12 and l[0].islower() or l.isupper() and len(l) <= 6), None)
        if start: cur = {"start": t, "end": t, "text": start}
    if cur: rows.append(cur)
    return [r for r in rows if len(r["text"]) >= 6]

if __name__ == "__main__":
    src = Path(sys.argv[1]); fps = float(sys.argv[2]) if len(sys.argv) > 2 else 4
    T = frames_text(src, fps)
    P = prompts(T)
    for r in P: print(f'{r["start"]:6.2f} → {r["end"]:6.2f}  {r["text"]}')
    json.dump({"prompts": P, "frames": {str(k): v for k, v in T.items()}}, open(Path("/tmp") / (src.stem + ".ocr.json"), "w"), indent=0)
