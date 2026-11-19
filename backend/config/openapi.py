"""Export or verify the live Django Ninja OpenAPI 3.1 schema snapshot."""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_HEX_SUFFIX_RE = re.compile(r"_[0-9a-f]{8}$")


def _default_output_path() -> Path:
    backend_dir = Path(__file__).resolve().parent.parent
    return backend_dir.parent / "docs" / "architecture" / "openapi.json"


def _stabilize_operation_ids(schema: dict[str, Any]) -> None:
    """Replace Ninja Extra's PYTHONHASHSEED-dependent hex suffix with deterministic IDs."""
    seen: set[str] = set()
    for path_key in sorted(schema.get("paths", {})):
        path_item = schema["paths"][path_key]
        if not isinstance(path_item, dict):
            continue
        for method in sorted(path_item):
            operation = path_item[method]
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            raw_id = str(operation["operationId"])
            base_id = _HEX_SUFFIX_RE.sub("", raw_id)
            candidate = base_id
            if candidate in seen:
                digest = hashlib.sha256(f"{method}:{path_key}".encode()).hexdigest()[:8]
                candidate = f"{base_id}_{digest}"
            seen.add(candidate)
            operation["operationId"] = candidate


def _rewrite_problem_detail_media_types(schema: dict[str, Any]) -> None:
    """Use RFC 7807 application/problem+json media type for 4xx/5xx ProblemDetail responses."""
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses")
            if not isinstance(responses, dict):
                continue
            for status_code, response_spec in responses.items():
                if not str(status_code).startswith(("4", "5")) or not isinstance(
                    response_spec, dict
                ):
                    continue
                content = response_spec.get("content")
                if not isinstance(content, dict) or "application/json" not in content:
                    continue
                json_media = content["application/json"]
                if (
                    isinstance(json_media, dict)
                    and json_media.get("schema", {}).get("$ref")
                    == "#/components/schemas/ProblemDetail"
                ):
                    content["application/problem+json"] = content.pop("application/json")


def render_openapi_json() -> str:
    """Bootstrap Django settings and serialize the current Ninja OpenAPI schema."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
    import django

    django.setup()
    from config.api import api

    schema = api.get_openapi_schema()
    _stabilize_operation_ids(schema)
    _rewrite_problem_detail_media_types(schema)
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export or verify Yuzu OpenAPI schema.")
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output_path(),
        help="Target JSON path (defaults to ../docs/architecture/openapi.json).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the target snapshot differs from the live schema.",
    )
    args = parser.parse_args(argv)
    rendered = render_openapi_json()

    if args.check:
        if not args.output.is_file():
            sys.stderr.write(f"OpenAPI snapshot missing: {args.output}\n")
            return 1
        if args.output.read_text(encoding="utf-8") != rendered:
            sys.stderr.write(
                f"OpenAPI snapshot is out of date at {args.output}. Run `make openapi` to update.\n"
            )
            return 1
        sys.stdout.write(f"OpenAPI snapshot is up to date: {args.output}\n")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(f"Exported OpenAPI schema to {args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
