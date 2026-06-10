"""Camera-region layout of the composite livestream frame, as width/height fractions.

Layout (measured on https://www.youtube.com/watch?v=a2EJcV29ido):
  - left:      down-ice camera, one end. Height capped at 0.94 to mask the
               burned-in red wall clock in the bottom-left corner.
  - house_top: overhead house cam, top half of the center strip.
  - house_bot: overhead house cam, bottom half (a small band around the seam
               between the two cams is excluded).
  - right:     down-ice camera, other end.
"""

REGIONS = {
    "left": (0.00, 0.42, 0.00, 0.94),   # x0, x1, y0, y1
    "house_top": (0.42, 0.58, 0.00, 0.44),
    "house_bot": (0.42, 0.58, 0.56, 1.00),
    "right": (0.58, 1.00, 0.00, 1.00),
}


def crop(gray, frac):
    h, w = gray.shape[:2]
    x0, x1, y0, y1 = frac
    return gray[int(y0 * h) : int(y1 * h), int(x0 * w) : int(x1 * w)]
