from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from backend.app.config import settings


def _resolve_path(path: str) -> Optional[str]:
    candidate = Path(path)
    if candidate.is_file():
        return str(candidate)
    storage_path = Path(settings.storage_path) / path
    if storage_path.is_file():
        return str(storage_path)
    return None


def _load_image(path: str) -> Optional[np.ndarray]:
    resolved = _resolve_path(path)
    if not resolved:
        return None
    img = cv2.imread(resolved)
    if img is None:
        return None
    return cv2.resize(img, (256, 256))


def compare_images(path1: str, path2: str) -> float:
    """Return similarity score 0-1 using color histogram correlation."""
    img_a = _load_image(path1)
    img_b = _load_image(path2)
    if img_a is None or img_b is None:
        return 0.0

    hist_a = cv2.calcHist([img_a], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hist_b = cv2.calcHist([img_b], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    score = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
    return round(float(max(0.0, min(1.0, score))), 3)


def _first_path(paths: List[str]) -> Optional[str]:
    for path in paths:
        resolved = _resolve_path(path)
        if resolved:
            return resolved
    return None


def compute_similarity_scores(images_by_type: Dict[str, List[str]]) -> Dict[str, Optional[float]]:
    pairs = [
        ("pdp_vs_dsqc", "pdp", "dsqc"),
        ("dsqc_vs_seller", "dsqc", "seller"),
        ("pdp_vs_seller", "pdp", "seller"),
    ]
    scores: Dict[str, Optional[float]] = {}
    for name, type_a, type_b in pairs:
        path_a = _first_path(images_by_type.get(type_a, []))
        path_b = _first_path(images_by_type.get(type_b, []))
        if path_a and path_b:
            scores[name] = compare_images(path_a, path_b)
        else:
            scores[name] = None
    return scores
