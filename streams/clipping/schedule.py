"""Posting schedule for the clipping accounts: what goes where, when, with every field to paste.

Writes studio/data/schedule.json (the Studio's Schedule page reads it; links / scheduled / submitted ticks Rishi enters there are
kept when this file is re-run) and refreshes each "Ready to post" kit's POST THIS.txt from the same text.
  uv run python streams/clipping/schedule.py          rebuild schedule.json + kits
  uv run python streams/clipping/schedule.py links    today's links grouped by campaign (for Content Rewards)
"""
import json
import shutil
import sys
from datetime import datetime, timedelta
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "studio" / "data" / "schedule.json"
KITS = ROOT / "Ready to post"
C = ROOT / "streams" / "clipping" / "campaigns"
IST, NY = ZoneInfo("Asia/Kolkata"), ZoneInfo("America/New_York")
CC = 'Music: "{}" by Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0'

FG_TAGS = "#forgeguipartner #robloxdev #roblox"          # brief: exactly these, in this order, right after the text
AV_TAGS = "#ad #animalvalley #animals #village #animalidlegame #animalidle"   # brief: #ad first

ACCOUNTS = {
    "rba": {"name": "Roblox But AI", "youtube": "@robloxbutai", "instagram": "@robloxbutai"},
    "coc": {"name": "CookedOrCracked", "youtube": "@CookedOrCracked", "instagram": "@cookedorcrackedclips"},
    "dod": {"name": "Day One Drops", "youtube": "@dayonedrops", "instagram": None},          # no Instagram for Day One Drops (Rishi, 11 Oct)
}
CAMPAIGNS = {
    "forgegui": {"name": "ForgeGUI", "submit": "Content Rewards → ForgeGUI Clipping [Roblox]: submit each link within 30 min of it going live."},
    "animal-valley": {"name": "Animal Valley", "submit": "Content Rewards → Animal Valley: submit within 30 min of going live, "
                      "attach the analytics screenshot; demographics screenshot later (paid only if ≥50% US views)."},
}

YT_SETTINGS = {
    "forgegui": ["Upload the normal .mp4 (not the INSTAGRAM one)", "Paste title, description, tags below",
                 "Audience: No, it's not made for kids", "Show more → Paid promotion: TICK",
                 "Altered or synthetic content: No", "Category: Gaming · Video language: English",
                 "Comments: on · Show like count: on", "Visibility → Schedule → the date and time on this card (your Mac is on IST)",
                 "Copy the video link YouTube shows → paste it here"],
    "animal-valley": ["Upload the normal .mp4 (not the INSTAGRAM one)", "Paste title, description, tags below",
                      "Audience: No, it's not made for kids", "Show more → Paid promotion: TICK",
                      "Altered or synthetic content: No", "Category: Gaming · Video language: English",
                      "Comments: on", "Visibility → Schedule → the date and time on this card",
                      "Copy the video link YouTube shows → paste it here"],
}
IG_SETTINGS = ["Use the INSTAGRAM 8Mbps file (AirDrop it to your phone)", "New Reel → don't add Instagram music, no filters",
               "Cover: the first frame (hook text) — check it isn't cut off in the grid", "Paste the caption exactly",
               "No location, no tags", "Advanced settings → AI label ON · Paid partnership label ON if offered",
               "Share it live at the time on this card (this account can't schedule Reels yet)",
               "After it goes live, pin the comment and copy the reel link → paste it here"]

