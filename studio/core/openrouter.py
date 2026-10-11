"""OpenRouter access for on-screen demos (e.g. a real Jev answer in an AI-news reel), with a hard spend cap.

Key: Keychain only (`uv run python -m studio.core.openrouter setkey`, hidden prompt; never printed, never in chat or the db).
Cap: Rishi set a full stop at $2 total (5 Oct 2026). Before every call the key's live usage is read from OpenRouter and compared
with the baseline taken on first use (studio/data/openrouter_ledger.json); at or over the cap, nothing is sent.
Every call is logged in the ledger (what was asked, what came back, cost).
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from studio.core.publisher import _kc_get, _kc_set

SVC = "studio.openrouter.apikey"
BASE = "https://openrouter.ai/api/v1"
CAP_USD = 2.00
LEDGER = Path(__file__).resolve().parents[1] / "data" / "openrouter_ledger.json"


def _key() -> str:
    k = _kc_get(SVC, "openrouter")
    if not k:
        sys.exit("No OpenRouter key yet: run `uv run python -m studio.core.openrouter setkey`.")
    return k


def _req(path, body=None, key=None):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Authorization": f"Bearer {key or _key()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as f:
            return json.loads(f.read())
    except urllib.error.HTTPError as e:                     # error bodies never contain the key
        raise RuntimeError(f"OpenRouter {e.code}: {e.read()[:300].decode(errors='replace')}") from None


def usage_usd() -> float:
    return float(_req("/key")["data"]["usage"])


def _ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    d = {"cap_usd": CAP_USD, "baseline_usd": usage_usd(), "calls": []}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, indent=1))
    return d


def spent() -> float:
    d = _ledger()
    return round(usage_usd() - d["baseline_usd"], 6)


def jev(state, questions: dict, model="~typesafe/jev-latest", note="") -> dict:
    """One real Jev call (TypeSafe System One API through OpenRouter). Refuses at/over the cap."""
    d = _ledger()
    s = usage_usd() - d["baseline_usd"]
    if s >= d["cap_usd"]:
        sys.exit(f"Spend cap reached: ${s:.4f} of ${d['cap_usd']:.2f}. Nothing sent.")
    t0 = time.time()
    res = _req("/systemone", {"state": state, "model": model, "questions": questions})
    ms = round((time.time() - t0) * 1000)
    d["calls"].append({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "note": note, "state": state, "questions": questions,
                       "answer": res, "roundtrip_ms": ms})
    LEDGER.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    return res


def set_key():
    import getpass
    key = getpass.getpass("Paste the OpenRouter API key (hidden), then Enter: ").strip()
    if not key.startswith("sk-or-"):
        sys.exit("That doesn't look like an OpenRouter key (they start with 'sk-or-'). Nothing saved.")
    try:
        _req("/key", key=key)
    except Exception:
        sys.exit("OpenRouter didn't accept that key. Nothing saved.")
    _kc_set(SVC, "openrouter", key)
    print("Key checked and saved to the Keychain. Spend cap for Studio demos: $%.2f." % CAP_USD)


if __name__ == "__main__":
    if sys.argv[1:] == ["setkey"]:
        set_key()
    elif sys.argv[1:] == ["spent"]:
        print(f"Spent on Studio demos: ${spent():.4f} of ${_ledger()['cap_usd']:.2f}")
    else:
        print("usage: python -m studio.core.openrouter setkey | spent")
