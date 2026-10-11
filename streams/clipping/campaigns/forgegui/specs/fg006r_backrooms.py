# Winning-format rebuild (11 Oct): opens on the Backrooms' own famous creepypasta line ("If you no-clip out of reality in the
# wrong areas…"), dun-dun-dun on the entities, lights die → SpongeBob "ight imma head out" + "I'm leaving" CTA.
SPEC = {
 "id": "fg-006", "src": "Backrooms RAW.mp4", "music": "sneaky_snitch", "music_db": -10,
 "concept": "Backrooms, winning format",
 "cuts": [("A1", 0.0, 8.0, 1.0), ("A2", 14.3, 25.6, 1.0), ("B", 25.6, 27.2, 1.0)],
 "hold": (26.8, 2.0),
 "lines": [("h1", "If you no-clip out of reality in the wrong areas, you end up in the Backrooms.", 0.0),
           ("v1", "Make me run faster.", ("A1", 5.6)),
           ("v2", "Make everything ten times cooler.", ("A2", 14.6)),
           ("r1", "Wait. Who is that?", ("A2", 17.6)),
           ("r2", "Who turned off the lights?", ("A2", 22.2)),
           ("c1", "Okay, I'm leaving. Forge G-U-I made it way too real.", ("A2", 24.0))],
 "typing": [(("A1", 0.3), 1.2), (("A1", 5.4), 2.2), (("A2", 14.4), 2.0)],
 "sfx": [(("A1", 1.8), "cine_drone", -20), (("A2", 16.4), "cine_shimmer", -15), (("A2", 17.4), "dun_dun_dun", -14, 1.6),
         (("A2", 21.9), "cine_whoosh_down", -12)],
 "fx": [{"at": ("A2", 16.4), "impact": 3},
        {"at": ("A2", 24.2), "gif": "ight_imma_head_out", "gif_s": 2.4, "w": 600, "pos": [0.5, 0.40]}],
 "titles": [("making the backrooms in roblox 💀", 0.0, ("A1", 5.4), "hook", 0.09, 80),
            ("10x COOLER", ("A2", 16.6), ("A2", 17.5), "stamp", 0.36, None)],
 "captions": {"highlight": ["no-clip", "reality", "backrooms", "faster", "ten", "cooler", "who", "lights", "leaving", "forge", "gui"],
              "style": {"y": 0.66, "size": 90}},
 "logo_from": ("A2", 24.0), "pill_until": ("B", 26.4),
}
