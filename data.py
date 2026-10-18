"""Fetch and cache Deadlock hero/item assets and Street Brawl item stats from deadlock-api.com."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

API = "https://api.deadlock-api.com"
CACHE_DIR = Path(__file__).parent / "cache"
STATS_TTL_S = 6 * 3600  # stats refresh every 6h; assets only change on patches
ASSETS_TTL_S = 24 * 3600


def _get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "deadlock-advisor/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _cached(name: str, ttl_s: float, fetch: Callable[[], Any]) -> Any:
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{name}.json"
    if path.exists() and time.time() - path.stat().st_mtime < ttl_s:
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def heroes() -> dict[int, str]:
    """{hero_id: name} for active heroes."""
    raw = _cached(
        "heroes", ASSETS_TTL_S, lambda: _get_json("/v1/assets/heroes", {"only_active": "true"})
    )
    return {h["id"]: h["name"] for h in raw}


def items() -> dict[int, dict[str, Any]]:
    """{item_id: {name, slot, tier, cost, image}} for upgrade items."""
    raw = _cached("items", ASSETS_TTL_S, lambda: _get_json("/v1/assets/items/by-type/upgrade"))
    return {
        int(i["id"]): {
            "name": i["name"],
            "slot": i.get("item_slot_type"),
            "tier": i.get("item_tier"),
            "cost": i.get("cost"),
            "image": i.get("shop_image") or i.get("image"),
        }
        for i in raw
    }


def _download_all(urls: dict[int, str | None], subdir: str) -> dict[int, Path]:
    """Download {key: url} once into cache/<subdir>/<key>.<ext>; return {key: Path}."""
    out_dir = CACHE_DIR / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, url in urls.items():
        if not url:
            continue
        ext = Path(urllib.parse.urlparse(url).path).suffix or ".png"
        path = out_dir / f"{key}{ext}"
        if not path.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "deadlock-advisor/0.1"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    path.write_bytes(resp.read())
            except urllib.error.HTTPError:
                continue  # some asset URLs are stale (404); skip them
        paths[key] = path
    return paths


def icons() -> dict[int, Path]:
    """Item icons in cache/icons/<item_id>.<ext>; returns {item_id: Path}."""
    return _download_all({iid: it["image"] for iid, it in items().items()}, "icons")


def hero_portraits() -> dict[int, Path]:
    """Top-bar hero portraits (as on the item-choice screen) in cache/heroes/; {hero_id: Path}."""
    raw = _cached(
        "heroes", ASSETS_TTL_S, lambda: _get_json("/v1/assets/heroes", {"only_active": "true"})
    )
    return _download_all(
        {h["id"]: (h.get("images") or {}).get("top_bar_vertical_image") for h in raw}, "heroes"
    )


def item_stats(
    hero_id: int, game_mode: str = "street_brawl", min_matches: int = 20
) -> dict[int, dict[str, Any]]:
    """Per-item win/match counts for one hero in the given game mode (last 30 days)."""
    params = {"game_mode": game_mode, "hero_id": hero_id, "min_matches": min_matches}
    raw = _cached(
        f"stats_{game_mode}_{hero_id}",
        STATS_TTL_S,
        lambda: _get_json("/v1/analytics/item-stats", params),
    )
    return {s["item_id"]: s for s in raw}


def find_hero(name: str) -> int:
    """Hero id by exact or unique partial name (case-insensitive)."""
    name = name.lower().strip()
    for hid, hname in heroes().items():
        if hname.lower() == name:
            return hid
    matches = [hid for hid, hname in heroes().items() if name in hname.lower()]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f"Unknown or ambiguous hero: {name!r}")


def find_item(name: str) -> int:
    """Item id by exact or unique partial name (case-insensitive)."""
    name = name.lower().strip()
    all_items = items()
    for iid, it in all_items.items():
        if it["name"].lower() == name:
            return iid
    matches = [iid for iid, it in all_items.items() if name in it["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f"Unknown or ambiguous item: {name!r}")
