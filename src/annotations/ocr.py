from abc import ABC, abstractmethod
from typing import List, Optional
import shutil
import uuid
import logging
import numpy as np
from annotations.models import OCRResult

logger = logging.getLogger(__name__)


class OCREngine(ABC):
    """Abstract interface for Optical Character Recognition engines."""

    @abstractmethod
    def recognize(self, image: np.ndarray) -> List[OCRResult]:
        """
        Recognize text regions in an engineering drawing image.

        Args:
            image: 2D or 3D numpy array representing the image.

        Returns:
            List of OCRResult objects containing detected text, bounding boxes, and confidence.
        """
        pass

    def is_available(self) -> bool:
        """Check if the OCR engine dependencies are installed and available."""
        return True


class MockOCREngine(OCREngine):
    """
    Mock OCR Engine for deterministic testing and synthetic benchmarking.
    Allows passing predefined OCR results without depending on local models or network.
    """

    def __init__(self, canned_results: Optional[List[OCRResult]] = None):
        self.canned_results = canned_results or []

    def set_results(self, results: List[OCRResult]) -> None:
        self.canned_results = results

    def recognize(self, image: np.ndarray) -> List[OCRResult]:
        return list(self.canned_results)


class FallbackOCREngine(OCREngine):
    """
    Fallback OCR engine for environments lacking native OCR engine binaries (such as Tesseract).
    Per architecture requirements, this implementation does NOT fabricate fake text or fake bounding boxes.
    It returns an empty list and documents the dependency limitation.
    """

    def recognize(self, image: np.ndarray) -> List[OCRResult]:
        logger.warning(
            "FallbackOCREngine active: No local OCR binary (e.g. tesseract) detected. "
            "Returning empty OCR results. Install tesseract-ocr to enable native recognition."
        )
        return []

    def is_available(self) -> bool:
        return True


class TesseractOCREngine(OCREngine):
    """
    Concrete OCR Engine leveraging Tesseract OCR via pytesseract.
    Converts Tesseract bounding boxes and word confidence into standardized OCRResult models.
    """

    def __init__(self):
        self._available = False
        if shutil.which("tesseract") is not None:
            try:
                import pytesseract
                self._available = True
            except ImportError:
                self._available = False

    def is_available(self) -> bool:
        return self._available

    def recognize(self, image: np.ndarray) -> List[OCRResult]:
        if not self.is_available():
            logger.warning("Tesseract binary or pytesseract library unavailable. Falling back to empty result.")
            return []

        import pytesseract

        try:
            # Extract detailed bounding box & confidence data from tesseract
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        except Exception as e:
            logger.error(f"Error during Tesseract recognition: {e}")
            return []

        results: List[OCRResult] = []
        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = data["text"][i].strip()
            conf_str = data["conf"][i]
            try:
                conf = float(conf_str) / 100.0
            except (ValueError, TypeError):
                conf = 0.0

            if text and conf > 0.0:
                x = float(data["left"][i])
                y = float(data["top"][i])
                w = float(data["width"][i])
                h = float(data["height"][i])
                results.append(
                    OCRResult(
                        id=f"ocr_{uuid.uuid4().hex[:8]}",
                        text=text,
                        confidence=round(conf, 3),
                        bounding_box=(x, y, w, h)
                    )
                )

        return results


def get_ocr_engine(engine_name: Optional[str] = None) -> OCREngine:
    """
    Factory to retrieve an OCR engine instance.
    Defaults to Tesseract if available, else gracefully falls back to FallbackOCREngine.
    """
    if engine_name == "mock":
        return MockOCREngine()

    if engine_name == "tesseract":
        return TesseractOCREngine()

    tesseract_engine = TesseractOCREngine()
    if tesseract_engine.is_available():
        return tesseract_engine

    return FallbackOCREngine()
