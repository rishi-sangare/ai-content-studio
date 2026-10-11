"""Campaign scoring for paid clip campaigns (Content Rewards / Vyro).

Claude extracts a brief into the JSON shape below; everything here is deterministic so a
verdict can always be explained. Rules come from our research (docs/clipping-field-guide.html,
streams/clipping/research/youtube-notes.md).

Brief JSON fields (unknown -> null):
  id, name, owner, owner_verified, url, brief_url, category,
  platforms [youtube|instagram|tiktok|x|facebook],
  cpm_usd, min_payout_usd, max_payout_usd,
  budget_total_usd, budget_remaining_usd, budget_refills (e.g. "weekly"),
  approval_rate (0-1), participants, top_earner_usd,
  tier1_min_pct, dedicated_page, ai_content_allowed, footage_provided,
  likes_per_1k_min, submit_within_min, gambling,
  requirements [strings, verbatim-ish rules from the brief]
"""
from dataclasses import dataclass, field

# Which platforms we can post on right now. Instagram joins in week 2.
ACTIVE_PLATFORMS = {"youtube", "instagram"}
# A brand-new account posting from India: tier-1 shares above this are not reachable yet.
MAX_TIER1_PCT = 50


@dataclass
class Factor:
    name: str
    points: float
    max_points: float
    why: str


@dataclass
class Verdict:
    verdict: str                 # TAKE | MAYBE | SKIP
    score: int                   # 0-100
    blocks: list = field(default_factory=list)
    factors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _lerp(x, lo, hi):
    """Map x from [lo, hi] to [0, 1], clamped. Works for reversed ranges."""
    if x is None:
        return None
    t = (x - lo) / (hi - lo)
    return max(0.0, min(1.0, t))


