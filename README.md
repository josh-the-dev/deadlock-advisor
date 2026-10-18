# Deadlock Street Brawl Item Advisor

An on-screen advisor for Deadlock's **Street Brawl** mode. When the item draft screen appears,
it recognises your hero and the three offered items, then highlights the pick with the best
recent win rate for that hero — or tells you to **reroll**.

Stats come from the free public [deadlock-api.com](https://api.deadlock-api.com) (last 30 days
of Street Brawl matches).

## Safe by design
The advisor is a completely separate program. It only takes screenshots of your desktop and
draws its own transparent, click-through window on top. It never reads or writes game memory,
injects anything, hooks rendering, or sends input to the game — you always click the item
yourself.

## Setup
Windows, Python 3.12+, and the game in **borderless windowed** mode.

```
pip install -r requirements.txt
python overlay.py
```

Leave it running while you play. On the item screen you'll see:
- a **green box** around the best card,
- the (smoothed) win rate above each card,
- **REROLL** under the re-roll button when every offer is notably below your hero's average.

Keys: **F8** re-checks the screen now, **Ctrl+F8** quits.

Options:
- `--hero Yamato` skips hero detection
- `--monitor N` picks the screen (default: your Windows primary monitor)
- `--key F7` changes the hotkey
- `--demo samples/others.png` renders once from a screenshot (handy for testing)

The first run downloads item icons and hero portraits into `cache/` (~10 MB).

## Other tools
- `python cli.py Yamato "Arctic Blast" "Echo Shard" "Surge of Power"` ranks items by name
- `python cli.py Yamato --top 10` shows a hero's best items
- `python detect.py samples/others.png` prints what the detector sees in a screenshot

## Status
Early. Tested on 2560×1440; other resolutions are scaled but untested. Enhanced items aren't
treated separately yet.

Not affiliated with Valve. Deadlock and its assets belong to Valve.
