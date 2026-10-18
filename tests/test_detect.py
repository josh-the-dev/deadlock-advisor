"""Detection against the committed sample screenshots (needs cached or downloadable assets)."""

from pathlib import Path

import cv2
import numpy as np
import pytest

import data
import detect

SAMPLES = Path(__file__).parent.parent / "samples"
pytestmark = pytest.mark.network


def load(name: str) -> np.ndarray:
    return cv2.imread(str(SAMPLES / name))


def load_enhanced() -> np.ndarray:
    """enhanced.png is a snip cropped 48 px on the left; pad it back to a 1440p frame."""
    snip = load("enhanced.png")
    screen = np.zeros((detect.BASE_H, detect.BASE_W, 3), np.uint8)
    screen[: snip.shape[0], 48 : 48 + snip.shape[1]] = snip
    return screen


@pytest.mark.parametrize(
    ("screen", "expected"),
    [
        (lambda: load("others.png"), ["Arctic Blast", "Echo Shard", "Surge of Power"]),
        (load_enhanced, ["Greater Expansion", "Guardian Ward", "Melee Charge"]),
    ],
)
def test_detect_offer(screen, expected: list[str]) -> None:
    names = data.items()
    offer = detect.detect_offer(screen(), top=2)
    assert [names[card[0][0]]["name"] for card in offer] == expected
    for card in offer:
        assert card[0][1] > 0.7  # confident match
        assert card[1][1] < 0.6  # clear gap to the runner-up


@pytest.mark.parametrize("screen", [lambda: load("others.png"), load_enhanced])
def test_detect_hero(screen) -> None:
    (best, best_n), (_, second_n) = detect.detect_hero(screen(), top=2)
    assert data.heroes()[best] == "Yamato"
    assert best_n >= detect.MIN_HERO_MATCHES
    assert best_n >= 1.5 * second_n


def test_blank_screen_is_not_an_offer() -> None:
    blank = np.full((detect.BASE_H, detect.BASE_W, 3), 40, np.uint8)
    assert all(card[0][1] < 0.65 for card in detect.detect_offer(blank, top=1))
