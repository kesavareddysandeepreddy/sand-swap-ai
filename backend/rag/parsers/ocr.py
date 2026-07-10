"""Pluggable OCR providers for image understanding."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class OCRProvider(ABC):
    """Abstract OCR provider contract."""

    @abstractmethod
    def extract_text(self, image_path: str) -> str:
        """Extract text content from an image file."""
        raise NotImplementedError


class NullOCRProvider(OCRProvider):
    """No-op OCR provider for environments without OCR runtimes."""

    def extract_text(self, image_path: str) -> str:
        return ""


class TesseractOCRProvider(OCRProvider):
    """OCR provider backed by pytesseract."""

    def extract_text(self, image_path: str) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return ""

        try:
            with Image.open(image_path) as image:
                return str(pytesseract.image_to_string(image)).strip()
        except Exception:  # noqa: BLE001
            return ""


class PaddleOCRProvider(OCRProvider):
    """OCR provider backed by PaddleOCR when available."""

    def __init__(self, language: str = "en") -> None:
        self.language = language
        self._engine = None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            return None

        self._engine = PaddleOCR(use_angle_cls=True, lang=self.language)
        return self._engine

    def extract_text(self, image_path: str) -> str:
        engine = self._get_engine()
        if engine is None:
            return ""

        try:
            result = engine.ocr(image_path, cls=True)
        except Exception:  # noqa: BLE001
            return ""

        lines: list[str] = []
        for page in result or []:
            for item in page or []:
                if len(item) < 2:
                    continue
                text = item[1][0] if isinstance(item[1], (tuple, list)) else ""
                if text:
                    lines.append(str(text).strip())
        return "\n".join(line for line in lines if line)


class OCRProviderFactory:
    """Resolve OCR provider by symbolic name."""

    def create(self, provider: str) -> OCRProvider:
        normalized = provider.lower().strip()
        if normalized in {"paddle", "paddleocr"}:
            return PaddleOCRProvider()
        if normalized in {"tesseract", "pytesseract"}:
            return TesseractOCRProvider()
        if normalized in {"none", "null", "disabled"}:
            return NullOCRProvider()
        return TesseractOCRProvider()


def detect_image_language_hint(path: str) -> str:
    """Return language hint from image file path for future OCR routing."""
    suffix = Path(path).suffix.lower()
    return "en" if suffix else "unknown"
