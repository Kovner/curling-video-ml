#!/usr/bin/env python3
"""Coarse shot detection from storyboard tiles (~1 frame / 10 s).

Computes per-region motion energy (mean abs diff between consecutive tiles),
then finds peaks in the combined down-ice camera signal. At this sampling rate
each delivery+sweep shows up as one burst, so peaks ~= shots.
"""
import argparse
import csv
import glob
import os
import re

import cv2
import numpy as np
from scipy.signal import find_peaks

from regions import REGIONS, crop


def load_tiles(tile_dir, start, end):
    out = []
    for f in sorted(glob.glob(os.path.join(tile_dir, "t*.jpg"))):
        t = int(re.search(r"t(\d+)\.jpg$", f).group(1))
        if start - 30 <= t <= end + 30:  # pad so diffs cover the window edges
            out.append((t, cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2GRAY).astype(np.float32)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tile_dir")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float, default=1e9)
    ap.add_argument("--prominence", type=float, default=8.0)
    ap.add_argument("--min-gap", type=float, default=30.0, help="min seconds between shots")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    tiles = load_tiles(args.tile_dir, args.start, args.end)
    names = list(REGIONS)
    rows = []
    for (t0, a), (t1, b) in zip(tiles, tiles[1:]):
        d = np.abs(b - a)
        rows.append((t1, *[crop(d, REGIONS[n]).mean() for n in names]))
    arr = np.array(rows)
    t = arr[:, 0]
    dt = np.median(np.diff(t))

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "motion_storyboard.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t", *names])
        w.writerows(rows)

    # shots: bursts in the combined down-ice cameras
    sig = arr[:, names.index("left") + 1] + arr[:, names.index("right") + 1]
    sigs = np.convolve(sig, np.ones(2) / 2, mode="same")
    peaks, _ = find_peaks(sigs, prominence=args.prominence, distance=max(1, int(args.min_gap / dt)))
    peaks = [p for p in peaks if args.start <= t[p] <= args.end]

    with open(os.path.join(args.out, "shots_storyboard.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["shot", "time_s", "time_mmss", "motion"])
        for i, p in enumerate(peaks, 1):
            m, s = divmod(int(t[p]), 60)
            w.writerow([i, int(t[p]), f"{m}:{s:02d}", round(float(sigs[p]), 1)])
    print(f"{len(peaks)} shots detected; results in {args.out}/")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(16, 5))
    for i, n in enumerate(names):
        ax.plot(t, arr[:, i + 1], label=n, lw=1.2)
    for p in peaks:
        ax.axvline(t[p], color="r", alpha=0.3)
    ax.set_xlabel("video time (s)")
    ax.set_ylabel("mean abs frame diff")
    ax.set_title(f"Motion energy by region ({len(peaks)} shot peaks marked)")
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(args.out, "motion_window.png"), dpi=110)


if __name__ == "__main__":
    main()
