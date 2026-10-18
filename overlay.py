"""Click-through overlay that watches for the item-choice screen and highlights the best card.

    python overlay.py                    # auto: detects the hero and offer, Ctrl+F8 quits
    python overlay.py --hero Yamato      # skip hero detection
    python overlay.py --monitor 2 --key F7
    python overlay.py --demo samples/others.png   # render once from a screenshot

Strictly external: we only screenshot the desktop and draw our own window. Nothing is
read from or sent to the game process.
"""

import argparse
import ctypes
import logging
import queue
import threading
import tkinter as tk
from ctypes import wintypes

import cv2
import mss
import numpy as np

import advisor
import data
import detect

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixels for Tk and mss

log = logging.getLogger("advisor")

POLL_MS = 1000
MIN_MATCH = 0.65  # below this, assume we're not looking at the item-choice screen
HERO_MARGIN = 1.5  # best hero must have this many times the runner-up's feature matches
KEY_COLOR = "#010101"  # drawn in this colour = fully transparent
REROLL_POS = (1280, 1100)  # under the "Use Re-Roll" button, at 1440p
LAST_CAPTURE = data.CACHE_DIR / "last_capture.png"

WM_HOTKEY = 0x0312
MOD_CONTROL, MOD_NOREPEAT = 0x0002, 0x4000
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_LAYERED = 0x20, 0x80, 0x80000
WS_EX_NOACTIVATE = 0x08000000
WDA_EXCLUDEFROMCAPTURE = 0x11  # keeps our drawings out of our own screenshots


def find_hero(screen: np.ndarray) -> int | None:
    """hero_id from the portrait, or None if the match isn't clear."""
    ranked = detect.detect_hero(screen, top=2)
    if not ranked or ranked[0][1] < detect.MIN_HERO_MATCHES:
        return None
    if len(ranked) > 1 and ranked[0][1] < HERO_MARGIN * ranked[1][1]:
        return None
    return ranked[0][0]


def detect_offer_ids(screen: np.ndarray) -> list[int] | None:
    """The three offered item ids, or None if this isn't the item-choice screen."""
    offer = detect.detect_offer(screen, top=1)
    if min(r[0][1] for r in offer) < MIN_MATCH:
        return None
    return [r[0][0] for r in offer]


def _hotkey_loop(events: queue.Queue[str], vk: int) -> None:
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, 1, MOD_NOREPEAT, vk):
        events.put("hotkey-taken")
        return
    user32.RegisterHotKey(None, 2, MOD_CONTROL | MOD_NOREPEAT, vk)
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY:
            events.put("refresh" if msg.wParam == 1 else "quit")


