#!/usr/bin/env python3
"""Detect shot start/end boundaries in a curling livestream video.

Samples the video at a few fps, computes motion energy in each camera region
(see regions.py), and segments shots with hysteresis thresholding:

  - a shot becomes active when the smoothed down-ice motion signal rises above
    `high` (delivery + sweepers moving),
  - its boundaries are walked outward until the signal drops below `low`
    (ice quiet again / rocks stopped).

Outputs a CSV of (shot, start_s, end_s, duration_s, peak_motion) and an
optional diagnostic plot. Thresholds are in robust z-score units (median/MAD),
so they should transfer across resolutions and lighting.
"""
import argparse
import csv
import os

import cv2
import numpy as np

from regions import REGIONS, crop


def motion_series(path, sample_fps, max_width=320, start=None, end=None):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise SystemExit(f"cannot open {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / sample_fps))
    if start:
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)

    names = list(REGIONS)
    times, vals = [], []
    prev = None
    i = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if end and t > end:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            if frame.shape[1] > max_width:
                scale = max_width / frame.shape[1]
                frame = cv2.resize(frame, (max_width, int(frame.shape[0] * scale)))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            if prev is not None:
                d = np.abs(gray - prev)
                times.append(t)
                vals.append([crop(d, REGIONS[n]).mean() for n in names])
            prev = gray
        i += 1
    cap.release()
    return np.array(times), np.array(vals), names


def robust_z(x):
    med = np.median(x)
    mad = np.median(np.abs(x - med)) + 1e-6
    return (x - med) / (1.4826 * mad)


def segment(t, sig, high=3.0, low=1.0, min_dur=8.0, merge_gap=6.0):
    """Hysteresis segmentation: seeds where sig > high, grown out to sig < low."""
    active = sig > high
    segs = []
    i = 0
    n = len(sig)
    while i < n:
        if not active[i]:
            i += 1
            continue
        s = i
        while s > 0 and sig[s - 1] > low:
            s -= 1
        e = i
        while e + 1 < n and (active[e + 1] or sig[e + 1] > low):
            e += 1
        segs.append([s, e])
        i = e + 1
    # merge segments separated by a short quiet gap
    merged = []
    for s, e in segs:
        if merged and t[s] - t[merged[-1][1]] < merge_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged if t[e] - t[s] >= min_dur]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=4.0, help="sampling rate")
    ap.add_argument("--start", type=float, help="analyze from this time (s)")
    ap.add_argument("--end", type=float, help="analyze until this time (s)")
    ap.add_argument("--high", type=float, default=3.0, help="shot trigger threshold (z)")
    ap.add_argument("--low", type=float, default=1.0, help="boundary threshold (z)")
    ap.add_argument("--min-dur", type=float, default=8.0, help="min shot duration (s)")
    ap.add_argument("--out", default="results/shots.csv")
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    t, vals, names = motion_series(args.video, args.fps, start=args.start, end=args.end)
    if len(t) < 10:
        raise SystemExit("not enough frames")

    downice = vals[:, names.index("left")] + vals[:, names.index("right")]
    # smooth over ~2 s
    k = max(1, int(2 * args.fps))
    sig = robust_z(np.convolve(downice, np.ones(k) / k, mode="same"))
    segs = segment(t, sig, args.high, args.low, args.min_dur)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["shot", "start_s", "end_s", "duration_s", "peak_z"])
        for i, (s, e) in enumerate(segs, 1):
            w.writerow([i, round(t[s], 1), round(t[e], 1), round(t[e] - t[s], 1),
                        round(float(sig[s : e + 1].max()), 2)])
    print(f"{len(segs)} shots -> {args.out}")
    for i, (s, e) in enumerate(segs, 1):
        m0, s0 = divmod(int(t[s]), 60)
        m1, s1 = divmod(int(t[e]), 60)
        print(f"  shot {i:2d}: {m0}:{s0:02d} - {m1}:{s1:02d}  ({t[e]-t[s]:.0f}s)")

    if args.plot:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(16, 5))
        ax.plot(t, sig, lw=0.8, label="down-ice motion (z)")
        for s, e in segs:
            ax.axvspan(t[s], t[e], color="g", alpha=0.2)
        ax.axhline(args.high, color="r", ls="--", lw=0.8)
        ax.axhline(args.low, color="orange", ls="--", lw=0.8)
        ax.set_xlabel("video time (s)")
        ax.legend()
        png = os.path.splitext(args.out)[0] + ".png"
        plt.tight_layout()
        plt.savefig(png, dpi=110)
        print(f"plot -> {png}")


if __name__ == "__main__":
    main()
