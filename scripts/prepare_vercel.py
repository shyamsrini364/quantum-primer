"""Prepare a clean server deployment; does not upload anything."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "reports" / "vercel-stage"


def main():
    manifest = ROOT / "data" / "index.json"
    if not manifest.is_file():
        raise SystemExit("Missing data/index.json. Restore the private library manifest first.")
    STAGE.mkdir(parents=True, exist_ok=True)
    for name in ["src", "web"]:
        shutil.copytree(ROOT / name, STAGE / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    for name in ["app.py", "pyproject.toml", "vercel.json", ".vercelignore"]:
        shutil.copy2(ROOT / name, STAGE / name)
    (STAGE / "data").mkdir(exist_ok=True)
    shutil.copy2(manifest, STAGE / "data" / "index.json")
    print("Prepared reports/vercel-stage. The library is server-only; no .env was copied.")


if __name__ == "__main__":
    main()
