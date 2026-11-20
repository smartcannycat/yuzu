"""Local Tesseract OCR fast-path for printed Aleado chassis-number plaques."""

from __future__ import annotations

import io
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from tempfile import NamedTemporaryFile

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Valid chassis reads: MODEL-CODE-SERIAL (GB5-1025108) or a bare serial
# number. Anything else is passed through as raw for the caller to judge.
_CHASSIS_FORMAT_RE = re.compile(r"^[A-Z0-9]{2,8}-[A-Z0-9]{4,8}$|^\d{4,12}$")
_STRICT_LOCAL_CHASSIS_RE = re.compile(r"^(?:[A-Z0-9]{2,8}-[A-Z0-9]{4,8}|\d{5,12})$")
_INTERNAL_SPACE_RE = re.compile(r"\s+")
_MAX_IMAGE_DIM = 4096
_MAX_IMAGE_PIXELS = 4_000_000


def sanitize_chassis_read(value: str | None) -> tuple[str | None, str | None]:
    """Normalize a raw model output into (frame_id, raw)."""
    raw = _INTERNAL_SPACE_RE.sub("", (value or "").strip().upper()) or None
    if raw is None:
        return None, None
    if _CHASSIS_FORMAT_RE.fullmatch(raw):
        return raw, raw
    return None, raw


@dataclass(frozen=True)
class LocalChassisReadResult:
    """Outcome of local Tesseract chassis OCR before optional Gemini fallback."""

    frame_id: str | None = None
    raw: str | None = None
    confidence: float = 0.0
    duration_ms: int = 0


def _extract_table_bands(gray: Image.Image) -> list[Image.Image]:
    """Extract horizontal text bands inside table borders, padded and upscaled for Tesseract."""
    width, height = gray.size
    pixels = list(gray.get_flattened_data())
    dark_threshold = 110
    border_row_min_dark = int(width * 0.75)
    line_ys = [
        y
        for y in range(height)
        if sum(1 for v in pixels[y * width : (y + 1) * width] if v < dark_threshold)
        >= border_row_min_dark
    ]

    bands_coords: list[tuple[int, int]] = []
    for i in range(len(line_ys) - 1):
        y0 = line_ys[i] + 2
        y1 = line_ys[i + 1] - 1
        if y1 - y0 >= 10:
            bands_coords.append((y0, y1))

    if not bands_coords:
        bands_coords.append((0, height))

    prepared: list[Image.Image] = []
    left = 2 if width > 8 else 0
    right = width - 2 if width > 8 else width
    for y0, y1 in bands_coords[:2]:
        cropped = gray.crop((left, y0, right, y1))
        # Skip low-contrast empty stripes before launching a subprocess.
        band_pixels = list(cropped.get_flattened_data())
        if sum(1 for v in band_pixels if v < 140) < 15:
            continue
        padded = ImageOps.expand(cropped, border=16, fill=255)
        upscaled = padded.resize(
            (padded.width * 3, padded.height * 3),
            Image.Resampling.BICUBIC,
        )
        prepared.append(upscaled)
    return prepared


def _parse_tesseract_tsv(tsv_text: str) -> list[tuple[str, float]]:
    """Extract (token, confidence) pairs from Tesseract TSV stdout."""
    tokens: list[tuple[str, float]] = []
    lines = tsv_text.splitlines()
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) != 12:
            continue
        word = cols[11].strip()
        if not word:
            continue
        try:
            conf = float(cols[10])
        except ValueError:
            continue
        if conf >= 0.0:
            tokens.append((word, conf))
    return tokens


def _best_chassis_from_tokens(
    tokens: list[tuple[str, float]],
    *,
    min_confidence: float,
) -> tuple[str | None, float]:
    """Return a high-confidence valid chassis identifier from TSV tokens, if present."""
    for word, conf in tokens:
        if conf < min_confidence:
            continue
        frame_id, _raw = sanitize_chassis_read(word)
        if (
            frame_id
            and _STRICT_LOCAL_CHASSIS_RE.fullmatch(frame_id)
            and any(ch.isdigit() for ch in frame_id)
        ):
            return frame_id, conf

    if len(tokens) >= 2:
        joined = "".join(word for word, _ in tokens)
        avg_conf = sum(conf for _, conf in tokens) / len(tokens)
        if avg_conf >= min_confidence:
            frame_id, _raw = sanitize_chassis_read(joined)
            if (
                frame_id
                and _STRICT_LOCAL_CHASSIS_RE.fullmatch(frame_id)
                and any(ch.isdigit() for ch in frame_id)
            ):
                return frame_id, avg_conf

    return None, 0.0


class LocalChassisOcrReader:
    """Fast local Tesseract OCR reader for clean printed chassis-number images."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        command: str = "tesseract",
        min_confidence: float = 80.0,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._enabled = enabled
        self._command = command
        self._min_confidence = min_confidence
        self._timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return self._enabled and bool(shutil.which(self._command))

    def _run_tesseract_tsv(self, band_image: Image.Image) -> str | None:
        with NamedTemporaryFile(suffix=".png") as tmp:
            band_image.save(tmp.name, format="PNG")
            try:
                result = subprocess.run(
                    [
                        self._command,
                        tmp.name,
                        "stdout",
                        "--psm",
                        "7",
                        "-c",
                        "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
                        "tsv",
                    ],
                    capture_output=True,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                logger.debug("Local chassis Tesseract execution failed: %s", exc)
                return None
        if result.returncode != 0:
            return None
        return result.stdout.decode("utf-8", errors="ignore")

    def read(self, image_bytes: bytes) -> LocalChassisReadResult | None:
        """Attempt high-confidence local OCR; returns None when Gemini fallback is needed."""
        if not self.available:
            return None

        started_at = time.perf_counter()
        try:
            with Image.open(io.BytesIO(image_bytes)) as src:
                width, height = src.size
                if (
                    width <= 0
                    or height <= 0
                    or width > _MAX_IMAGE_DIM
                    or height > _MAX_IMAGE_DIM
                    or width * height > _MAX_IMAGE_PIXELS
                ):
                    return None
                gray = src.convert("L")
        except (OSError, ValueError, Image.DecompressionBombError):
            return None

        for band in _extract_table_bands(gray):
            tsv = self._run_tesseract_tsv(band)
            if not tsv:
                continue
            tokens = _parse_tesseract_tsv(tsv)
            frame_id, conf = _best_chassis_from_tokens(
                tokens,
                min_confidence=self._min_confidence,
            )
            if frame_id is not None:
                return LocalChassisReadResult(
                    frame_id=frame_id,
                    raw=frame_id,
                    confidence=conf,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
        return None
