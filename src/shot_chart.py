#!/usr/bin/env python3
"""Render a shot chart: resting positions from phases.csv on a to-scale house.

x: inches right of the centerline (arrival cam view), y: inches past the pin.
"""
import argparse
import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases", default="results/phases.csv")
    ap.add_argument("--out", default="results/shot_chart.png")
    args = ap.parse_args()

    with open(args.phases) as fh:
        rows = [r for r in csv.DictReader(fh) if r["x_in"]]

    fig, ax = plt.subplots(figsize=(7, 11))
    for r, color in [(72, "#1a9641"), (48, "white"), (24, "#2c7fb8"), (6, "white")]:
        ax.add_patch(Circle((0, 0), r, color=color, zorder=1, ec="gray", lw=0.5))
    ax.axhline(0, color="gray", lw=0.7, zorder=2)          # tee line
    ax.axvline(0, color="gray", lw=0.7, zorder=2)          # centerline
    ax.axhline(72, color="black", lw=1.2, zorder=2)        # backline
    ax.axhline(-252, color="red", lw=1.2, zorder=2)        # hogline

    for r in rows:
        k = int(r["shot"])
        x, y = float(r["x_in"]), float(r["y_in"])
        team = "red" if k % 2 == 1 else "gold"  # stones alternate
        ax.add_patch(Circle((x, y), 5.7, color=team, zorder=3, ec="black", lw=0.8))
        ax.annotate(str(k), (x, y), ha="center", va="center", zorder=4,
                    fontsize=8, fontweight="bold", color="white")

    ax.set_xlim(-90, 90)
    ax.set_ylim(-270, 100)
    ax.set_aspect("equal")
    ax.set_xlabel("inches from centerline")
    ax.set_ylabel("inches from pin (negative = short)")
    ax.set_title("Resting position of each delivered stone\n"
                 "(note: positions are where each stone stopped, before later shots moved it)")
    plt.tight_layout()
    plt.savefig(args.out, dpi=120)
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
