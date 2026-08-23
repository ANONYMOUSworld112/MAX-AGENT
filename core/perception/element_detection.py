"""
MAX OS — Perception Engine: Visual Element Detection Fallback (Priority 4).
Detects buttons, input boxes, icons, and interactive visual regions directly from screenshot images
when structured accessibility trees are unexposed or unavailable.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageFilter, ImageOps

from core.perception.accessibility import ElementDescriptor


class VisualElementDetectionEngine:
    """
    Computer-vision and image-heuristic based visual element detector.
    Identifies high-contrast rectangular interactive components, input boxes,
    and buttons directly from pixel bitmaps.
    """

    def __init__(self, min_element_size: int = 16, max_element_size: int = 800):
        self.min_element_size = min_element_size
        self.max_element_size = max_element_size

    def detect_visual_elements(
        self,
        image: Image.Image,
        base_offset: Tuple[int, int] = (0, 0),
        window_title: str = "",
        app_name: str = "",
    ) -> List[ElementDescriptor]:
        """
        Scans a screenshot or window crop to extract visual element bounding boxes.
        """
        if not image or image.width <= 0 or image.height <= 0:
            return []

        elements: List[ElementDescriptor] = []
        offset_x, offset_y = base_offset

        # Convert to grayscale for contrast & edge analysis
        gray = ImageOps.grayscale(image)
        edges = gray.filter(ImageFilter.FIND_EDGES)

        # Segment image into grid regions and find high-contrast bounding contours
        # For lightweight deterministic operation, scan for rectangular contours
        width, height = gray.size

        # Simple grid-based contrast scanner for button/field candidates
        step_x = max(24, width // 40)
        step_y = max(18, height // 30)

        # Detect candidate rectangular regions
        for y in range(0, height - step_y, step_y):
            for x in range(0, width - step_x, step_x):
                box = (x, y, min(width, x + step_x * 3), min(height, y + step_y * 2))
                crop_edge = edges.crop(box)
                stat = ImageOps.grayscale(crop_edge).getextrema()

                # If region contains significant edge contrast (bounding borders)
                if stat and stat[1] - stat[0] > 100:
                    cand_w = box[2] - box[0]
                    cand_h = box[3] - box[1]

                    if self.min_element_size <= cand_w <= self.max_element_size and self.min_element_size <= cand_h <= self.max_element_size:
                        global_x = offset_x + x
                        global_y = offset_y + y

                        id_seed = f"visual:{app_name}:{window_title}:{global_x},{global_y},{cand_w},{cand_h}"
                        elem_id = f"elem_{hashlib.md5(id_seed.encode('utf-8')).hexdigest()[:8]}"

                        # Infer type from aspect ratio: wide = input or button, square = icon/button
                        aspect = cand_w / max(1, cand_h)
                        elem_type = "button" if 1.0 <= aspect <= 4.0 else ("edit" if aspect > 4.0 else "custom")

                        elements.append(
                            ElementDescriptor(
                                id=elem_id,
                                type=elem_type,
                                text="",
                                role=elem_type,
                                bounds={"x": global_x, "y": global_y, "width": cand_w, "height": cand_h},
                                confidence=0.72,  # Visual fallback carries medium confidence
                                enabled=True,
                                focused=False,
                                interactable=True,
                                source="visual_detection",
                                accessibility_id="",
                                application=app_name,
                                window=window_title,
                            )
                        )

        # Deduplicate overlapping visual boxes
        return self._deduplicate_elements(elements)[:40]

    def _deduplicate_elements(self, elements: List[ElementDescriptor]) -> List[ElementDescriptor]:
        deduped: List[ElementDescriptor] = []
        for elem in elements:
            overlap = False
            for existing in deduped:
                # Check bounding box IoU
                ex = existing.bounds
                bx = elem.bounds
                if abs(ex["x"] - bx["x"]) < 20 and abs(ex["y"] - bx["y"]) < 15:
                    overlap = True
                    break
            if not overlap:
                deduped.append(elem)
        return deduped
