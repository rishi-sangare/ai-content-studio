"""Motion-graphics layer (Remotion, studio/motion): animated captions + title cards + stamps, rendered with alpha.

Recipe: "motion": {"captions": true, "highlight": ["word", …], "titles": [{"text", "start", "end", "kind", "y", "sub"}],
                   "style": {"y": 0.66, "accent": "#FFD23F", "accent2": "#7CFF6B", "size": 104, "maxWords": 3}}
render.py overlays the result over the edit (and skips the old PIL captions). Cached by a hash of the props.
"""
import hashlib
import json
import subprocess
from pathlib import Path

MOTION = Path(__file__).resolve().parents[1] / "motion"
CACHE = Path(__file__).resolve().parents[1] / "data" / "motion_cache"


def overlay(recipe: dict, total: float) -> Path:
    m = recipe["motion"]
    words = []
    if m.get("captions", True) and recipe.get("voiceover_words"):
        hl = {h.lower() for h in m.get("highlight", [])}
        for w in json.loads(Path(recipe["voiceover_words"]).read_text())["words"]:
            clean = w["word"].strip(" ,.?!\"'").lower()
            words.append({"text": w["word"], "start": round(w["start"], 3), "end": round(w["end"], 3),
                          "hl": clean in hl or any(c.isdigit() for c in clean)})
    props = {"fps": 30, "duration": round(total, 3), "words": words, "titles": m.get("titles", []), "style": m.get("style", {})}
    blob = json.dumps(props, sort_keys=True)
    src_sig = "".join(str(p.stat().st_mtime_ns) for p in sorted((MOTION / "src").glob("*")))
    key = hashlib.sha1((blob + src_sig).encode()).hexdigest()[:12]
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / f"overlay_{key}.mov"
    if out.exists():
        return out
    pj = CACHE / f"props_{key}.json"
    pj.write_text(blob)
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "Overlay", str(out), f"--props={pj}", "--codec=prores",
                    "--prores-profile=4444", "--pixel-format=yuva444p10le", "--image-format=png", "--concurrency=8",
                    "--log=error"], cwd=MOTION, check=True)
    return out
