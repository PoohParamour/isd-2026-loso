"""Find and straighten a bright transcript page photographed on a dark screen."""

from __future__ import annotations

import cv2
import numpy as np
import statistics
from PIL import Image, ImageOps


def _page_quad(image: np.ndarray) -> np.ndarray | None:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    # A photographed PDF viewer has a bright page against a dark surround.
    # Close tiny gaps from table rules, but keep the page boundary intact.
    mask = cv2.inRange(gray, 120, 255)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area_ratio = cv2.contourArea(contour) / (width * height)
    if not 0.28 <= area_ratio <= 0.92:
        return None
    perimeter = cv2.arcLength(contour, True)
    polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
    if len(polygon) != 4 or not cv2.isContourConvex(polygon):
        return None
    points = polygon.reshape(4, 2).astype(np.float32)
    # Reject nearly axis-aligned pages: existing OCR profiles are tuned for them.
    edges = [points[(i + 1) % 4] - points[i] for i in range(4)]
    tilt = min(abs(float(np.degrees(np.arctan2(edge[1], edge[0])))) % 90 for edge in edges)
    if tilt < 5:
        return None
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
