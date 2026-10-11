"""Make a ready-to-post kit: uv run python streams/clipping/campaigns/forgegui/make_kit.py <clip-id> <version> "<folder name>" "<account>" "<slot>"
Copies the render, makes the Instagram 8 Mbps copy, writes POST THIS.txt from KITS below."""
import json, shutil, subprocess, sys
from pathlib import Path
FG = Path(__file__).resolve().parent; ROOT = FG.parents[3]
TAGS = "#forgeguipartner #robloxdev #roblox"
KITS = {
 "fg-002": ("Making Needle In A Haystack in Roblox 💀", "67 million hay and he still didn't find it 😭 I used ForgeGUI for this", "I used ForgeGUI for this 💀 would you have used the RPG too?"),
 "fg-003": ("Making GTA 6 in Roblox before GTA 6 😭", "weapons, a car and it actually drives 💀 I used ForgeGUI for this", "I used ForgeGUI for this 😭 what should I add next?"),
 "fg-004": ("I became Gojo in Roblox using AI 😭", "nah, I'd win 💜 hollow purple, a whole city and infinite void. I used ForgeGUI for this", "I used ForgeGUI for this 😭 Sukuna next?"),
 "fg-005": ("I made Keyboard Escape in Roblox 💀", "every key presses, lights up and counts 😭 I used ForgeGUI for this", "I used ForgeGUI for this 😭 what game should I make next?"),
 "fg-006": ("Making the Backrooms in Roblox 💀", "it was fine until the lights went off 😭 I used ForgeGUI for this", "I used ForgeGUI for this 😭 should I add an entity next?"),
 "fg-007": ("I made Steal an Egg in Roblox using AI 😭", "the mother chicken went full chicken jockey 💀 I used ForgeGUI for this", "I used ForgeGUI for this 😭 what should the chicken do next?"),
 "fg-008": ("Can AI make Grow a Garden in 40 seconds? 🌱", "seed, timer, harvest and a rainbow mutation 🌈 I used ForgeGUI for this", "I used ForgeGUI for this 😭 what mutation should I add next?"),
 "fg-009": ("Cheating on a test in Roblox using AI 😭", "iPhone 67 was a mistake 💀 I used ForgeGUI for this", "I used ForgeGUI for this 😭 what class should I make next?"),
}
cid, v, folder, account, slot = sys.argv[1:6]
title, desc, pin = KITS[cid]
src = FG / "clips" / cid / f"{cid}_v{v}.mp4"
rec = json.loads((FG / "clips" / cid / f"v{v}.json").read_text())
out = ROOT / "Ready to post" / folder; out.mkdir(parents=True, exist_ok=True)
shutil.copy(src, out / f"{cid}.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c:v", "libx264", "-profile:v", "high", "-b:v", "8M", "-maxrate", "8M", "-bufsize", "16M",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out / f"{cid} INSTAGRAM 8Mbps.mp4")], check=True)
(out / "POST THIS.txt").write_text(f"""FORGEGUI campaign — {account}. Post at {slot}.
MAX 3 posts per day on this account. Likes, comments and shares must be ON. Never post this same file on another account.

YOUTUBE
Title (the disclosure must come right after the text, in this exact order):
{title} {TAGS}

Description:
{title} {TAGS}

{desc}

{rec["music"]["credit"]}

Settings: Made for kids = NO · Altered/AI content = NO · Paid promotion = TICK (it's a sponsored campaign) · Category Gaming · English

Pin this comment right after it goes live:
{pin}

INSTAGRAM (8Mbps file) — caption, exactly in this order:
{title} {TAGS}

{desc}
(AI label ON)

Then submit the link on Content Rewards (ForgeGUI campaign) WITHIN 30 MINUTES and paste it to Claude.
""")
print("kit →", out)
