"""Development-only geometry probe on unlabeled image pixels."""

from pathlib import Path

import cv2
import numpy as np

from lab10_fastapi.transcript_app.photo_preprocess import _order_corners


def rectify(image: np.ndarray) -> tuple[np.ndarray, dict]:
    height, width = image.shape[:2]
    scale = min(1.0, 1200.0 / max(height, width))
    small = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
        area = cv2.contourArea(contour) / (small.shape[0] * small.shape[1])
        if area < 0.50:
            break
        polygon = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        corners = _order_corners(polygon.reshape(4, 2).astype('float32') / scale)
        tl, tr, br, bl = corners
        top_y = (tl[1] + tr[1]) / 2
        bottom_y = (bl[1] + br[1]) / 2
        left_x = (tl[0] + bl[0]) / 2
        right_x = (tr[0] + br[0]) / 2
        # Require a page-spanning table, not an arbitrary nested box.
        if top_y < height * 0.12 or bottom_y < height * 0.75 or right_x - left_x < width * 0.70:
            continue
        target = np.array([[left_x, top_y], [right_x, top_y],
                           [right_x, bottom_y], [left_x, bottom_y]], dtype='float32')
        motion = float(np.max(np.linalg.norm(corners - target, axis=1)))
        info = {'area': round(area, 3), 'motion': round(motion, 1), 'corners': corners.round().astype(int).tolist()}
        if motion < min(width, height) * 0.005:
            return image, info
        matrix = cv2.getPerspectiveTransform(corners, target)
        corrected = cv2.warpPerspective(image, matrix, (width, height),
                                        flags=cv2.INTER_CUBIC,
                                        borderMode=cv2.BORDER_CONSTANT,
                                        borderValue=(255, 255, 255))
        return corrected, info
    return image, {'area': None, 'motion': 0}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / 'all/Lab5_transcript_dataset/images/augmented/th/71010001_aug1_rotate_bright.png',
        root / 'all/Lab5_transcript_dataset/images/augmented/th/71010001_aug4_perspective.png',
        root / 'all/Lab5_transcript_dataset/images/augmented/th/71010009_aug4_perspective.png',
        root / 'all/Lab5_transcript_dataset/images/original/th/71010001.png',
    ]
    for path in paths:
        image = cv2.imread(str(path))
        corrected, info = rectify(image)
        target = root / 'tmp' / f'{path.stem}-table-rectified.png'
        cv2.imwrite(str(target), corrected)
        print(path.name, info, target)
