"""Copy a bank's allowlisted source photos into private, backed-up storage (no database access).

Run with backend/.venv/Scripts/python.exe scripts/import-study-images.py SOURCE_DIRECTORY.
Original bytes are preserved; crops and orientation are applied by the learning viewer.
"""
import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPIC = "2026-10-28-erik-naravoslovje"


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    topic = json.loads((ROOT / f"backend/app/content/data/families/danijel/topics/{TOPIC}.json").read_text(encoding="utf-8"))
    sources = topic["lab"]["sources"]
    missing = [s["file"] for s in sources if not (args.source / s["file"]).is_file()]
    if missing:
        raise SystemExit(f"Missing {len(missing)} photos: {', '.join(missing)}")
    dest = args.data_dir / "files" / "study" / "danijel" / TOPIC
    dest.mkdir(parents=True, exist_ok=True)
    for source in sources:
        shutil.copy2(args.source / source["file"], dest / source["file"])
    print(f"Copied {len(sources)} source photos to private storage: {dest}")


if __name__ == "__main__":
    main()
