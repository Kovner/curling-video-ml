# Validation of detect_shots.py on the test end (15:22–30:58)

Clip: `data/end_test.mp4` (936 s, 640x360 @ 30fps). All times are clip-relative.

## Ground truth

Established by combining:
- the storyboard cadence analysis (16 quasi-periodic motion bursts, matching the
  16 shots of a full end), and
- manual frame review of every ambiguous event (frame strips every 3–5 s around
  each candidate, checking for a delivery/sweeping vs. people walking).

Frame review confirmed:
- a real first shot at ~0:18–0:35 (delivery visible in the right panel,
  stone arriving in the house cam) that naive thresholds missed;
- three motion bursts that are **not** shots, at ~10:03, ~11:26, ~12:42 —
  players walking down the ice between shots (large near-camera motion);
- sweeping during the 12:11–12:28 segment (a real shot, previously suspect).

## Result: 16/16 shots detected, 3/3 walk-bys rejected, 0 false positives

| Failure mode found | Fix |
|---|---|
| First shot missed: summing the two down-ice panels dilutes motion seen mostly by the far camera | z-score each panel separately, take the per-sample max |
| Walk-bys indistinguishable from deliveries in down-ice motion alone | house-cam phase ordering (below) |

### Walk-by rejection (house phase ordering)

A shot crosses the delivery-end house cam early in its segment and produces
arrival-house motion late (stone + sweepers arriving). A walker returning to the
delivery end crosses the arrival house first. Measured peak positions (0 =
segment start, 1 = end):

- 16 shots: arrival-house peak at 0.43–0.97, always after the delivery-house peak
- 3 walk-bys: arrival-house peak at 0.00–0.12, always before the delivery-house peak

Decision rule: arrival-house peak later than delivery-house peak AND ≥ 0.4.
Known gap: a walker moving in the same direction as play would pass this test
(none occur in this end).

### Boundary accuracy

Spot-checked by frame inspection (shots 1, 5, 11): detected starts land at or a
few seconds before the delivery push-off; detected ends land within ~5 s of the
rocks coming to rest. Not yet frame-exact ground truth — good enough for shot
counting, attribution, and per-shot timing stats.

## Shot phases + result coordinates (src/phases.py)

Per-shot phase coverage on the test end (16 shots):

- slide begin: 16/16 (sweepers staged at the delivery hogline used to pin
  the body-front signal and mask the skip stones; mask-edge blobs are now
  excluded)
- release (sweep-onset proxy): 14/16; near hogline: 11/16
- far hogline: 12/16; stop: 16/16 (anchored search around the known rest
  position recovers stops that blind chaining missed)
- resting position: 16/16 (12 from the arrival-cam dot track, 4 from the
  pre/post house-state diff fallback)

Phase-frame verification (results/phase_sheet_*.jpg, one frame per detected
phase per shot): slide frames show the thrower at/leaving the hack; several
release frames show the stone dot visibly ahead of the thrower (shots 2, 4,
6, 7, 8); stop frames show the stone at its final position. Kinematic gaps
are physically plausible across all shots (release 1.2-3.1 s after slide,
hog-to-hog 9-17 s).

Spot validation against frame review:
- shot 2 slide 82.3 vs ~83 observed; shot 11 slide 507.9 vs ~509;
  shot 15 slide 812.0 vs ~812.6
- shot 1 resting position (46.1, -111.4) in vs hand-measured (47.1, -110.4)
- shot 5 stop at 263.2 confirmed in frames (stone glides 11 s past the
  down-ice motion-segment end — phase 7 must come from the house cam)

Known limitations (v1):
- backline cross (phase 3) not separately observable: the thrower's body
  extends past the backline at setup; it is ~1 s after slide begin
- release (phase 4) is measured via sweep onset, not true handle
  separation: at this resolution the thrower's head/shoulders lead the
  body blob (hiding the stone) and clothing can read as handle-colored
  (a pink jacket produced 100-150 px "red" blobs; real handle/broom dots
  are 1-25 px, so a 30 px area cap separates them). Sweepers engage at
  release, so the proxy carries ~±1 s
- near hog (phase 5) triggers a stone-diameter early: red dots merge with
  the red hogline pixels into one oversized component right at the line
- mid-sheet (between the hoglines, ~72 ft) is unviewed by the house cams
- result positions degrade toward the cam fringe (long guards / through
  stones); takeout tracking of displaced stones is not attempted yet
- positions are where each stone stopped; later shots may move it

## Discarded approaches (for the record)

- *Persistent house-strip pixel change pre/post segment*: fails — neighboring
  shots change the house within any reasonable comparison window, and people
  standing in the house dominate the diff.
- *Stone-handle color detection (HSV red/yellow) for state comparison*: detects
  resting stones well (see stone-count trajectory 0→11 over the end, then 0
  after clearing), but guards stop short of the camera's view (state unchanged)
  and broom heads are stone-colored and stone-sized (travel false positives).
  Still promising as the foundation for future make/miss + shot-type analytics,
  just not as the shot/walk-by discriminator.
