from __future__ import annotations

from io import StringIO
from pathlib import Path
import tokenize


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCANNED_DIRS = ("src", "tests", "scripts", "alembic")


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for relative_dir in SCANNED_DIRS:
        base_dir = PROJECT_ROOT / relative_dir
        if not base_dir.exists():
            continue
        files.extend(sorted(base_dir.rglob("*.py")))
    return files


def _find_any_tokens(path: Path) -> list[str]:
    matches: list[str] = []
    source = path.read_text(encoding="utf-8")
    for token in tokenize.generate_tokens(StringIO(source).readline):
        if token.type == tokenize.NAME and token.string == "Any":
            relative_path = path.relative_to(PROJECT_ROOT)
            matches.append(f"{relative_path}:{token.start[0]}")
    return matches


def test_project_contains_no_any_tokens() -> None:
    matches: list[str] = []
    for path in _iter_python_files():
        matches.extend(_find_any_tokens(path))

    assert not matches, "Présence interdite de `Any` dans le code Python du projet :\n" + "\n".join(matches)
