# Deadlock Street Brawl Item Advisor

An overlay that advises which item to draft, or whether to reroll, in Deadlock's **Street Brawl** mode, based on live win-rate stats.

## Street Brawl context
- Items are **drafted from random offers, not bought**. There's no gold cost, so don't reason about "expensive items" or affordability bias.
- Each draft round offers a few items. The advisor ranks only the items in the current offer, so timing biases mostly cancel out within a round.
- Street Brawl has **enhanced** versions of draft picks. The API's `enhanced_items` parameter on `/v1/analytics/item-stats` controls how they're counted. Still unknown: how the UI shows an enhanced offer (ask the user).

## Anti-cheat rules (non-negotiable)
The user must not get banned. Stay strictly external and read-only:
- OK: a separate always-on-top, click-through window (game in **borderless windowed**), screen capture via Windows Graphics Capture/DXGI/`mss`, icon template matching or OCR, and hotkeys handled by our own process.
- NEVER: reading or writing game memory, DLL injection, DirectX/Present hooking, or sending clicks/keys to the game. The user always clicks the item themselves.

## Data source
Free public API at `https://api.deadlock-api.com` (OpenAPI at `/openapi.json`). No scraping.
- `/v1/analytics/item-stats?game_mode=street_brawl&hero_id=N&min_matches=20` returns `item_id, wins, losses, matches, players, avg_buy_time_s, ...` (default window: last 30 days).
- `/v1/assets/heroes?only_active=true` and `/v1/assets/items/by-type/upgrade` provide names, ids and icon URLs (`shop_image`/`image`), which are useful as icon templates.

## Current files (stdlib only, Python 3.14)
- `data.py` fetches the data and caches it in `cache/`: stats for 6h, assets for 24h. Also has `find_hero`/`find_item` for name lookup, and `icons()`, which downloads item icons once into `cache/icons/<item_id>.<ext>` (about 245 icons, 9 MB; a few stale asset URLs return 404 and are skipped).
- `advisor.py` has `rate(hero_id, offered_ids)`, which returns items sorted by smoothed win rate (a Bayesian prior pulls each item toward the hero's baseline, `PRIOR_WEIGHT=300`), plus the baseline and a reroll flag (`best < baseline - REROLL_MARGIN`).
- `detect.py` (needs `opencv-python` and `numpy`) does `detect_offer(screen_bgr)`, which returns the top matches for the left, centre and right cards. Each card's icon box is scaled from 1440p, the frame is trimmed, and the crop is compared with every cached icon by grayscale correlation (64×64), searching ±32 px around the expected spot. It takes ~0.06 s per screen. On both samples all 6 cards are correct, scoring 0.77–0.93 with a runner-up ≤0.55. A best score below ~0.65 probably means this isn't the item screen (not tested yet). Manual test: `python detect.py samples/others.png`.
- `overlay.py` (needs `mss`) runs with `python overlay.py [--hero X] [--monitor N] [--key F8] [--demo img]`. It's a fullscreen tkinter window: topmost, `-transparentcolor`, click-through (`WS_EX_TRANSPARENT`) and excluded from capture (`WDA_EXCLUDEFROMCAPTURE`). Every 1 s it grabs the primary monitor (the user's 1440p screen is primary, mss #2) and runs `detect_offer`. On a new offer it detects the hero (`detect.detect_hero`, ORB feature matching of the top-centre portrait against `top_bar_vertical_image`; Yamato scored ~120 vs ≤67 for the runner-up; a pixel template match failed) and then draws: a green box on the best card, the win rate above each card, or REROLL. The drawings clear when the screen goes away. F8 forces a refresh, Ctrl+F8 quits. New offers are saved to `cache/last_capture.png`. Not yet tested in-game.
- `cli.py` is a manual test: `python cli.py Paige "Mystic Burst" "Healing Rite" "Extended Magazine"` or `python cli.py Paige --top 10`.

The baseline is an item-weighted average win rate, so it isn't the hero's true win rate. That's fine for relative ranking. The reroll threshold is a rough heuristic and needs tuning.

## Item-choice screen (from `samples/`, user is 2560×1440 borderless)
- `samples/others.png` is roughly a full-screen capture (2559×1439). `samples/enhanced.png` is a cropped snip (2512×1439), so don't calibrate absolute coordinates from it.
- The screen shows "SELECT ITEMS / CHOICE n OF 3", a "Use Re-Roll" button in the centre with "n Re-Roll Remaining", the hero portrait at the top centre and "ROUND n".
- Three circular cards: left (low), centre (high), right (low). Each card has a square icon with the item name beneath it. Approximate icon squares at 1440p, measured in others.png (x1-x2, y1-y2): left 620-804, 763-947; centre 1188-1372, 433-617; right 1756-1940, 763-947 (about 184 px).
- Ring colour = slot: orange = weapon, green = vitality, purple = spirit.
- **Enhanced:** an "ENHANCED ⚡" label under the name, plus a small lightning badge in the icon's bottom-right corner.
- **Rare:** a "RARE!" label above the icon and an ornate teal ring. This is not simply tier 4: Greater Expansion (tier 3) showed as rare.
- In-game icons use the same art as `cache/icons`, but with a tint and a frame, so match in grayscale and/or crop the frame off.
2. Detection: icon matching works (see `detect.py`). Still to do: live screen capture (`mss`), a "not the item screen" score threshold, and detecting enhanced offers. Check the badge region at the icon's bottom-right, or the blue "ENHANCED" text under the name, then pass the result to the API's `enhanced_items`.
3. Hero: auto-detected from the item screen portrait (only verified for Yamato so far).
4. Overlay: auto mode done. Next: test it in-game. Distribution to friends: plan a PyInstaller one-file exe (consider dropping OpenCV for Pillow+numpy to cut its size; ORB is the only hard OpenCV dependency).
5. Possibly: use `include_item_ids`/time filters to compare items within the same draft round more precisely.

## Repo
Public on GitHub at https://github.com/josh-the-dev/deadlock-advisor (MIT, branch `main`). `cache/` is gitignored; `samples/` is committed. Deps are listed in `requirements.txt`.

## Working preferences
- The user wants to **stay within their plan usage and not spend extra credits**. Be frugal: no subagents, minimal web fetches, small focused changes, no exploratory sprawl.
- Keep dependencies minimal and add them only when needed (e.g. `mss`, `opencv-python`, `PyQt6`).
- Git commits must **not** include any Claude/Anthropic co-author or attribution lines.
