#!/usr/bin/env python3
"""Mark the phases of each detected shot and measure the shot result.

Phases (times in seconds on the video clock):
  1 pre-shot      from the previous shot's stop until the slide begins
  2 slide_begin   thrower pushes out of the hack (delivery house cam)
  3 backline      stone/thrower front crosses the backline (delivery cam)
  4 release       shooter lets go: the handle color becomes visible as a dot
                  separated ahead of the thrower's body blob (delivery cam)
  5 near_hog      stone reaches the delivery-end hogline (edge of the
                  delivery cam's view)
  6 far_hog       stone crosses the arrival-end hogline (arrival cam)
  7 stop          stone comes to rest (arrival cam dot track stabilizes)

Result: resting (x, y) of the delivered stone in inches from the pin.
x positive to the right as seen in the arrival house cam, y positive past the
pin (away from the delivery end). Calibrated from an ellipse fit of the green
12-ft ring (144 in diameter). Positions are reliable in/near the house and
degrade toward the cam's fringe (long guards, through stones).

Stream geometry (validated frame-by-frame, see results/validation.md):
the center strip holds two overhead house cams, each oriented with its own
house toward the strip edge and mid-sheet toward the strip center. The
delivered stone travels upward in both cams: hack (strip bottom) -> delivery
house -> delivery hogline (y~193) -> [middle of sheet, unviewed] -> arrival
hogline (y~152) -> arrival house (strip top). Note the down-ice motion
segment from detect_shots.py typically starts ~3 s after the slide begins
and ends several seconds before the stone actually stops; phases use the
house cams for precise timing.
"""
import argparse
import csv
import json
import os

import cv2
import numpy as np

STRIP_X = (268, 372)          # house-cam strip in the 640x360 frame
TOP, BOT = slice(0, 180), slice(180, 360)


def read_strip(cap, t):
    cap.set(cv2.CAP_PROP_POS_MSEC, max(t, 0) * 1000)
    ok, f = cap.read()
    return f[:, STRIP_X[0]:STRIP_X[1]] if ok else None


def median_strip(cap, t0, t1, n=9):
    frames = [read_strip(cap, tt) for tt in np.linspace(t0, t1, n)]
    frames = [f for f in frames if f is not None]
    return np.median(frames, axis=0).astype(np.uint8)