POSTS = [
    # ---------------- Night of Sat 10 → Sun 11 Oct (IST) ----------------
    dict(id="fg-002@rba", at="2026-10-11 01:00", account="rba", campaign="forgegui", clip="fg-002", version=5,
         kit="15 - TONIGHT 1.00am - ROBLOX BUT AI - fg-002 needle haystack", music="Fluffing a Duck",
         title="Finding 1 needle in 67 MILLION hay in Roblox 😭",
         body="5 prompts in, 3 out of 67,000,000 hay checked… so I pulled out an RPG 💀\n"
              "I used ForgeGUI for this, the AI that builds Roblox games from what you type (forgegui.com)\n\n"
              "keep searching or RPG? 👇",
         tags="roblox, roblox dev, roblox studio, roblox ai, forgegui, needle in a haystack, roblox games, ai game maker, game dev",
         pin="I used ForgeGUI for this 😭 would you keep searching or grab the RPG?"),
    dict(id="fg-004@coc", at="2026-10-11 01:15", account="coc", campaign="forgegui", clip="fg-004", version=4,
         kit="16 - TONIGHT 1.15am - CookedOrCracked - fg-004 Gojo", music="Sneaky Snitch",
         title="I made Gojo in Roblox with AI… nah, I'd win 😭",
         body="Hollow Purple, a whole city to wipe out and Domain Expansion: Infinite Void, all from 4 prompts 💜\n"
              "I used ForgeGUI for this (forgegui.com)\n\nSukuna or Toji next? 👇",
         tags="roblox, gojo, jujutsu kaisen, roblox gojo, hollow purple, infinite void, roblox ai, roblox dev, forgegui, roblox studio",
         pin="I used ForgeGUI for this 😭 Sukuna or Toji next?"),
    dict(id="fg-003@rba", at="2026-10-11 01:45", account="rba", campaign="forgegui", clip="fg-003", version=7,
         kit="17 - TONIGHT 1.45am - ROBLOX BUT AI - fg-003 GTA 6", music="Sneaky Snitch",
         title="Rockstar took too long so I made GTA 6 in Roblox 😭",
         body="A map, weapons, a weapon wheel and a car that actually drives (49 mph 💀), from 4 prompts.\n"
              "I used ForgeGUI for this (forgegui.com)\n\ncops or a heist next? 👇",
         tags="roblox, gta 6, gta vi, roblox gta 6, roblox dev, roblox ai, forgegui, roblox studio, game dev",
         pin="I used ForgeGUI for this 😭 cops or a heist next?"),
    dict(id="fg-007@rba", at="2026-10-11 02:30", account="rba", campaign="forgegui", clip="fg-007", version=4,
         kit="18 - TONIGHT 2.30am - ROBLOX BUT AI - fg-007 steal an egg", music="Fluffing a Duck",
         title="I made Steal an Egg in Roblox… the mom was NOT happy 😭",
         body="Hatching eggs, $25 a second from one chicken, then I stole ONE egg and the mother chicken came for me 💀\n"
              "I used ForgeGUI for this (forgegui.com)\n\nwhat should she do next? 👇",
         tags="roblox, steal an egg, roblox ai, chicken jockey, roblox dev, forgegui, roblox studio, roblox games, ai game maker",
         pin="I used ForgeGUI for this 😭 what should the mother chicken do next?"),
    dict(id="av-006@dod", at="2026-10-11 03:00", account="dod", campaign="animal-valley", clip="av-006", version=3,
         kit="23 - TONIGHT 3.00am - DAY ONE DROPS - av-006 cozy game 3am", music="Monkeys Spinning Monkeys",
         title="I downloaded a cozy game to fall asleep. It's now 6 AM 💀",
         body="11 PM: one tiny bear chopping trees.\n6 AM: a bear army, a windmill, 2,100 acorns and a tractor driving through gold.\n\n"
              "be honest, what time did you finally put your phone down last night? 👇",
         tags="animal valley, animal valley game, cozy games, cozy game, idle game, mobile games, relatable, one more upgrade, cant sleep",
         pin="be honest, what time did you finally put your phone down last night? 👇"),
    dict(id="av-007@dod", at="2026-10-11 03:30", account="dod", campaign="animal-valley", clip="av-007", version=3,
         kit="24 - TONIGHT 3.30am - DAY ONE DROPS - av-007 group project", music="Sneaky Snitch",
         title="every group project has these 3 animals 😭",
         body="The bear does 100% of the work. The panda presents it. The fox shows up at the very end and takes all the acorns.\n"
              "And the ducks? Left on read since Tuesday 💀\n\nwhich one are you? 👇",
         tags="animal valley, group project, relatable, school memes, work memes, cozy game, animal game, idle game, mobile games",
         pin="be honest… bear, panda, fox or duck? 👇"),
    # ---------------- Night of Sun 11 → Mon 12 Oct (IST) ----------------
    dict(id="fg-005@rba", platforms=["instagram"], at="2026-10-12 01:00", account="rba", campaign="forgegui", clip="fg-005", version=5,
         kit="25 - MON 12 1.00am - ROBLOX BUT AI - fg-005 keyboard", music="Monkeys Spinning Monkeys",
         title="I made Keyboard Escape in Roblox with 5 sentences 💀",
         body="Every key presses, lights up, clicks and counts (111 key presses 😭), all from typing 5 sentences.\n"
              "I used ForgeGUI for this (forgegui.com)\n\nwhat game should I make next? 👇",
         tags="roblox, keyboard escape, roblox keyboard, satisfying, roblox ai, roblox dev, forgegui, roblox studio, roblox games",
         pin="I used ForgeGUI for this 😭 what game should I make next?"),
    dict(id="fg-006@coc", platforms=["instagram"], at="2026-10-12 01:15", account="coc", campaign="forgegui", clip="fg-006", version=3,
         kit="26 - MON 12 1.15am - CookedOrCracked - fg-006 backrooms", music="Sneaky Snitch",
         title="Making the Backrooms in Roblox… then the lights went out 💀",
         body="Level 0, faster running, 10x cooler… and then something showed up. 3 prompts.\n"
              "I used ForgeGUI for this (forgegui.com)\n\nwould you stay or leave? 👇",
         tags="roblox, backrooms, roblox backrooms, level 0, roblox horror, roblox ai, roblox dev, forgegui, roblox studio",
         pin="I used ForgeGUI for this 😭 would you stay or leave?"),
    dict(id="fg-009@rba", platforms=["instagram"], at="2026-10-12 01:45", account="rba", campaign="forgegui", clip="fg-009", version=4,
         kit="27 - MON 12 1.45am - ROBLOX BUT AI - fg-009 cheat on a test", music="Sneaky Snitch",
         title="Cheating on a test in Roblox… caught in 4K 😭",
         body="Made a classroom, a test and an iPhone 67 with AI. The teacher had other plans 💀\n"
              "I used ForgeGUI for this (forgegui.com)\n\nwhat class should I make next? 👇",
         tags="roblox, roblox school, cheating on a test, caught in 4k, roblox ai, roblox dev, forgegui, roblox studio, roblox games",
         pin="I used ForgeGUI for this 😭 what class should I make next?"),
    dict(id="fg-008@rba", platforms=["instagram"], at="2026-10-12 02:30", account="rba", campaign="forgegui", clip="fg-008", version=5,
         kit="28 - MON 12 2.30am - ROBLOX BUT AI - fg-008 grow a garden", music="Monkeys Spinning Monkeys",
         title="Can AI make Grow a Garden in 40 seconds? 🌱",
         body="Seed, 5-second timer, harvest with E and a RAINBOW mutation, from 40 seconds of typing 🌈\n"
              "I used ForgeGUI for this (forgegui.com)\n\nwhat mutation should I add next? 👇",
         tags="roblox, grow a garden, rainbow mutation, roblox ai, roblox dev, forgegui, roblox studio, roblox games, ai game maker",
         pin="I used ForgeGUI for this 😭 what mutation should I add next?"),
    dict(id="av-008@dod", at="2026-10-12 03:00", account="dod", campaign="animal-valley", clip="av-008", version=1,
         kit="29 - MON 12 3.00am - DAY ONE DROPS - av-008 nature documentary", music="Fluffing a Duck",
         title="a nature documentary about my phone game 🌿",
         body="The bear has chopped trees for 9 hours straight. The panda keeps the coins. The fox has not left the acorn pile.\n"
              "Nature is healing 🦆\n\nwhich animal are you, honestly? 👇",
         tags="animal valley, nature documentary, cozy game, idle game, animal game, relatable, mobile games, funny animals",
         pin="which animal are you, honestly? 👇"),
    dict(id="av-009@dod", at="2026-10-12 03:30", account="dod", campaign="animal-valley", clip="av-009", version=3,
         kit="30 - MON 12 3.30am - DAY ONE DROPS - av-009 day 1 vs day 30", music="Monkeys Spinning Monkeys",
         title="day 1 vs day 30 in Animal Valley 🌰",
         body="Day 1: 0 acorns. Day 30: 2.51 TRILLION acorns in one tap… and a helicopter 🚁 that escalated quickly\n\n"
              "what day are you on? 👇",
         tags="animal valley, day 1 vs day 30, idle game, cozy game, satisfying, mobile games, progress, animal game",
         pin="what day are you on? 👇"),
]


