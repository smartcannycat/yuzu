"""Optional OCR fallback for Farpost image-code CAPTCHAs.

The image CAPTCHA is a secondary challenge shown after repeated ALTCHA solves.
It is noisy (digits over a light grid), so this solver is best-effort and is
disabled by default. Deployments that need it can enable it and install the
``tesseract`` binary.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import time
from tempfile import NamedTemporaryFile

from PIL import Image, ImageOps

_DIGITS_RE = re.compile(r"\D+")


class TesseractImageCaptchaSolver:
    """Read digit codes with the local Tesseract binary."""

    def __init__(
        self,
        *,
        command: str = "tesseract",
        timeout_sec: float = 5.0,
        min_digits: int = 3,
        max_digits: int = 6,
    ) -> None:
        self.command = command
        self.timeout_sec = timeout_sec
        self.min_digits = min_digits
        self.max_digits = max_digits

    @property
    def available(self) -> bool:
        return bool(shutil.which(self.command))

    def solve(self, image: bytes, *, deadline: float) -> str | None:
        if not self.available or time.monotonic() >= deadline:
            return None
        try:
            processed = self._preprocess(image)
        except (OSError, ValueError):
            return None
        try:
            with NamedTemporaryFile(suffix=".png") as tmp:
                tmp.write(processed)
                tmp.flush()
                result = subprocess.run(
                    [
                        self.command,
                        tmp.name,
                        "stdout",
                        "--psm",
                        "7",
                        "-c",
                        "tessedit_char_whitelist=0123456789",
                    ],
                    capture_output=True,
                    timeout=self.timeout_sec,
                    check=False,
                )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        code = _DIGITS_RE.sub("", result.stdout.decode("utf-8", errors="ignore"))
        if not self.min_digits <= len(code) <= self.max_digits:
            return None
        return code

    @staticmethod
    def _preprocess(image: bytes) -> bytes:
        with Image.open(io.BytesIO(image)) as source:
            grayscale = source.convert("L")
        grayscale = ImageOps.autocontrast(grayscale)
        width, height = grayscale.size
        scale = 4
        pixels = list(grayscale.get_flattened_data())
        dark = [1 if value < 165 else 0 for value in pixels]
        rows = [sum(dark[y * width : (y + 1) * width]) for y in range(height)]
        cols = [sum(dark[y * width + x] for y in range(height)) for x in range(width)]
        # Remove the long grid lines while keeping the digit strokes.
        for y, count in enumerate(rows):
            if count > width * 0.7:
                for x in range(width):
                    dark[y * width + x] = 0
        for x, count in enumerate(cols):
            if count > height * 0.7:
                for y in range(height):
                    dark[y * width + x] = 0
        cleaned = Image.new("L", (width, height))
        cleaned.putdata([0 if value else 255 for value in dark])
        cleaned = cleaned.resize((width * scale, height * scale), Image.LANCZOS)
        buffer = io.BytesIO()
        cleaned.save(buffer, format="PNG")
        return buffer.getvalue()
