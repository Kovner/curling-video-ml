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
