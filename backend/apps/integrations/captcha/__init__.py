"""Anti-bot challenge solvers shared by scraper integrations."""

from apps.integrations.captcha.altcha import (
    AltchaChallenge,
    AltchaError,
    AltchaSolution,
    AltchaSolveTimeoutError,
    AltchaUnsupportedAlgorithmError,
    build_altcha_payload,
    solve_altcha,
    solve_altcha_payload,
)
from apps.integrations.captcha.farpost import (
    FarpostCaptchaError,
    FarpostCaptchaSolver,
    FarpostChallengePage,
    is_farpost_challenge_response,
    parse_farpost_challenge,
)
from apps.integrations.captcha.image import TesseractImageCaptchaSolver

__all__ = [
    "AltchaChallenge",
    "AltchaError",
    "AltchaSolution",
    "AltchaSolveTimeoutError",
    "AltchaUnsupportedAlgorithmError",
    "FarpostCaptchaError",
    "FarpostCaptchaSolver",
    "FarpostChallengePage",
    "TesseractImageCaptchaSolver",
    "build_altcha_payload",
    "is_farpost_challenge_response",
    "parse_farpost_challenge",
    "solve_altcha",
    "solve_altcha_payload",
]
