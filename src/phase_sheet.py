#!/usr/bin/env python3
"""Phase verification sheet: for every shot, the house-cam frame at each
detected phase time. Slide/release/near-hog show the delivery cam; far-hog
and stop show the arrival cam. A correct phase time should show: slide =
thrower pushing out, release = hand just off the handle, near hog = stone at
the red line, far hog = stone at the arrival red line, stop = stone at rest.
"""
import argparse
import csv

import cv2
import numpy as np

PHASES = [("t2_slide", "slide", "bot"), ("t4_release", "release", "bot"),
          ("t5_near_hog", "near hog", "bot"), ("t6_far_hog", "far hog", "top"),
          ("t7_stop", "stop", "top")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--phases", default="results/phases.csv")
    ap.add_argument("--out", default="results/phase_sheet")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)

    def crop(t, half):
        cap.set(cv2.CAP_PROP_POS_MSEC, max(t, 0) * 1000)
        ok, f = cap.read()
        if not ok:
            return np.zeros((360, 208, 3), np.uint8)
        s = f[0:180, 268:372] if half == "top" else f[180:360, 268:372]
        return cv2.resize(s, (208, 360), interpolation=cv2.INTER_CUBIC)

    with open(args.phases) as fh:
        shots = list(csv.DictReader(fh))

    rows = []
    for r in shots:
        tiles = []
        for col, label, half in PHASES:
            v = r[col]
            if v:
                tile = crop(float(v), half)
                txt = f"{int(r['shot'])} {label} {v}"
            else:
                tile = np.zeros((360, 208, 3), np.uint8)
                txt = f"{int(r['shot'])} {label} --"
            cv2.putText(tile, txt, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
            tiles.append(tile)
        rows.append(np.hstack(tiles))
    for part in range(0, len(rows), 8):
        sheet = np.vstack(rows[part:part + 8])
        path = f"{args.out}_{part // 8 + 1}.jpg"
        cv2.imwrite(path, sheet)
        print(f"-> {path}")


if __name__ == "__main__":
    main()
