# Research and lessons

## Finding the right campaign

Three passes over a public campaign board (signed out, read only): every campaign with budget, pay per 1K views per platform,
minimum and maximum payout per post, creators joined and budget burn since the previous day. Then the "Newest" sort, then every
filter on the board. Scoring weighed:

1. proven view ceiling
2. money really left and burn rate
3. pay rate and **minimum payout** (a $20 minimum means ~10K views before a post earns anything)
4. competition (budget per creator)
5. newness
6. fit: footage supplied, faceless/AI allowed, audience rules
7. how fast a new account in that niche gets views

The finding that changed the strategy: **nearly every well-paying campaign requires 40–50% of views from the US or Tier-1
countries.** Pulling our own channels' country split through the YouTube Analytics API showed 5–22%. Every later decision
(account per campaign, topics, posting at US evening, no Indian engagement early) follows from that number.

## How podcast clips are really edited

Four parallel studies (YouTube frames, Instagram screenshots and audio labels, clipping psychology, the creator's own catalogue):

- **Effects don't decide reach.** The same template got 57K and 2.3M views. Huberman's 4.2M Shorts have no captions. Low performers had *more* cuts per 10 s than 1M+ clips.
- **What decides reach:**
  1. the moment and its first spoken line (it must make sense to a stranger)
  2. the topic and angle (named effects, X-vs-Y, red flags, tests and rules; "Why…" titles do worst, at 0.86× the channel median)
  3. hook text on frame 1 (within one account, reels without it got 2–21K vs 172K–28.8M with it)
  4. a hard cut right after the payoff
- **Music is rare.** 15 of 17 top Reels used original audio, and Diary of a CEO clips use no music and no sound effects.
- **Shares drive Instagram.** Direct-message shares to non-followers are a top ranking signal. So the test for a moment is "would someone send this to a specific person?"
- **Don't copy the client's own clips.** The creator's team had already posted one of our picks. Instagram favours the original over near-copies.

Resulting spec:
- full-screen face, host on screen at 0 s
- hook headline for 0–3.5 s only
- clean white captions, 1–3 words, one highlight colour
- a visual change every 3–4 s (real camera cuts, or punch-ins)
- 30–55 s, cut ≤0.5 s after the last word
- original audio, at most one whoosh, no B-roll or logos

## Things that went wrong, and what changed

| What happened | Cause | Fix |
|---|---|---|
| Brand name said "gooey" | TTS reading "GUI" as a word | Write `G-U-I`; check accepts it; captions normalised |
| Meme words cut off mid-word | Guessed trim points on meme sounds | Transcribe each meme clip; size the pause to the sound |
| "THAN BED" in captions | Transcriber homophone | `fix_words` map per clip |
| A freeze frame rendered black | 1/30 s window had no frame in a 24 fps source | Freeze takes the first real frame in a 0.1 s window |
| Impact frames never appeared | Each window was narrower than one frame | Snap windows to the frame grid |
| A reminder loop never fired | `pgrep` matched its own command line | Wait on a PID instead |
| Reminders held back all night | They only fire while the agent is idle | Keep posting windows free of long tasks; long work goes to background agents |
| A new YouTube channel was removed for spam | Renamed channel + 3 sponsored AI-narrated videos with an external link on day one; footage shared by thousands of clippers | Appeal; Instagram-only while pending; new channels ramp 1/day with no links in week one |
| Clips felt "plain" | Faithful but personality-free edits | The winning-format rebuild for memes-allowed campaigns; a research-backed clean spec for podcasts |

## What I'd tell someone building this

- Make the agent **verify by a different sense** than the one it used to make the thing: transcribe the audio it generated, and look at frames of the video it cut.
- Keep **one source of truth** (a recipe, a schedule file) and render everything else from it.
- Write the rules down once (`CLAUDE.md`, memory) and let feedback flow into them.
- Treat platform rules and audience data as the product's real constraints. They mattered more than any editing trick.
