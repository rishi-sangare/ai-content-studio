# Winning-format rebuild (10 Oct): rant hook, JJK meme beats in context, impact frames, coloured captions, "honored one" CTA.
# "Would you lose? / Nah, I'd win" = Gojo's overconfident line (JJK ch. 221); "Stand proud, you're strong" = Sukuna's line to a beaten
# foe (said here to the dummies); "Throughout heaven and earth, I alone am the honored one" = Gojo's awakening line → CTA.
SPEC = {
 "id": "fg-004", "src": "gojo saturo raw.mp4", "music": "sneaky_snitch", "music_db": -9,
 "concept": "Gojo in Roblox, winning format: cooked hook → Hollow Purple (GIF) → 'would you lose?' 'Nah, I'd win' → blast with impact "
            "frames → 'Stand proud, you're strong' to the dummies → Domain Expansion: Infinite Void (GIF) → honored-one CTA",
 "cuts": [("A", 0.8, 11.2, 1.0), ("B", 12.5, 16.2, 1.5), ("F1", 16.6, 1.7, 0), ("C", 16.6, 21.5, 1.0),
          ("D1", 27.3, 31.6, 1.3), ("D2", 31.6, 37.2, 1.0)],
 "hold": (36.6, 1.6),
 "lines": [("h1", "Roblox is so cooked. You can just type Gojo into Roblox now.", 0.0),
           ("v1", "Give me Gojo's Hollow Purple.", ("A", 5.2)),
           ("r1", "That's actually Hollow Purple.", ("A", 9.05)),
           ("v2", "Spawn a city. And some dummies.", ("B", 12.6)),
           ("r2", "Nah. I'd win.", ("F1", 16.6 + 0.55)),
           ("r3", "Stand proud. You were strong.", ("C", 19.2)),
           ("v3", "Domain Expansion.", ("D1", 27.8)),
           ("r4", "Infinite Void.", ("D2", 31.9)),
           ("c1", "Throughout heaven and earth, Forge G-U-I alone is the honored one.", ("D2", 33.5))],
 "typing": [(("A", 3.0), 2.4), (("B", 12.5), 1.6), (("D1", 27.5), 2.6)],
 "sfx": [(("A", 7.6), "cine_shimmer", -13), (("A", 7.65), "anime_wow", -15),
         (("F1", 16.6), "dun_dun_dun", -15, 1.2),
         (("C", 17.18), "cine_boom", -8), (("C", 17.2), "vine_boom", -12), (("C", 18.3), "cine_whoosh", -15),
         (("D2", 31.6), "cine_swell_short", -12), (("D2", 31.65), "cine_boom", -11)],
 "fx": [{"at": ("A", 7.55), "gif": "gojo_hollow_purple", "gif_s": 1.45, "w": 800, "pos": [0.5, 0.40]},
        {"at": ("F1", 16.6 + 0.45), "gif": "nah_id_win_panel", "gif_s": 1.2, "w": 520, "pos": [0.5, 0.42]},
        {"at": ("C", 17.18), "impact": 5}, {"at": ("C", 17.18), "shake": 0.45},
        {"at": ("D2", 31.65), "impact": 3}, {"at": ("D2", 31.7), "gif": "gojo_infinite_void", "gif_s": 1.5, "w": 820, "pos": [0.5, 0.40]}],
 "titles": [("I became Gojo in Roblox using AI 😭", 0.0, ("A", 5.2), "hook", 0.09, 80),
            ("would you lose? 🤨", ("F1", 16.6), ("F1", 16.6 + 1.65), "stamp", 0.17, None)],
 "captions": {"highlight": ["cooked", "gojo", "hollow", "purple", "win", "strong", "domain", "expansion", "infinite", "void",
                            "honored", "forge", "g-u-i", "city", "dummies"], "style": {"y": 0.64, "size": 92}},
 "logo_from": ("D2", 33.5),
}
