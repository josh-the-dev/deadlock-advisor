"""Identify the three offered items on the Street Brawl item-choice screen by matching icons."""

import sys

import cv2
import numpy as np

import data

Match = tuple[int, float]  # (id, score), higher is better
Box = tuple[int, int, int, int]  # x1, y1, x2, y2 at 1440p

BASE_W, BASE_H = 2560, 1440
# Icon squares (x1, y1, x2, y2) at 1440p: left, centre, right card
CARD_BOXES: list[Box] = [(620, 763, 804, 947), (1188, 433, 1372, 617), (1756, 763, 1940, 947)]
INSET = 0.12  # trim the in-game frame and the enhanced badge's edge
SIZE = 64
JITTER = 32  # search +/- this many px (at 1440p) around each box
STEP = 8


def _prep(img: np.ndarray) -> np.ndarray:
    """Grayscale, resize, and normalise an icon image for comparison."""
    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3:4] / 255.0
        img = (img[:, :, :3] * alpha).astype(np.uint8)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.resize(img, (SIZE, SIZE), interpolation=cv2.INTER_AREA).astype(np.float32)
    img -= img.mean()
    return img / (np.linalg.norm(img) + 1e-6)


def _inset(img: np.ndarray, frac: float) -> np.ndarray:
    h, w = img.shape[:2]
    dy, dx = int(h * frac), int(w * frac)
    return img[dy : h - dy, dx : w - dx]


_templates = None


def templates() -> tuple[list[int], np.ndarray]:
    """(item_ids, matrix) with one flattened, normalised icon per row."""
    global _templates
    if _templates is None:
        ids, rows = [], []
        for iid, path in data.icons().items():
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is not None:
                ids.append(iid)
                rows.append(_prep(_inset(img, INSET)).ravel())
        _templates = (ids, np.stack(rows))
    return _templates


def match_icon(crop: np.ndarray, top: int = 3) -> list[Match]:
    """[(item_id, score), ...] best first; score is a correlation in [-1, 1]."""
    ids, mat = templates()
    scores = mat @ _prep(_inset(crop, INSET)).ravel()
    return [(ids[i], float(scores[i])) for i in np.argsort(-scores)[:top]]


def match_card(screen: np.ndarray, box: Box, top: int = 3) -> list[Match]:
    """Best match_icon result over small shifts of the expected icon box."""
    sx, sy = screen.shape[1] / BASE_W, screen.shape[0] / BASE_H
    best = None
    for dy in range(-JITTER, JITTER + 1, STEP):
        for dx in range(-JITTER, JITTER + 1, STEP):
            x1, y1, x2, y2 = box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy
            crop = screen[max(0, int(y1 * sy)) : int(y2 * sy), max(0, int(x1 * sx)) : int(x2 * sx)]
            if crop.size == 0:
                continue
            result = match_icon(crop, top)
            if best is None or result[0][1] > best[0][1]:
                best = result
    return best


# Hero portrait (top centre) region at 1440p. Its scale/crop differs from the downloaded
# art and the background is orange vs transparent, so match ORB features rather than pixels.
PORTRAIT_BOX: Box = (1020, 0, 1150, 140)
MIN_HERO_MATCHES = 40  # Yamato scored 116-129 on the samples, the runner-up at most 67

_orb = cv2.ORB_create(500, edgeThreshold=8, patchSize=15)
_matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
_hero_templates = None


def hero_templates() -> dict[int, np.ndarray]:
    """{hero_id: ORB descriptors} of the downloaded top-bar portraits (alpha-masked)."""
    global _hero_templates
    if _hero_templates is None:
        _hero_templates = {}
        for hid, path in data.hero_portraits().items():
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is None or img.ndim != 3 or img.shape[2] != 4:
                continue
            mask = (img[:, :, 3] > 128).astype(np.uint8) * 255
            _, desc = _orb.detectAndCompute(cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY), mask)
            if desc is not None:
                _hero_templates[hid] = desc
    return _hero_templates


def detect_hero(screen: np.ndarray, top: int = 3) -> list[Match]:
    """[(hero_id, good_feature_matches), ...] best first, from the portrait at the top centre."""
    sx, sy = screen.shape[1] / BASE_W, screen.shape[0] / BASE_H
    x1, y1, x2, y2 = PORTRAIT_BOX
    crop = screen[int(y1 * sy) : int(y2 * sy), int(x1 * sx) : int(x2 * sx)]
    crop = cv2.resize(crop, (2 * (x2 - x1), 2 * (y2 - y1)), interpolation=cv2.INTER_CUBIC)
    _, desc = _orb.detectAndCompute(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None)
    if desc is None:
        return []
    scores = []
    for hid, tdesc in hero_templates().items():
        pairs = [m for m in _matcher.knnMatch(desc, tdesc, k=2) if len(m) == 2]
        scores.append((hid, sum(a.distance < 0.8 * b.distance for a, b in pairs)))
    return sorted(scores, key=lambda s: -s[1])[:top]


def detect_offer(screen: np.ndarray, top: int = 3) -> list[list[Match]]:
    """match_card results for the left, centre and right cards."""
    return [match_card(screen, box, top) for box in CARD_BOXES]


if __name__ == "__main__":
    names = data.items()
    screen = cv2.imread(sys.argv[1])
    heroes = data.heroes()
    print("hero: " + ", ".join(f"{heroes[hid]} {n}" for hid, n in detect_hero(screen)))
    for i, result in enumerate(detect_offer(screen)):
        print(f"card {i}: " + ", ".join(f"{names[iid]['name']} {s:.2f}" for iid, s in result))
