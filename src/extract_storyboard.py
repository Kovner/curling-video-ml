#!/usr/bin/env python3
"""Extract timestamped frame tiles from a yt-dlp storyboard .mhtml download.

Each MIME part is a JPEG mosaic (e.g. 960x540 = 3x3 grid of 320x180 tiles);
tiles are evenly spaced in time across the video. The stdlib email parser
mangles the binary payloads, so we split on the MIME boundary manually.
"""
import argparse
import os
import re

import cv2


def extract_jpegs(mhtml_path):
    data = open(mhtml_path, "rb").read()
    m = re.search(rb'boundary="([^"]+)"', data)
    if not m:
        raise ValueError("no MIME boundary found")
    parts = data.split(b"--" + m.group(1))
    jpegs = []
    for p in parts:
        soi = p.find(b"\xff\xd8\xff")
        if soi == -1:
            continue
        eoi = p.rfind(b"\xff\xd9")
        if eoi == -1:
            continue
        jpegs.append(p[soi : eoi + 2])
    return jpegs, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mhtml")
    ap.add_argument("--out", default="data/sb_tiles")
    ap.add_argument("--grid", type=int, nargs=2, default=[3, 3], metavar=("ROWS", "COLS"))
    args = ap.parse_args()

    jpegs, raw = extract_jpegs(args.mhtml)
    # Video duration from the last slide caption, e.g. "Slide #124: 03:04:15"
    caps = re.findall(rb"Slide #\d+: ([\d:]+)", raw)
    h, m, s = (int(x) for x in caps[-1].split(b":"))
    # captions give the *start* of the last mosaic; add one mosaic of duration
    n_frag = len(jpegs)
    last_start = h * 3600 + m * 60 + s
    frag_dur = last_start / max(n_frag - 1, 1)
    duration = last_start + frag_dur

    rows, cols = args.grid
    per = rows * cols
    interval = duration / (n_frag * per)
    os.makedirs(args.out, exist_ok=True)
    import numpy as np

    n_tiles = 0
    for fi, jpg in enumerate(jpegs):
        img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        th, tw = img.shape[0] // rows, img.shape[1] // cols
        for r in range(rows):
            for c in range(cols):
                tile = img[r * th : (r + 1) * th, c * tw : (c + 1) * tw]
                if tile.size == 0:
                    continue
                t = (fi * per + r * cols + c) * interval
                cv2.imwrite(os.path.join(args.out, f"t{int(t):05d}.jpg"), tile)
                n_tiles += 1
    print(f"wrote {n_tiles} tiles to {args.out} (interval ~{interval:.2f}s)")


if __name__ == "__main__":
    main()
