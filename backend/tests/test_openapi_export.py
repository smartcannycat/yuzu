from pathlib import Path

from django.conf import settings

from config.openapi import render_openapi_json


def test_openapi_snapshot_is_in_sync() -> None:
    """Ensure committed docs/architecture/openapi.json matches live Django Ninja schemas."""
    snapshot_path = Path(settings.BASE_DIR).parent / "docs" / "architecture" / "openapi.json"
    assert snapshot_path.is_file(), f"Missing OpenAPI snapshot at {snapshot_path}"
    assert snapshot_path.read_text(encoding="utf-8") == render_openapi_json()
