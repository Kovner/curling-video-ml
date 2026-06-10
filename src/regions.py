"""Camera-region layout of the composite livestream frame, as width/height fractions.

Layout (measured on https://www.youtube.com/watch?v=a2EJcV29ido):
  - left:  down-ice camera, one end. Height capped at 0.94 to mask the
           burned-in red wall clock in the bottom-left corner.
  - house: vertical strip with two stacked overhead house cams.
  - right: down-ice camera, other end.
"""

REGIONS = {
    "left": (0.00, 0.42, 0.00, 0.94),   # x0, x1, y0, y1
    "house": (0.42, 0.58, 0.00, 1.00),
    "right": (0.58, 1.00, 0.00, 1.00),
}


def crop(gray, frac):
    h, w = gray.shape[:2]
    x0, x1, y0, y1 = frac
    return gray[int(y0 * h) : int(y1 * h), int(x0 * w) : int(x1 * w)]