class Overlay:
    def __init__(
        self, hero_id: int | None = None, demo: np.ndarray | None = None, monitor: int | None = None
    ) -> None:
        self.fixed_hero = hero_id
        self.hero_id = hero_id
        self.demo = demo
        self.shown_ids = None
        self.sct = mss.MSS()
        mons = self.sct.monitors[1:]
        self.mon = (
            mons[monitor - 1]
            if monitor
            else next((m for m in mons if m.get("is_primary")), mons[0])
        )
        self.sx = self.mon["width"] / detect.BASE_W
        self.sy = self.mon["height"] / detect.BASE_H

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry(
            f"{self.mon['width']}x{self.mon['height']}+{self.mon['left']}+{self.mon['top']}"
        )
        self.root.attributes("-topmost", True, "-transparentcolor", KEY_COLOR)
        self.canvas = tk.Canvas(self.root, bg=KEY_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.root.update()
        self._setup_window()

    def _setup_window(self) -> None:
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(self.root.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
        )
        user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)

    def _pt(self, x: float, y: float) -> tuple[float, float]:
        return x * self.sx, y * self.sy

    def _text(self, x: float, y: float, text: str, color: str, size: int) -> None:
        x, y = self._pt(x, y)
        item = self.canvas.create_text(
            x, y, text=text, fill=color, font=("Segoe UI", int(size * self.sy), "bold")
        )
        x1, y1, x2, y2 = self.canvas.bbox(item)
        bg = self.canvas.create_rectangle(
            x1 - 8, y1 - 2, x2 + 8, y2 + 2, fill="#181818", outline=""
        )
        self.canvas.tag_lower(bg, item)

    def _grab(self) -> np.ndarray:
        if self.demo is not None:
            return self.demo
        shot = np.asarray(self.sct.grab(self.mon))
        return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)

    def _draw(self, ids: list[int]) -> None:
        advice = advisor.rate(self.hero_id, ids)
        rated, reroll = advice.ranked, advice.reroll
        by_id = {r.item_id: r for r in rated}
        best = rated[0].item_id
        for (x1, y1, x2, y2), iid in zip(detect.CARD_BOXES, ids, strict=True):
            r = by_id[iid]
            is_best = iid == best and not reroll
            if is_best:
                pad = 14
                self.canvas.create_rectangle(
                    *self._pt(x1 - pad, y1 - pad),
                    *self._pt(x2 + pad, y2 + pad),
                    outline="#33ff66",
                    width=max(3, int(8 * self.sy)),
                )
            self._text(
                (x1 + x2) / 2, y1 - 70, f"{r.score:.1%}", "#33ff66" if is_best else "#dddddd", 20
            )
        if reroll:
            self._text(*REROLL_POS, "REROLL", "#ff4444", 34)
        hero = data.heroes()[self.hero_id]
        self._text(detect.BASE_W / 2, 175, hero, "#aaaaaa", 11)
        log.info(
            "%s: %s%s",
            hero,
            "REROLL  " if reroll else "",
            "  ".join(f"{by_id[i].name} {by_id[i].score:.1%}" for i in ids),
        )

    def tick(self, force: bool = False) -> None:
        """Capture once; draw advice for a new offer, or clear when the item screen is gone."""
        screen = self._grab()
        ids = detect_offer_ids(screen)
        if ids is None:
            if self.shown_ids is not None:
                self.canvas.delete("all")
                self.shown_ids = None
            return
        if ids == self.shown_ids and not force:
            return
        self.canvas.delete("all")
        self.shown_ids = ids
        if self.demo is None:
            cv2.imwrite(str(LAST_CAPTURE), screen)  # for calibration/debugging
        if not self.fixed_hero:
            self.hero_id = find_hero(screen) or self.hero_id  # keep the last hero if unclear
        if self.hero_id is None:
            log.warning("Item screen found but hero not recognised; saved %s", LAST_CAPTURE)
            self._text(
                detect.BASE_W / 2, 200, "Advisor: hero not recognised (use --hero)", "#ffcc33", 16
            )
            return
        self._draw(ids)

    def poll(self, events: queue.Queue[str]) -> None:
        """Handle hotkey events and tick, then reschedule itself on the Tk loop."""
        try:
            while True:
                ev = events.get_nowait()
                if ev == "quit":
                    self.root.destroy()
                    return
                if ev == "hotkey-taken":
                    log.error("Hotkey already in use by another program; pick another with --key")
                    self.root.destroy()
                    return
                if ev == "refresh":
                    self.tick(force=True)
        except queue.Empty:
            pass
        if self.demo is None:
            self.tick()
        self.root.after(POLL_MS, self.poll, events)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", help="hero name (default: detect from the item screen)")
    ap.add_argument("--key", default="F8", help="F1-F12: force refresh; Ctrl+key quits")
    ap.add_argument("--demo", help="render once from this screenshot instead of the screen")
    ap.add_argument("--monitor", type=int, help="mss monitor number (default: the primary monitor)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    hero_id = data.find_hero(args.hero) if args.hero else None
    detect.templates()  # warm caches so the first detection is fast
    detect.hero_templates()

    demo = cv2.imread(args.demo) if args.demo else None
    overlay = Overlay(hero_id, demo, args.monitor)
    events = queue.Queue()
    vk = 0x6F + int(args.key.upper().lstrip("F"))
    threading.Thread(target=_hotkey_loop, args=(events, vk), daemon=True).start()
    if demo is not None:
        overlay.root.after(200, overlay.tick)
    log.info("Watching for the item screen. %s = refresh, Ctrl+%s = quit.", args.key, args.key)
    overlay.poll(events)
    overlay.root.mainloop()


if __name__ == "__main__":
    main()
