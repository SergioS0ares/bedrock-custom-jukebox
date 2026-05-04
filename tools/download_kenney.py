"""Download and extract a Kenney assets ZIP into the frontend assets folder.

Usage:
  python tools/download_kenney.py --url <ZIP_URL>

This script downloads a ZIP file (recommended: a Kenney CC0 pack ZIP URL), extracts
image files (.png, .jpg, .jpeg, .webp) into `frontend/juke-crafter/src/assets/kenney/`,
and writes a LICENSE-assets.txt file that credits Kenney.

Note: provide a direct URL to a ZIP file (e.g. an official Kenney download link or GitHub release asset).
"""
import os
import sys
import argparse
import shutil
import tempfile
from pathlib import Path
import zipfile

try:
    import requests
except Exception:
    print("The 'requests' package is required. Install with: python -m pip install requests")
    raise


OUT_DIR = Path("frontend/juke-crafter/src/assets/kenney").resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)


def download_zip(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} ...")
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(1024 * 64):
            if chunk:
                f.write(chunk)
    print(f"Saved to {dest}")
    return dest


def extract_images(zip_path: Path, out_dir: Path):
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        copied = 0
        for name in names:
            ext = Path(name).suffix.lower()
            if ext in allowed:
                # preserve filename (flat)
                target = out_dir / Path(name).name
                with z.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                copied += 1
        print(f"Extracted {copied} image files to {out_dir}")


def write_license(out_dir: Path, source_url: str):
    txt = (
        "Kenney Assets\n"
        f"Source: {source_url}\n"
        "Suggested credit: Kenney (https://kenney.nl)\n"
        "License: often CC0/public-domain for many packs; verify the pack's page before redistributing.\n"
    )
    path = out_dir / "LICENSE-assets.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"Wrote license file: {path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="Direct URL to a ZIP file (Kenney asset pack)")
    args = p.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="kenney_dl_"))
    try:
        zip_path = tmp / "pack.zip"
        download_zip(args.url, zip_path)
        extract_images(zip_path, OUT_DIR)
        write_license(OUT_DIR, args.url)
        print("Done. You may want to review and pick specific images to reference in the frontend.")
    finally:
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass


if __name__ == "__main__":
    main()
