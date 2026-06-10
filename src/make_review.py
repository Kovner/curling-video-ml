#!/usr/bin/env python3
"""Build human-validation artifacts from detect_shots.py output.

1. A review reel: the clip sped up, with the detection state burned in
   (green "SHOT n" banner while a shot is active, red "rejected walk-by"
   during rejected segments, timecode always visible). Watching it answers
   "did we catch every shot, and do the boundaries look right?" in minutes.
2. A contact sheet: start / middle / end frame for every detected shot.
   Each row should read: delivery setup -> stone moving/sweeping -> rocks at
   rest. Any row that doesn't is a boundary error.
"""
import argparse
import csv
import os
import subprocess

import cv2
import numpy as np


def load_segs(path):
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    return [(float(r["start_s"]), float(r["end_s"])) for r in rows]


def banner(frame, text, color):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 34), color, -1)
    cv2.putText(frame, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)


def make_reel(video, shots, walkbys, out, speed):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    tmp = out + ".tmp.mp4"
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    i = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % speed == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            shot = next((k for k, (s, e) in enumerate(shots, 1) if s <= t <= e), None)
            walk = any(s <= t <= e for s, e in walkbys)
            if shot:
                banner(frame, f"SHOT {shot}", (40, 140, 40))
            elif walk:
                banner(frame, "rejected walk-by", (40, 40, 180))
            m, s = divmod(int(t), 60)
            cv2.putText(frame, f"{m}:{s:02d} ({speed}x)", (w - 130, h - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            vw.write(frame)
        i += 1
    vw.release()
    cap.release()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp,
                    "-c:v", "libx264", "-crf", "26", "-pix_fmt", "yuv420p", out], check=True)
    os.remove(tmp)


def make_contact_sheet(video, shots, out, tile_w=480):
    cap = cv2.VideoCapture(video)

    def grab(t, label):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok:
            return None
        f = cv2.resize(f, (tile_w, tile_w * f.shape[0] // f.shape[1]))
        cv2.putText(f, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return f

    rows = []
    for k, (s, e) in enumerate(shots, 1):
        m0, s0 = divmod(int(s), 60)
        m1, s1 = divmod(int(e), 60)
        tiles = [grab(s, f"shot {k} START {m0}:{s0:02d}"),
                 grab((s + e) / 2, f"shot {k} MID"),
                 grab(e, f"shot {k} END {m1}:{s1:02d}")]
        if all(t is not None for t in tiles):
            rows.append(np.hstack(tiles))
    cap.release()
    cv2.imwrite(out, np.vstack(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--shots", default="results/shots.csv")
    ap.add_argument("--rejected", default="results/shots_rejected.csv")
    ap.add_argument("--speed", type=int, default=4, help="reel speedup factor")
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()

    shots = load_segs(args.shots)
    walkbys = load_segs(args.rejected) if os.path.exists(args.rejected) else []
    sheet = os.path.join(args.out_dir, "contact_sheet.jpg")
    make_contact_sheet(args.video, shots, sheet)
    print(f"contact sheet -> {sheet}")
    reel = os.path.join(args.out_dir, "review_reel.mp4")
    make_reel(args.video, shots, walkbys, reel, args.speed)
    print(f"review reel -> {reel}")


if __name__ == "__main__":
    main()
