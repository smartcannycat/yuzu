#!/usr/bin/env python3
"""Cross-service architecture boundary checks for ML domain and frontend stores/types."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

FORBIDDEN_ML_LAYERS = frozenset({"api", "factories", "infrastructure", "services"})
_TS_EXTENSIONS = (".ts", ".mts", ".js", ".mjs", ".vue")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_IMPORT_FROM_RE = re.compile(
    r"""(?:^|;)\s*(?:import|export)\s+(?:type\s+)?"""
    r"""(?:\*\s+as\s+[\w$]+|\{[^}]*\}|[\w$]+(?:\s*,\s*(?:\{[^}]*\}|\*\s+as\s+[\w$]+))?|\*)"""
    r"""\s+from\s+['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_SIDE_EFFECT_IMPORT_RE = re.compile(r"""(?:^|;)\s*import\s+['"]([^'"]+)['"]""", re.MULTILINE)
_DYNAMIC_IMPORT_RE = re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)""")


def _resolve_relative_ml_parts(
    file_path: Path,
    repo_root: Path,
    level: int,
    module: str | None,
) -> list[str]:
    """Resolve a relative Python import inside `ml_service/domains/` relative to `repo_root`."""
    rel_parts = file_path.relative_to(repo_root).parts
    package_parts = list(rel_parts[:-1])
    ascend = level - 1
    if ascend > len(package_parts):
        return []
    base_parts = package_parts[: len(package_parts) - ascend]
    if module:
        base_parts.extend(module.split("."))
    return base_parts


def _is_forbidden_ml_target(parts: list[str]) -> bool:
    if not parts:
        return False
    if parts[0] in FORBIDDEN_ML_LAYERS:
        return True
    return len(parts) >= 2 and parts[0] == "ml_service" and parts[1] in FORBIDDEN_ML_LAYERS


def _check_ml_import_from(
    node: ast.ImportFrom,
    py_file: Path,
    repo_root: Path,
    rel_display: Path,
) -> list[str]:
    if node.level > 0:
        parts = _resolve_relative_ml_parts(py_file, repo_root, node.level, node.module)
        if _is_forbidden_ml_target(parts):
            target = f"{'.' * node.level}{node.module or ''}"
            return [
                f"{rel_display}:{node.lineno}: forbidden relative ML domain import from '{target}'"
            ]
        if parts == ["ml_service"]:
            return [
                f"{rel_display}:{node.lineno}: forbidden relative ML domain import "
                f"'ml_service.{alias.name}'"
                for alias in node.names
                if alias.name in FORBIDDEN_ML_LAYERS
            ]
        return []

    if not node.module:
        return []
    parts = node.module.split(".")
    if _is_forbidden_ml_target(parts):
        return [f"{rel_display}:{node.lineno}: forbidden ML domain import from '{node.module}'"]
    if node.module == "ml_service":
        return [
            f"{rel_display}:{node.lineno}: forbidden ML domain import 'ml_service.{alias.name}'"
            for alias in node.names
            if alias.name in FORBIDDEN_ML_LAYERS
        ]
    return []


def _check_ml_file_imports(py_file: Path, repo_root: Path) -> list[str]:
    rel_display = py_file.relative_to(repo_root)
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(rel_display))
    except SyntaxError as exc:
        return [f"{rel_display}:{exc.lineno}: syntax error: {exc.msg}"]

    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            errors.extend(
                f"{rel_display}:{node.lineno}: forbidden ML domain import '{alias.name}'"
                for alias in node.names
                if _is_forbidden_ml_target(alias.name.split("."))
            )
        elif isinstance(node, ast.ImportFrom):
            errors.extend(_check_ml_import_from(node, py_file, repo_root, rel_display))
    return errors


def check_ml_domain_boundaries(repo_root: Path) -> list[str]:
    """Verify `ml_service/domains/` has zero imports from outer ML service layers."""
    domains_dir = repo_root / "ml_service" / "domains"
    if not domains_dir.is_dir():
        return [f"Missing ML domains directory: {domains_dir}"]

    py_files = sorted(domains_dir.rglob("*.py"))
    if not py_files:
        return [f"No Python files found under {domains_dir}"]

    errors: list[str] = []
    for py_file in py_files:
        errors.extend(_check_ml_file_imports(py_file, repo_root))
    return errors


def _strip_js_comments(source: str) -> str:
    without_blocks = _BLOCK_COMMENT_RE.sub("", source)
    return _LINE_COMMENT_RE.sub("", without_blocks)


def _extract_ts_specifiers(source: str) -> list[str]:
    cleaned = _strip_js_comments(source)
    specifiers: list[str] = []
    for pattern in (_IMPORT_FROM_RE, _SIDE_EFFECT_IMPORT_RE, _DYNAMIC_IMPORT_RE):
        specifiers.extend(pattern.findall(cleaned))
    return specifiers


def _is_runtime_store_file(path: Path) -> bool:
    name = path.name
    if name.endswith(".d.ts") or ".test." in name or ".spec." in name:
        return False
    return path.suffix in _TS_EXTENSIONS


def _resolve_ts_import(specifier: str, importer: Path, frontend_src: Path) -> Path | None:
    if specifier.startswith("@/"):
        candidate_base = (frontend_src / specifier[2:]).resolve()
    elif specifier.startswith("."):
        candidate_base = (importer.parent / specifier).resolve()
    else:
        return None

    candidates: list[Path] = [candidate_base]
    if candidate_base.suffix not in _TS_EXTENSIONS:
        candidates.extend(Path(f"{candidate_base}{ext}") for ext in _TS_EXTENSIONS)
        candidates.extend((candidate_base / f"index{ext}") for ext in _TS_EXTENSIONS)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _find_cycles(graph: dict[Path, list[Path]]) -> list[list[Path]]:
    state: dict[Path, int] = {}  # 0=unvisited, 1=visiting, 2=visited
    stack: list[Path] = []
    cycles: list[list[Path]] = []
    seen_signatures: set[tuple[Path, ...]] = set()

    def dfs(node: Path) -> None:
        state[node] = 1
        stack.append(node)
        for neighbor in graph.get(node, ()):
            neighbor_state = state.get(neighbor, 0)
            if neighbor_state == 1:
                idx = stack.index(neighbor)
                cycle = [*stack[idx:], neighbor]
                canonical = tuple(sorted(cycle[:-1]))
                if canonical not in seen_signatures:
                    seen_signatures.add(canonical)
                    cycles.append(cycle)
            elif neighbor_state == 0:
                dfs(neighbor)
        stack.pop()
        state[node] = 2

    for node in sorted(graph):
        if state.get(node, 0) == 0:
            dfs(node)
    return cycles


def check_frontend_architecture(repo_root: Path) -> list[str]:
    """Verify acyclic `frontend/src/stores/` imports and OpenAPI SSOT import in `types/lots.ts`."""
    frontend_src = (repo_root / "frontend" / "src").resolve()
    stores_dir = frontend_src / "stores"
    if not stores_dir.is_dir():
        return [f"Missing frontend stores directory: {stores_dir}"]

    store_files = sorted(
        path.resolve()
        for path in stores_dir.rglob("*")
        if path.is_file() and _is_runtime_store_file(path)
    )
    if not store_files:
        return [f"No runtime store modules found under {stores_dir}"]

    store_set = set(store_files)
    graph: dict[Path, list[Path]] = {store_file: [] for store_file in store_files}

    for store_file in store_files:
        source = store_file.read_text(encoding="utf-8")
        neighbors: list[Path] = []
        for specifier in _extract_ts_specifiers(source):
            resolved = _resolve_ts_import(specifier, store_file, frontend_src)
            if resolved is not None and resolved in store_set and resolved not in neighbors:
                neighbors.append(resolved)
        graph[store_file] = sorted(neighbors)

    errors: list[str] = []
    for cycle in _find_cycles(graph):
        formatted = " -> ".join(str(path.relative_to(repo_root.resolve())) for path in cycle)
        errors.append(f"Circular store import detected: {formatted}")

    generated_types = (frontend_src / "types" / "api.generated.ts").resolve()
    lots_types = (frontend_src / "types" / "lots.ts").resolve()
    if not generated_types.is_file():
        errors.append(f"Missing generated OpenAPI types file: {generated_types}")
    if not lots_types.is_file():
        errors.append(f"Missing frontend lot types file: {lots_types}")
    else:
        lots_source = lots_types.read_text(encoding="utf-8")
        resolved_targets = {
            _resolve_ts_import(spec, lots_types, frontend_src)
            for spec in _extract_ts_specifiers(lots_source)
        }
        if generated_types not in resolved_targets:
            errors.append(
                "frontend/src/types/lots.ts must import types from '@/types/api.generated'"
            )

    return errors


def run_checks(repo_root: Path) -> int:
    """Execute all cross-service architecture checks and return exit status."""
    resolved_root = repo_root.resolve()
    errors = [
        *check_ml_domain_boundaries(resolved_root),
        *check_frontend_architecture(resolved_root),
    ]
    if errors:
        for error in errors:
            sys.stderr.write(f"ERROR: {error}\n")
        return 1

    sys.stdout.write(
        "Architecture checks passed: ml_service/domains isolated, "
        "frontend/src/stores acyclic, frontend/src/types/lots.ts uses api.generated.\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    default_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Verify ML domain and frontend store/type architecture boundaries."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root,
        help="Repository root directory (defaults to parent of scripts/).",
    )
    args = parser.parse_args(argv)
    return run_checks(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