def score(b: dict) -> Verdict:
    blocks, warnings, factors = [], [], []
    platforms = {p.lower() for p in (b.get("platforms") or [])}

    # --- hard blocks: any one of these means SKIP, no matter the pay ---
    if b.get("gambling"):
        blocks.append("Gambling/casino promotion - illegal for you under India's Online Gaming Act 2025.")
    if not platforms & ACTIVE_PLATFORMS:
        blocks.append(f"Doesn't accept a platform we post on yet ({', '.join(sorted(ACTIVE_PLATFORMS))}).")
    if b.get("footage_provided") is False:
        blocks.append("No footage supplied - we only run campaigns that provide their own clips.")
    if b.get("dedicated_page"):
        blocks.append("Requires a dedicated page for this campaign; we run one themed channel for now.")
    if (b.get("tier1_min_pct") or 0) > MAX_TIER1_PCT:
        blocks.append(f"Needs {b['tier1_min_pct']}% tier-1 viewers - not reachable on a new India-based account yet.")
    if b.get("owner_verified") is False:
        blocks.append("Campaign owner isn't verified - creators report unverified owners not paying.")
    if b.get("approval_rate") is not None and b["approval_rate"] < 0.40:
        blocks.append(f"Approval rate {b['approval_rate']:.0%} - most clips get rejected.")
    total, remaining = b.get("budget_total_usd"), b.get("budget_remaining_usd")
    if total and remaining is not None and remaining / total < 0.15 and not b.get("budget_refills"):
        blocks.append(f"Only {remaining / total:.0%} of budget left - likely to run out before a new clip pays.")

    # --- weighted factors (0-100 total) ---
    cpm = b.get("cpm_usd")
    def add(name, frac, max_pts, why):
        if frac is None:
            factors.append(Factor(name, max_pts * 0.5, max_pts, why + " (unknown - counted as average)"))
        else:
            factors.append(Factor(name, round(max_pts * frac, 1), max_pts, why))

    add("Pay rate", _lerp(cpm, 0.5, 3.0), 20,
        f"${cpm}/1K views" if cpm is not None else "CPM")

    min_views = None
    if cpm and b.get("min_payout_usd") is not None:
        min_views = b["min_payout_usd"] / cpm * 1000
    add("Views needed before any pay", _lerp(min_views, 15000, 2000), 15,
        f"~{min_views:,.0f} views to reach the minimum payout" if min_views is not None else "Minimum views")

    ar = b.get("approval_rate")
    add("Approval rate", _lerp(ar, 0.40, 0.80), 20,
        f"{ar:.0%} of submissions approved" if ar is not None else "Approval rate")

    runway = remaining / total if (total and remaining is not None) else None
    if b.get("budget_refills"):
        runway = max(runway or 0, 0.8)
    add("Budget runway", runway, 15,
        (f"{runway:.0%} of budget left" + (f", refills {b['budget_refills']}" if b.get('budget_refills') else ""))
        if runway is not None else "Budget left")

    per_head = remaining / b["participants"] if (remaining and b.get("participants")) else None
    add("Competition", _lerp(per_head, 5, 50), 10,
        f"${per_head:,.0f} of budget left per clipper ({b['participants']} clippers)" if per_head is not None else "Competition")

    t1 = b.get("tier1_min_pct")
    add("Tier-1 requirement", _lerp(t1, 50, 0) if t1 is not None else None, 15,
        f"needs {t1}% US/UK/CA/AU viewers" if t1 is not None else "Tier-1 requirement")

    fp = b.get("footage_provided")
    add("Footage provided", None if fp is None else (1.0 if fp else 0.0), 5,
        "campaign supplies licensed footage" if fp else "no footage - copyright risk if we source it")

    # --- warnings: not blockers, but things the checklist must enforce ---
    if b.get("likes_per_1k_min"):
        warnings.append(f"Engagement rule: at least {b['likes_per_1k_min']} likes per 1,000 views or the clip is rejected.")
    if b.get("submit_within_min"):
        warnings.append(f"Submit within {b['submit_within_min']} minutes of posting.")
    if b.get("ai_content_allowed") is False:
        warnings.append("AI-generated content is banned - only edit the supplied footage.")
    if b.get("top_earner_usd") is not None and b["top_earner_usd"] < 200:
        warnings.append(f"Top earner so far made only ${b['top_earner_usd']:,.0f} - low ceiling.")

    total_score = int(round(sum(f.points for f in factors)))
    if blocks:
        v = "SKIP"
    elif total_score >= 65:
        v = "TAKE"
    elif total_score >= 45:
        v = "MAYBE"
    else:
        v = "SKIP"
    return Verdict(v, total_score, blocks, factors, warnings)


def checklist(b: dict) -> list:
    """Rules every clip for this campaign must pass. 'when' = render | post | after."""
    items = [{"rule": r, "when": "render"} for r in (b.get("requirements") or [])]
    std = [
        ("#ad disclosure visible before the 'more' cutoff (caption start)", "post"),
        ("Likes visible on the post", "post"),
        ("Keep the post live at least 30 days", "after"),
        ("Screenshot analytics (views, audience countries) at 24h, 72h and 7 days", "after"),
    ]
    if b.get("submit_within_min"):
        std.append((f"Submit the link within {b['submit_within_min']} minutes of posting", "after"))
    if b.get("likes_per_1k_min"):
        std.append((f"Engagement: >= {b['likes_per_1k_min']} likes per 1,000 views", "after"))
    if b.get("tier1_min_pct"):
        std.append((f"Audience: >= {b['tier1_min_pct']}% tier-1 viewers (attach analytics)", "after"))
    return items + [{"rule": r, "when": w} for r, w in std]


def format_card(b: dict, v: Verdict) -> str:
    icon = {"TAKE": "✅", "MAYBE": "🤔", "SKIP": "⛔"}[v.verdict]
    lines = [f"{icon} {v.verdict}  {b.get('name')}  — score {v.score}/100"]
    for blk in v.blocks:
        lines.append(f"   ⛔ {blk}")
    for f in v.factors:
        lines.append(f"   {f.points:>5.1f}/{f.max_points:<3} {f.name}: {f.why}")
    for w in v.warnings:
        lines.append(f"   ⚠️  {w}")
    return "\n".join(lines)
