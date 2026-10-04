"""Find and straighten a bright transcript page photographed on a dark screen."""

from __future__ import annotations

import cv2
import numpy as np
import statistics
from PIL import Image, ImageOps


def _page_quad(image: np.ndarray) -> np.ndarray | None:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    # Preserve the original crop for strongly rotated pages. Their edges
    # cannot be classified as horizontal/vertical until OCR chooses orientation.
    legacy_mask = cv2.inRange(gray, 120, 255)
    legacy_mask = cv2.morphologyEx(legacy_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    legacy_contours, _ = cv2.findContours(legacy_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if legacy_contours:
        legacy_contour = max(legacy_contours, key=cv2.contourArea)
        legacy = cv2.approxPolyDP(legacy_contour, .02*cv2.arcLength(legacy_contour, True), True)
        if .28 <= cv2.contourArea(legacy_contour)/(width*height) <= .92 and len(legacy) == 4 and cv2.isContourConvex(legacy):
            points = legacy.reshape(4, 2).astype(np.float32)
            angles = [abs(float(np.degrees(np.arctan2(edge[1],edge[0])))) % 90
                      for edge in np.roll(points,-1,axis=0)-points]
            if min(min(angle,90-angle) for angle in angles) > 25:
                return points
    # A photographed PDF viewer has a bright page against a dark surround.
    # Close tiny gaps from table rules, but keep the page boundary intact.
    # Average screen pixels before locating the page. A fixed high threshold
    # cuts away the shaded part of a page and invents a slanted bottom edge.
    smooth = cv2.GaussianBlur(gray, (0, 0), 5)
    threshold, _ = cv2.threshold(smooth, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.inRange(smooth, min(round(threshold), 90), 255)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(contour) / (width * height)
    if not 0.28 <= area_ratio <= 0.92:
        return None
    perimeter = cv2.arcLength(contour, True)
    polygon = cv2.approxPolyDP(contour, 0.003 * perimeter, True)
    # A page crossing the frame has extra corners where it hits the image
    # border. Fit its four real edges and intersect them instead of warping
    # those artificial corners into a rectangle.
    vertices = polygon.reshape(-1, 2).astype(np.float32)
    sides = {}
    center = vertices.mean(axis=0)
    for p, q in zip(vertices, np.roll(vertices, -1, axis=0)):
        if any(abs(float(p[k] - boundary)) < 2 and abs(float(q[k] - boundary)) < 2
               for k, boundary in ((0, 0), (0, width - 1), (1, 0), (1, height - 1))):
            continue
        delta = q - p
        length = float(np.linalg.norm(delta))
        if length < min(width, height) * 0.3:
            continue
        midpoint = (p + q) / 2
        if abs(delta[0]) > abs(delta[1]) * 2:
            key = 'top' if midpoint[1] < center[1] else 'bottom'
        elif abs(delta[1]) > abs(delta[0]) * 2:
            key = 'left' if midpoint[0] < center[0] else 'right'
        else:
            continue
        if key not in sides or length > sides[key][0]:
            sides[key] = (length, np.cross(np.r_[p, 1], np.r_[q, 1]))
    if len(sides) != 4:
        # Keep the established quadrilateral path for pages rotated far from
        # the image axes; horizontal/vertical edge classification is ambiguous
        # there and the independent OCR orientation step follows this warp.
        legacy = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(legacy) == 4 and cv2.isContourConvex(legacy):
            return legacy.reshape(4, 2).astype(np.float32)
        return None
    points = []
    for first, second in [('top', 'left'), ('top', 'right'), ('bottom', 'right'), ('bottom', 'left')]:
        point = np.cross(sides[first][1], sides[second][1])
        if abs(point[2]) < 1e-6:
            return None
        points.append(point[:2] / point[2])
    points = np.array(points, dtype=np.float32)
    if not cv2.isContourConvex(points) or any(
        not (-width * .25 <= x <= width * 1.25 and -height * .25 <= y <= height * 1.25)
        for x, y in points
    ):
        return None
    # A near-upright page still needs its dark viewer surround removed.
    # Full-page scans are excluded above by their area, not by edge angle.
    return points


def _ordered(points: np.ndarray) -> np.ndarray:
    total = points.sum(axis=1)
    diff = np.diff(points, axis=1).ravel()
    return np.array([points[np.argmin(total)], points[np.argmin(diff)],
                     points[np.argmax(total)], points[np.argmax(diff)]], dtype=np.float32)


def straighten_photo(source: Image.Image) -> Image.Image | None:
    """Return a rectified page, or None when there is no clear bright quadrilateral.

    Orientation is chosen by the caller from OCR text so the geometry step does
    not guess which edge of a heavily rotated page is the top.
    """
    image = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
    quad = _page_quad(image)
    if quad is None:
        return None
    tl, tr, br, bl = _ordered(quad)
    width = round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    if min(width, height) < 400:
        return None
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    result = cv2.warpPerspective(image, cv2.getPerspectiveTransform(np.array([tl, tr, br, bl]), target),
                                 (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(result)


def deskew_table(source: Image.Image) -> tuple[Image.Image, float] | None:
    """Straighten a small table tilt only when many long rules agree.

    This does not attempt to undo a perspective warp. The caller keeps the
    original extraction unless the corrected image has stronger structure.
    """
    image = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
    height, width = image.shape[:2]
    if width < 600 or height < 600:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 60, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=120,
                            minLineLength=round(width * 0.3), maxLineGap=30)
    if lines is None:
        return None
    angles = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = float(np.degrees(np.arctan2(int(y2) - int(y1), int(x2) - int(x1))))
        if abs(angle) < 10:
            angles.append(angle)
    if len(angles) < 8:
        return None
    angle = statistics.median(angles)
    if not 0.8 <= abs(angle) <= 4.0:
        return None
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    corrected = cv2.warpAffine(image, matrix, (width, height),
                               flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
    return Image.fromarray(corrected), angle
