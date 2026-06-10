# curling-video-ml

ML/CV analysis of curling livestreams. Long-term vision: auto-track shot types per
team, break down make percentages by scenario, measure time-per-shot, etc.

**Current milestone:** detect the beginning and end of every shot in a game.

Test video: https://www.youtube.com/watch?v=a2EJcV29ido
("6/8 - Sheet 1 - Spring Monday Open League 2026"), focusing on the end at
**15:22 – 30:58** for prototyping.

## Status: shot boundary detection works on real video

On the real 15:22–30:58 clip (`data/end_test.mp4`), `src/detect_shots.py` detects
**16/16 shots with 0 false positives**, rejecting all 3 "walk-by" events (players
walking down the ice between shots). See `results/validation.md` for how ground
truth was established and `results/shots.csv` for the boundaries.

Two findings that made it work:

1. **Per-panel normalization.** Each down-ice camera gets its own robust z-score
   and the per-sample max is used. Summing the panels first dilutes deliveries
   seen mostly by the far camera (this missed the first shot of the test end).
2. **House-cam phase ordering rejects walk-bys.** A shot crosses the
   delivery-end house cam early in its motion segment and reaches the arrival
   house late; a walker returning to the delivery end crosses the houses in the
   opposite order. Down-ice motion alone cannot make this distinction.

Detected shot durations already show the expected pattern: ~9–20 s for early
(lead/second) stones, stretching to 24–31 s for the final skip stones.

## Earlier findings (storyboard proof of concept)

The stream is a fixed-layout composite of three views:

| Region | Content |
|---|---|
| Left panel (~0–42% of width) | Down-ice camera, one end |
| Center strip (~42–58%) | Two stacked overhead house cams |
| Right panel (~58–100%) | Down-ice camera, other end |

A red wall-clock timestamp is burned into the bottom-left corner.

Even using only YouTube's **storyboard preview frames** (320x180, one frame every
~9.9 s — see "environment limitation" below), simple per-region frame differencing
resolves the shot cadence clearly. Peak detection on the combined left+right camera
motion signal over 15:22–30:58 finds **exactly 16 bursts** — the expected 16 shots
of a full end — with a plausible rhythm: ~50–60 s between shots early in the end,
stretching to 70–110 s for the final (skip) stones.

![motion energy](results/motion_window.png)

See `results/shots_storyboard.csv` for the detected shot times.

This strongly suggests that with the real video (e.g. 480p @ 30fps, sampled at a
few fps) we can detect shot start/end boundaries precisely: shot start = motion
burst begins in the delivery-end camera, shot end = motion settles in the house cam.

## Pipeline

```
scripts/download.sh          # yt-dlp invocation that works for this stream
src/extract_storyboard.py    # storyboard .mhtml -> timestamped frame tiles
src/analyze_storyboard.py    # tiles -> motion signal -> shot peaks (coarse, ~10s)
src/detect_shots.py          # full video -> precise shot start/end segments (CSV)
```

### Coarse storyboard analysis (works anywhere, reproducible from checked-in data)

```bash
pip install -r requirements.txt
python src/extract_storyboard.py data/storyboard.mhtml --out data/sb_tiles
python src/analyze_storyboard.py data/sb_tiles --start 922 --end 1858 --out results/
```

### Full-resolution detection (needs the actual video)

```bash
./scripts/download.sh                       # or download manually with yt-dlp
python src/detect_shots.py data/end_test.mp4 --plot --out results/shots.csv
```

`detect_shots.py` samples the video at ~4 fps, computes motion energy per camera
region, segments candidates with hysteresis thresholding (a shot is "active" while
motion stays elevated; boundaries are walked out to the quiet baseline), then
rejects walk-bys using the house-cam phase rule. Play direction is auto-detected
(`--direction` to force it).

## Environment limitation (why storyboards?)

This repo was bootstrapped in a cloud sandbox whose egress proxy presents different
client IPs to youtube.com and googlevideo.com. YouTube binds stream URLs to the
requesting IP, so every actual video download 403s here, regardless of player
client / PO token / JS-challenge setup (all of which were configured and working —
see `scripts/download.sh`). Only the storyboard images were downloadable, so the
proof of concept uses those. Run the download on a normal residential connection
and everything in `detect_shots.py` applies to the real frames.

## Next steps

- [x] Run `detect_shots.py` on the real 15:22–30:58 clip and validate against
      ground truth: 16/16 shots, 0 false positives (`results/validation.md`).
- [ ] Validate on more ends / a full game (end breaks, between-end practice
      slides, and same-direction walkers are untested failure modes).
- [ ] Frame-exact boundary ground truth; tighten "all rocks stopped" using the
      house cam (stone-handle HSV detection already prototyped — stones are
      cleanly detectable as red/yellow dots, see validation notes).
- [ ] Team attribution: stones alternate, and handle color of the delivered
      stone is detectable in the house cam.
- [ ] OCR the burned-in clock to make timing robust to stream gaps.
- [ ] Stone tracking in the house cam -> shot type + make/miss inference.