def texts(p):
    """Every paste-able field, built so each campaign's brief is met word for word."""
    credit = CC.format(p["music"])
    if p["campaign"] == "forgegui":
        caption = f"{p['title']} {FG_TAGS}"                                   # title IS the caption on Shorts
        yt_title, yt_desc = caption, f"{caption}\n\n{p['body']}\n\n{credit}"
        ig = f"{caption}\n\n{p['body']}"
    else:
        yt_title, yt_desc = p["title"], f"{AV_TAGS}\n\n{p['body']}\n\n{credit}"
        ig = f"{p['title']}\n\n{p['body']}\n\n{AV_TAGS}"
    return {"youtube": {"title": yt_title, "description": yt_desc, "tags": p["tags"], "pinned_comment": p["pin"],
                        "settings": YT_SETTINGS[p["campaign"]]},
            "instagram": {"caption": ig, "pinned_comment": p["pin"], "settings": IG_SETTINGS}}


def build():
    old = {e["id"]: e for e in json.loads(OUT.read_text())["posts"]} if OUT.exists() else {}
    out = []
    for p in POSTS:
        at = datetime.strptime(p["at"], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        kit = KITS / p["kit"]
        stem = p["clip"]
        render = C / p["campaign"] / "clips" / p["clip"] / f"{p['clip']}_v{p['version']}.mp4"
        e = {"id": p["id"], "at": p["at"], "at_ny": at.astimezone(NY).strftime("%-I:%M %p"), "night": f"{(at - timedelta(days=1)):%a %d} → {at:%a %d %b}",
             "account": p["account"], **{f"account_{k}": v for k, v in ACCOUNTS[p["account"]].items()},
             "campaign": p["campaign"], "campaign_name": CAMPAIGNS[p["campaign"]]["name"], "submit_rule": CAMPAIGNS[p["campaign"]]["submit"],
             "platforms": p.get("platforms") or (["youtube"] + (["instagram"] if ACCOUNTS[p["account"]]["instagram"] else [])),
             "clip": p["clip"], "version": p["version"], "preview": str(render.relative_to(ROOT)),
             "yt_file": str(kit / f"{stem}.mp4"), "ig_file": str(kit / f"{stem} INSTAGRAM 8Mbps.mp4"), "kit": p["kit"],
             **texts(p)}
        prev = old.get(p["id"], {})                                           # keep what Rishi entered
        for plat in ("youtube", "instagram"):
            for k in ("link", "scheduled", "submitted"):
                if prev.get(plat, {}).get(k):
                    e[plat][k] = prev[plat][k]
        out.append(e)
        write_kit(e, kit, render)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated": datetime.now(IST).strftime("%Y-%m-%d %H:%M"), "posts": out}, indent=1, ensure_ascii=False))
    print(f"schedule.json: {len(out)} posts")


def write_kit(e, kit, render):
    """Folder per post (renamed when its time changes) holding both files + POST THIS.txt with the same text as the Studio."""
    if not kit.exists():                                                     # a time change renames the old folder
        match = [d for d in KITS.iterdir() if d.is_dir() and f" - {e['clip']} " in d.name + " " and "POSTED" not in d.name]
        if match:
            match[0].rename(kit)
        else:
            kit.mkdir(parents=True)
    yt, ig = kit / f"{e['clip']}.mp4", kit / f"{e['clip']} INSTAGRAM 8Mbps.mp4"
    if not yt.exists() or yt.stat().st_size != render.stat().st_size:          # the kit always holds the scheduled version
        shutil.copy(render, yt)
    if not ig.exists() or ig.stat().st_mtime < yt.stat().st_mtime:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(render), "-c:v", "libx264", "-profile:v", "high", "-b:v", "8M",
                        "-maxrate", "8M", "-bufsize", "16M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(ig)], check=True)
    y, i = e["youtube"], e["instagram"]
    parts = [f"{e['account_name']} — {e['campaign_name']} — goes live {e['at']} IST ({e['at_ny']} New York)",
             "Same text is in the Studio → Schedule (copy buttons + a box to paste the links).", "",
             f"YOUTUBE ({e['account_youtube']})", "Title:", y["title"], "", "Description:", y["description"], "", "Tags:", y["tags"], "",
             "Settings:", *[f"- {x}" for x in y["settings"]], "", "Pinned comment:", y["pinned_comment"], ""]
    if "instagram" in e["platforms"]:
        parts += [f"INSTAGRAM ({e['account_instagram']}) — post it live at the time (scheduling isn't on this account yet)",
                  "Caption:", i["caption"], "", "Settings:", *[f"- {x}" for x in i["settings"]], "",
                  "Pinned comment:", i["pinned_comment"], ""]
    parts.append(e["submit_rule"])
    (kit / "POST THIS.txt").write_text("\n".join(parts) + "\n")


def links():
    """Every link Rishi pasted, grouped by campaign then go-live time, ready for Content Rewards."""
    posts = json.loads(OUT.read_text())["posts"]
    for camp in dict.fromkeys(e["campaign_name"] for e in posts):
        print(f"\n== {camp} ==")
        for e in sorted((e for e in posts if e["campaign_name"] == camp), key=lambda e: e["at"]):
            for plat, label in (("youtube", "YouTube"), ("instagram", "Instagram")):
                if plat not in e.get("platforms", ["youtube", "instagram"]):
                    continue
                l = e[plat].get("link")
                tick = "✅ submitted" if e[plat].get("submitted") else ""
                print(f"{e['at'][11:]} IST  {e['account_name']:<16} {label:<9} {e['clip']}  {l or '(no link yet)'}  {tick}")


if __name__ == "__main__":
    links() if sys.argv[1:] == ["links"] else build()
