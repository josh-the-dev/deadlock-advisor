"""Advisor ranking and reroll logic, using fake stats (no network)."""

import pytest

import advisor
import data

ITEMS = {1: {"name": "Good"}, 2: {"name": "Average"}, 3: {"name": "Bad"}, 4: {"name": "Lucky"}}


@pytest.fixture
def fake_stats(monkeypatch: pytest.MonkeyPatch) -> dict[int, dict[str, int]]:
    stats = {
        1: {"wins": 5500, "matches": 10000},  # 55%
        2: {"wins": 5000, "matches": 10000},  # 50%
        3: {"wins": 4000, "matches": 10000},  # 40%
        4: {"wins": 6, "matches": 6},  # 100% on a tiny sample
    }
    monkeypatch.setattr(data, "item_stats", lambda hero_id: stats)
    monkeypatch.setattr(data, "items", lambda: ITEMS)
    return stats


def test_ranks_by_smoothed_win_rate(fake_stats: dict) -> None:
    advice = advisor.rate(0, [3, 1, 2])
    assert [r.name for r in advice.ranked] == ["Good", "Average", "Bad"]
    assert not advice.reroll


def test_prior_stops_tiny_samples_winning(fake_stats: dict) -> None:
    advice = advisor.rate(0, [4, 1])
    assert advice.ranked[0].name == "Good"
    assert advice.ranked[1].raw_wr == 1.0


def test_reroll_when_every_offer_is_below_baseline(fake_stats: dict) -> None:
    assert advisor.rate(0, [3]).reroll


def test_unknown_item_falls_back_to_baseline(fake_stats: dict) -> None:
    advice = advisor.rate(0, [99])
    assert advice.ranked[0].matches == 0
    assert advice.ranked[0].score == pytest.approx(advice.baseline)
