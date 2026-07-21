"""Crea deploy-eb.zip compatible con Linux (rutas con /, no \\)."""
import sys
import zipfile
from pathlib import Path

EXCLUDE_DIRS = {"venv", ".venv", "__pycache__", ".git"}
EXCLUDE_FILES = {".env"}
EXCLUDE_SUFFIX = {".db", ".pyc", ".zip"}


def should_skip(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return True
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix in EXCLUDE_SUFFIX:
        return True
    return False


def main():
    if len(sys.argv) != 3:
        print("Uso: python zip_eb.py <carpeta-backend> <archivo.zip>")
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()

    if not root.is_dir():
        print(f"No existe: {root}")
        sys.exit(1)

    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if not path.is_file() or should_skip(path, root):
                continue
            arcname = path.relative_to(root).as_posix()
            zf.write(path, arcname)

    print(f"ZIP creado: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
