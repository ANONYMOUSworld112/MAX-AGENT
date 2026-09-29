"""Optical Character Recognition (OCR) fallback engine (Level 5)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from PIL import Image

from core.max_infra.kill_switch import KillSwitch

logger = logging.getLogger("max.perception.text_detection")


@dataclass
class TextRegion:
    text: str
    confidence: float
    bounding_box: Tuple[int, int, int, int]  # (left, top, right, bottom)


class TextDetector:
    def __init__(self) -> None:
        self.kill_switch = KillSwitch.get_instance()
        self._tesseract_available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._tesseract_available is None:
            try:
                import pytesseract  # type: ignore
                self._tesseract_available = True
            except ImportError:
                self._tesseract_available = False
        return self._tesseract_available

    def detect_text(self, image: Image.Image) -> List[TextRegion]:
        """Performs OCR detection on the provided image."""
        self.kill_switch.guard()

        if not self.is_available():
            logger.debug("Tesseract OCR not installed; returning empty text regions.")
            return []

        try:
            import pytesseract  # type: ignore
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            regions: List[TextRegion] = []
            n_boxes = len(data["text"])
            for i in range(n_boxes):
                word = data["text"][i].strip()
                conf = float(data["conf"][i])
                if word and conf > 30.0:
                    x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                    regions.append(TextRegion(
                        text=word,
                        confidence=conf / 100.0,
                        bounding_box=(x, y, x + w, y + h),
                    ))
            return regions
        except Exception as exc:
            logger.warning("OCR processing error: %s", exc)
            return []
