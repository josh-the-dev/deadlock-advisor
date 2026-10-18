"""Manual test harness until screen detection exists.

python cli.py Paige "Extended Magazine" "Mystic Burst" "Healing Rite"
python cli.py Paige --top 15
"""

import argparse

import advisor
import data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("hero")
    ap.add_argument("offered", nargs="*", help="item names currently offered")
    ap.add_argument("--top", type=int, help="show the hero's N best items instead")
    args = ap.parse_args()

    hero_id = data.find_hero(args.hero)
    ids = list(data.item_stats(hero_id)) if args.top else [data.find_item(n) for n in args.offered]

    advice = advisor.rate(hero_id, ids)
    rated, baseline, reroll = advice.ranked, advice.baseline, advice.reroll
    if args.top:
        rated = rated[: args.top]

    print(f"{data.heroes()[hero_id]} - Street Brawl baseline WR {baseline:.1%}\n")
    for i, r in enumerate(rated):
        raw = f"{r.raw_wr:.1%}" if r.raw_wr is not None else "  n/a"
        mark = "->" if i == 0 and not args.top else "  "
        print(
            f"{mark} {r.name:<28} score {r.score:.1%}  raw {raw}  "
            f"n={r.matches:<6} pick {r.pick_share:.0%}"
        )
    if not args.top:
        print("\nAdvice:", "REROLL" if reroll else f"take {rated[0].name}")


if __name__ == "__main__":
    main()