def detect_dots(bgr, min_area=2, max_area=120):
    """Stone-handle colored (red/yellow) blobs: (color, x, y)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    masks = {
        "red": ((h < 10) | (h > 170)) & (s > 90) & (v > 60),
        "yellow": (h >= 18) & (h <= 35) & (s > 90) & (v > 100),
    }
    out = []
    for color, m in masks.items():
        n, lab, stats, cents = cv2.connectedComponentsWithStats(m.astype(np.uint8))
        for i in range(1, n):
            if min_area <= stats[i, cv2.CC_STAT_AREA] <= max_area:
                out.append((color, float(cents[i][0]), float(cents[i][1])))
    return out


def fit_house(strip, half):
    """Ellipse fit of the green 12-ft ring -> (cx, cy, rx, ry) in strip coords."""
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    green = ((h >= 40) & (h <= 85) & (s > 60) & (v > 40)).astype(np.uint8)
    mask = np.zeros_like(green)
    mask[half] = 1
    cnts, _ = cv2.findContours(green * mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    (cx, cy), (d1, d2), ang = cv2.fitEllipse(c)
    return cx, cy, d1 / 2, d2 / 2


def find_hogline(strip, y_range):
    """Row of the red hogline: max horizontal redness within y_range."""
    b, g, r = (strip[..., i].astype(int) for i in range(3))
    redness = np.clip(r - np.maximum(g, b), 0, None).sum(axis=1)
    y0, y1 = y_range
    return y0 + int(np.argmax(redness[y0:y1]))


def calibrate(cap, quiet_times):
    strip = median_strip(cap, *quiet_times, n=11)
    tx, ty, trx, try_ = fit_house(strip, TOP)
    bx, by, brx, bry = fit_house(strip, BOT)
    return {
        "arrival": {"pin": [tx, ty], "px_per_in": [trx / 72.0, try_ / 72.0],
                    "hog_y": find_hogline(strip, (int(ty + try_) + 5, 178))},
        "delivery": {"pin": [bx, by], "px_per_in": [brx / 72.0, bry / 72.0],
                     "hog_y": find_hogline(strip, (182, int(by - bry) - 5)),
                     "back_y": by + bry},
    }


# ---------------------------------------------------------------- delivery

def delivery_front(frame, quiet, hog_y):
    """Leading (lowest-y) edge of moving bodies below the delivery hogline."""
    d = cv2.absdiff(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                    cv2.cvtColor(quiet, cv2.COLOR_BGR2GRAY))
    m = (d > 28).astype(np.uint8)
    m[: hog_y - 8] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, cents = cv2.connectedComponentsWithStats(m)
    tops = [stats[i, cv2.CC_STAT_TOP] for i in range(1, n)
            if stats[i, cv2.CC_STAT_AREA] > 60]
    return min(tops) if tops else None


def track_delivery(cap, t_seed, calib, fps=8.0):
    """Phases 2-5 from the delivery house cam around the slide."""
    dcal = calib["delivery"]
    quiet = median_strip(cap, t_seed - 26, t_seed - 18, n=7)
    ts = np.arange(t_seed - 18, t_seed + 8, 1.0 / fps)
    fronts, dotlists = [], []
    for t in ts:
        f = read_strip(cap, t)
        fronts.append(delivery_front(f, quiet, dcal["hog_y"]) if f is not None else None)
        dotlists.append([d for d in detect_dots(f)
                         if dcal["hog_y"] - 6 <= d[2] <= dcal["back_y"] + 8]
                        if f is not None else [])

    # median-smooth the front series (interpolating gaps) so single-sample
    # flickers don't split the slide into disqualified fragments
    idx = [i for i, f in enumerate(fronts) if f is not None]
    if len(idx) >= 5:
        filled = np.interp(np.arange(len(fronts)), idx, [fronts[i] for i in idx])
        k = 5
        pad = np.pad(filled, k // 2, mode="edge")
        fronts = [float(np.median(pad[i:i + k])) for i in range(len(fronts))]

    t2 = t3 = t4 = t5 = None
    # phase 2: the slide is the advancing run (decreasing front y) that exits
    # the view through the hogline region. Between-shot fidgeting at the hack
    # also advances, but never gets near the hog. Take the latest qualifying
    # run that starts before the down-ice motion segment is underway.
    runs = []
    run_start = None
    prev = None
    stall = 0
    for i, fr in enumerate(fronts):
        if fr is None:
            continue
        if prev is not None and fr < prev + 1:   # advancing or holding
            if run_start is None and fr < prev - 0.5:
                run_start = i - 1
            stall = 0 if fr < prev - 0.5 else stall + 1
            if stall > 4 and run_start is not None:
                runs.append((run_start, i))
                run_start = None
        else:
            if run_start is not None:
                runs.append((run_start, i))
                run_start = None
        prev = fr
    if run_start is not None:
        runs.append((run_start, len(fronts) - 1))
    qual = []
    for a, b in runs:
        seg = [f for f in fronts[a:b + 1] if f is not None]
        if (seg and ts[b] - ts[a] >= 1.0 and seg[0] >= 225
                and min(seg) <= dcal["hog_y"] + 12 and seg[0] - min(seg) >= 40):
            qual.append((a, b))
    # the slide ends (front exits via the hogline) right as down-ice sweeping
    # ramps up, i.e. near the motion-segment seed
    if qual:
        a, b = min(qual, key=lambda q: abs(ts[q[1]] - t_seed))
        t2 = ts[a]
    # phase 3 (backline cross) is not separately observable on this rink: the
    # thrower's body already extends past the backline at setup, and the stone
    # itself is hidden under the hand. Left blank.
    # phase 4: the handle dot appears in the delivery zone once the hand lets
    # go (it is covered during the slide)
    if t2 is not None:
        for i, ds in enumerate(dotlists):
            if ts[i] <= t2 + 0.5:
                continue
            if any(dcal["hog_y"] + 4 <= d[2] <= dcal["back_y"] for d in ds):
                t4 = ts[i]
                break
    # phase 5: dot reaches the delivery hogline (edge of this cam's view)
    start5 = t4 if t4 is not None else t2
    if start5 is not None:
        for i, ds in enumerate(dotlists):
            if ts[i] <= start5:
                continue
            if any(d[2] <= dcal["hog_y"] + 3 for d in ds):
                t5 = ts[i]
                break
    return t2, t3, t4, t5


# ----------------------------------------------------------------- arrival

def stationary_tail(chain, now, eps=2.0, span=2.0):
    pts = [(t, x, y) for t, x, y in chain if t >= now - span]
    if len(pts) < 3:
        return False
    xs, ys = [p[1] for p in pts], [p[2] for p in pts]
    return max(xs) - min(xs) < eps and max(ys) - min(ys) < eps


def track_arrival(cap, s, e, calib, fps=8.0):
    """Phases 6-7 + delivered-stone resting position from the arrival cam.

    Dot observations are chained frame-to-frame (gated nearest neighbor,
    occlusion gaps up to 4 s, chains freeze once stationary so passing
    brooms can't extend them). The delivered stone is the chain with net
    upward travel that best overlaps the shot window. Resting position
    falls back to a pre/post house-state diff when no chain survives
    (e.g. the handle is too small to see until the stone is well inside
    the cam's view).
    """
    acal = calib["arrival"]
    pre = median_strip(cap, s - 10, s - 2, n=7)
    rest = [d for d in detect_dots(pre) if d[2] < 180]
    chains = []
    for t in np.arange(s + 2, e + 20, 1.0 / fps):
        f = read_strip(cap, t)
        if f is None:
            continue
        for c, x, y in detect_dots(f):
            if y >= 182:
                continue
            if any((x - rx) ** 2 + (y - ry) ** 2 <= 64 for _, rx, ry in rest):
                continue
            best = None
            for ch in chains:
                lt, lx, ly = ch[-1]
                if t - lt > 4.0:
                    continue
                d2 = (x - lx) ** 2 + (y - ly) ** 2
                if stationary_tail(ch, lt) and d2 > 36:
                    continue
                if d2 < (6 + 22 * (t - lt)) ** 2 and (best is None or d2 < best[1]):
                    best = (ch, d2)
            if best:
                best[0].append((t, x, y))
            else:
                chains.append([(t, x, y)])

    t6 = t7 = x_in = y_in = None
    method = ""
    cands = [ch for ch in chains if len(ch) >= 5 and ch[0][2] - ch[-1][2] >= 15]
    if cands:
        ch = max(cands, key=lambda c: (min(c[-1][0], e + 6) - max(c[0][0], s), len(c)))
        arr = np.array(ch)
        above = arr[arr[:, 2] <= acal["hog_y"]]
        if len(above):
            t6 = float(above[0, 0])
        fin = np.median(arr[-4:, 1:], axis=0)
        moving = arr[(np.abs(arr[:, 1] - fin[0]) > 2.5) | (np.abs(arr[:, 2] - fin[1]) > 2.5)]
        t7 = float(moving[-1, 0]) if len(moving) else float(arr[0, 0])
        x_px, y_px = fin
        method = "track"
    else:
        # fallback: stone added to the house state
        post = median_strip(cap, e + 10, e + 24, n=9)
        added = [d for d in detect_dots(post) if d[2] < 180 and
                 all((d[1] - rx) ** 2 + (d[2] - ry) ** 2 > 36 for _, rx, ry in rest)]
        if added:
            d = max(added, key=lambda d: d[2])  # frontmost new stone
            x_px, y_px = d[1], d[2]
            method = "state-diff"
        else:
            return t6, t7, None, None, "none"
    (cx, cy), (sx, sy) = acal["pin"], acal["px_per_in"]
    x_in = (x_px - cx) / sx
    y_in = (cy - y_px) / sy
    return t6, t7, x_in, y_in, method


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--shots", default="results/shots.csv")
    ap.add_argument("--quiet", type=float, nargs=2, default=[40, 80],
                    help="quiet stretch with clear houses for calibration (s)")
    ap.add_argument("--out", default="results/phases.csv")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    calib = calibrate(cap, args.quiet)
    print("calibration:", json.dumps(calib, default=float))

    with open(args.shots) as fh:
        shots = list(csv.DictReader(fh))

    rows = []
    prev_stop = None
    for r in shots:
        k = int(r["shot"])
        s, e = float(r["start_s"]), float(r["end_s"])
        t2, t3, t4, t5 = track_delivery(cap, s, calib)
        t6, t7, x_in, y_in, method = track_arrival(cap, s, e, calib)
        t1 = prev_stop
        prev_stop = t7 if t7 is not None else e
        fmt = lambda v, nd=1: round(v, nd) if v is not None else ""
        rows.append([k, fmt(t1), fmt(t2), fmt(t3), fmt(t4), fmt(t5), fmt(t6), fmt(t7),
                     fmt(x_in), fmt(y_in), method])
        print(f"shot {k:2d}: pre={fmt(t1)} slide={fmt(t2)} back={fmt(t3)} "
              f"release={fmt(t4)} near_hog={fmt(t5)} far_hog={fmt(t6)} stop={fmt(t7)} "
              f"result=({fmt(x_in)},{fmt(y_in)}) in [{method}]")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["shot", "t1_preshot", "t2_slide", "t3_backline", "t4_release",
                    "t5_near_hog", "t6_far_hog", "t7_stop", "x_in", "y_in", "result_method"])
        w.writerows(rows)
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
