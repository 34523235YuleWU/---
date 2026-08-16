from __future__ import annotations

import tkinter as tk
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "tiles_fluffy"
OUT = ROOT / "assets" / "tiles_runtime"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.withdraw()
    try:
        for suit in ("wan", "tiao", "tong"):
            for rank in range(1, 10):
                source = tk.PhotoImage(file=SOURCE / f"{suit}_{rank}.png")
                source.subsample(10, 10).write(OUT / f"{suit}_{rank}_large.png", format="png")
                source.subsample(20, 20).write(OUT / f"{suit}_{rank}_small.png", format="png")
        back = tk.PhotoImage(file=SOURCE / "back.png")
        back.subsample(10, 10).write(OUT / "back_large.png", format="png")
        back.subsample(20, 20).write(OUT / "back_small.png", format="png")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
