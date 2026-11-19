import json
from pathlib import Path

from django.conf import settings

from config.openapi import render_openapi_json


def test_openapi_snapshot_is_in_sync() -> None:
    """Ensure committed docs/architecture/openapi.json matches live Django Ninja schemas."""
    snapshot_path = Path(settings.BASE_DIR).parent / "docs" / "architecture" / "openapi.json"
    assert snapshot_path.is_file(), f"Missing OpenAPI snapshot at {snapshot_path}"
    rendered = render_openapi_json()
    assert snapshot_path.read_text(encoding="utf-8") == rendered

    schema = json.loads(rendered)
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            for code, resp in operation["responses"].items():
                if str(code).startswith(("4", "5")):
                    content = resp.get("content") or {}
                    assert "application/problem+json" in content
                    assert "application/json" not in content
