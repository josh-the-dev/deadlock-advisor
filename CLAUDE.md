# CLAUDE.md

Guidance for Claude (and humans) working on this repo.

## What this is
An external overlay for Deadlock's **Street Brawl** mode. It watches the screen for the item-draft
screen, recognises the hero and the three offered items, and highlights the pick with the best
recent win rate for that hero, or says **REROLL**. Stats come from the public deadlock-api.com.

## Anti-cheat rules (non-negotiable)
Users must never risk a ban. The program stays strictly external and read-only:
- **Allowed:** our own always-on-top, click-through window (game in borderless windowed); desktop
  screen capture (`mss`, DXGI, Windows Graphics Capture); image matching or OCR on those captures;
  global hotkeys registered by our own process.
- **Never:** reading or writing game memory, DLL injection, DirectX/Present hooking, or sending
  clicks or keys to the game. The user always makes the pick themselves.

Reject any feature that needs to cross this line, even if it would be more accurate.

## Domain notes
- Street Brawl items are **drafted from random offers, not bought**. There's no gold cost, so
  don't reason about price or affordability.
- The advisor ranks only the items in the current offer, so most timing biases cancel out.
- Win rates are smoothed with a Bayesian prior toward the hero's baseline (`advisor.PRIOR_WEIGHT`).
  The baseline is an item-weighted average, not the hero's true win rate. That's fine for ranking.
  The reroll threshold (`REROLL_MARGIN`) is a heuristic and needs tuning.
- **Enhanced** offers show an "ENHANCED ⚡" label under the name and a lightning badge in the icon's
  bottom-right corner. The API's `enhanced_items` parameter on `/v1/analytics/item-stats`
  controls how they're counted. They aren't detected or treated separately yet.
- **Rare** offers show a "RARE!" label and an ornate teal ring. This is not the same as tier 4.
- Ring colour = slot: orange = weapon, green = vitality, purple = spirit.

## Data source
Free public API at `https://api.deadlock-api.com` (OpenAPI at `/openapi.json`). Use the API, never
scrape. Be polite: cache everything (`cache/`, stats 6 h, assets 24 h, icons forever).
- `/v1/analytics/item-stats?game_mode=street_brawl&hero_id=N&min_matches=20` returns
  per-item `wins/losses/matches` for the last 30 days.
- `/v1/assets/heroes?only_active=true` gives hero names and `images.top_bar_vertical_image`
  (the portrait on the draft screen).
- `/v1/assets/items/by-type/upgrade` gives item names, slots, tiers and `shop_image` icons.
- Never commit downloaded Valve artwork. It is fetched at runtime into the gitignored `cache/`.

## Architecture
Flat modules, each with one job:

| Module | Role |
|---|---|
| `data.py` | API fetches plus the on-disk cache; name lookup; icon and portrait downloads |
| `advisor.py` | `rate(hero_id, offered_ids)` returns the ranked offer, the baseline and a reroll flag. Pure logic, no I/O apart from `data` |
| `detect.py` | `detect_offer(screen)`: icon matching of the three cards. `detect_hero(screen)`: ORB feature matching of the portrait |
| `overlay.py` | Windows overlay plus the 1 s polling loop and hotkeys. The only module that touches Win32 or Tk |
| `cli.py` | Manual ranking from item names, for debugging the advisor |

Detection details worth knowing:
- All screen coordinates are defined at **2560×1440** (`detect.BASE_W/BASE_H`) and scaled to the
  captured size. Card icon boxes live in `detect.CARD_BOXES`.
- Item icons: crop each card's box, trim a 12% frame, convert to grayscale at 64×64, then take the
  normalised correlation against every cached icon, searching ±32 px around the box. On the
  samples, correct matches score 0.77–0.93 and the runner-up at most 0.55. `overlay.MIN_MATCH`
  (0.65) decides whether the item screen is showing at all.
- Hero portrait: pixel templates failed (different crop, orange background), so we use ORB features
  with a ratio test against alpha-masked portraits. The best hero needs ≥ `MIN_HERO_MATCHES` and
  ≥ `HERO_MARGIN` times the runner-up's count.
- The overlay window uses `WDA_EXCLUDEFROMCAPTURE`, so it never shows up in its own screenshots.
- `samples/others.png` is a near-full 1440p capture. `samples/enhanced.png` is a snip cropped 48 px
  on the left, so don't calibrate absolute coordinates from it.

## Python standards
- **Python ≥ 3.12**, Windows only (Win32 overlay). Config lives in `pyproject.toml`.
- **Dependencies:** keep them minimal (`numpy`, `opencv-python`, `mss`, stdlib otherwise). Justify
  any new runtime dependency. Dev tools go in the `dev` extra.
- **Style:** `ruff format` and `ruff check` must pass (line length 100, rules E/F/W/I/UP/B/SIM).
  Use modern syntax (`X | None`, `list[int]`, f-strings, `pathlib`).
- **Types:** annotate every public function's parameters and return type. Use dataclasses for
  structured results rather than loose tuples where it helps readability.
- **Docstrings:** one line on each module and public function, describing what it returns or does.
  Comments explain *why* (calibration sources, thresholds), not *what*.
- **Constants:** tunable numbers are UPPER_CASE module constants with a comment saying where the
  value came from. No magic numbers inline.
- **Errors:** let unexpected errors raise. Catch only specific, expected failures (e.g. a stale
  asset URL returning 404) and say why in a comment.
- **Output:** library modules don't print. `overlay.py` reports through `logging`, while `cli.py`
  and `detect.py`'s `__main__` may print.
- **Tests:** `pytest` in `tests/`. Detection tests run against `samples/`, and advisor tests use
  fake stats (no network). Tests marked `network` need the API or cached assets. Add a sample
  screenshot plus a test for every new screen layout or detection fix.

## Commands
```
pip install -e ".[dev]"     # runtime + ruff + pytest
python overlay.py           # run the advisor (Ctrl+F8 quits)
python overlay.py --demo samples/others.png
python detect.py samples/others.png
ruff format . && ruff check .
pytest                      # all tests; `pytest -m "not network"` for offline only
```

## Git
- Branch `main`, public at https://github.com/josh-the-dev/deadlock-advisor (MIT).
- Write small, focused commits with imperative messages.
- Commits must **not** include Claude/Anthropic co-author or attribution lines.

## Roadmap
1. Test in-game. Use `cache/last_capture.png` (saved on each new offer) to recalibrate.
2. Verify hero detection across more heroes.
3. Detect enhanced offers and query stats with `enhanced_items` accordingly.
4. Package as a PyInstaller one-file exe for friends, published as a GitHub Release.
   Consider whether OpenCV can be trimmed. ORB is the only hard OpenCV dependency.
5. Possibly use `include_item_ids` or time filters to compare items within the same draft round.
