"""Rank offered Street Brawl items for a hero and decide whether to reroll."""

from dataclasses import dataclass

import data

# Pseudo-matches pulling each item's win rate toward the hero's baseline,
# so a 6-0 item with 6 matches doesn't outrank a 54% item with 10k matches.
PRIOR_WEIGHT = 300
# Reroll when the best offer is this far below the hero's baseline win rate.
REROLL_MARGIN = 0.01


@dataclass
class Rated:
    item_id: int
    name: str
    score: float      # smoothed win rate
    raw_wr: float | None
    matches: int
    pick_share: float  # matches relative to the hero's most-bought item


def rate(hero_id, offered_ids):
    stats = data.item_stats(hero_id)
    names = data.items()
    total_w = sum(s["wins"] for s in stats.values())
    total_m = sum(s["matches"] for s in stats.values()) or 1
    baseline = total_w / total_m
    top_m = max((s["matches"] for s in stats.values()), default=1)

    rated = []
    for iid in offered_ids:
        s = stats.get(iid)
        w, m = (s["wins"], s["matches"]) if s else (0, 0)
        rated.append(Rated(
            item_id=iid,
            name=names.get(iid, {}).get("name", str(iid)),
            score=(w + PRIOR_WEIGHT * baseline) / (m + PRIOR_WEIGHT),
            raw_wr=w / m if m else None,
            matches=m,
            pick_share=m / top_m,
        ))
    rated.sort(key=lambda r: r.score, reverse=True)
    reroll = bool(rated) and rated[0].score < baseline - REROLL_MARGIN
    return rated, baseline, reroll
