#!/usr/bin/env python3
"""
sort_by_sensor.py — Organize a folder of drone photos into RGB / Multispectral
/ Thermal / Unknown subfolders based on EXIF, XMP, and filename heuristics.

Safe by default: COPIES files rather than moving them, and supports --dry-run
to preview the plan without touching disk. Use --move to physically relocate
files instead. Use --symlink for an organized view without duplicating bytes.

Examples
--------
Preview what would happen:
    python3 sort_by_sensor.py ~/Photos/MyFlight --dry-run

Copy into ~/Photos/MyFlight_sorted/{RGB,Multispectral,Thermal,Unknown}/:
    python3 sort_by_sensor.py ~/Photos/MyFlight

Same but write to an explicit output folder:
    python3 sort_by_sensor.py ~/Photos/MyFlight -o ~/SortedOutput

Move (not copy) — fastest, but original folder is emptied:
    python3 sort_by_sensor.py ~/Photos/MyFlight --move

Make symlinks (zero-byte references; works on macOS/Linux):
    python3 sort_by_sensor.py ~/Photos/MyFlight --symlink

This script depends on Pillow only for reading XMP BandName from DJI
multispectral photos. If Pillow isn't installed, the script still works using
filename and EXIF-Model heuristics — it just can't read the XMP band field.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# ----- Optional Pillow import. Without it we just skip XMP BandName reads. -----
try:
    from PIL import Image, ExifTags  # type: ignore
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


SUPPORTED_EXT = {".jpg", ".jpeg", ".tif", ".tiff"}

_THERMAL_MODELS = (
    "FC4382", "FC4381", "FC4380", "FC350",
    "H20T", "H20N", "XT2", "XTR", "XT",
    "ZENMUSE H20T", "ZENMUSE XT2", "ZENMUSE XT",
    "FLIR", "TAU", "BOSON", "VUE PRO",
    "M3T", "MAVIC 3 THERMAL",
)
_MULTISPECTRAL_MODELS = (
    "FC4396", "FC6310M",
    "P4M", "P4 MULTISPECTRAL", "P4MULTISPECTRAL",
    "ALTUM", "ALTUM-PT", "REDEDGE", "RED-EDGE", "RED EDGE",
    "MICASENSE", "SEQUOIA", "PARROT SEQUOIA",
    "MS600", "MS600 PRO",
    "M3M", "MAVIC 3 MULTISPECTRAL",
)


def _read_image_metadata(path: Path) -> tuple[str, str, str]:
    """Return (make, model, bandName). Empty strings if anything fails."""
    if not _HAS_PIL:
        return "", "", ""
    try:
        with Image.open(path) as img:
            raw = img._getexif() or {}
            tags = {ExifTags.TAGS.get(k, k): v for k, v in raw.items()}
            make = str(tags.get("Make", "")).strip("\x00 ").strip()
            model = str(tags.get("Model", "")).strip("\x00 ").strip()
            band = ""
            try:
                xmp = img.getxmp() if hasattr(img, "getxmp") else None
            except Exception:
                xmp = None
            if xmp:
                band = _find_xmp_band(xmp) or ""
            return make, model, band
    except Exception:
        return "", "", ""


def _find_xmp_band(obj):
    """Depth-first search of the XMP dict for any key ending in 'BandName'."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k) == "BandName" or str(k).endswith(":BandName"):
                if isinstance(v, (str, int, float)):
                    return str(v).strip()
            found = _find_xmp_band(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_xmp_band(item)
            if found:
                return found
    return None


def classify_sensor(filename: str, make: str, model: str, band_name: str = "") -> str:
    """Bucket a photo into 'RGB' / 'Multispectral' / 'Thermal' / 'Unknown'."""
    f = (filename or "").lower()
    m = (model or "").upper()
    mk = (make or "").upper()
    bn = (band_name or "").lower()

    # Check multispectral suffixes FIRST — they're more specific and would
    # otherwise be caught by the broader thermal substring fallback below
    # (e.g. "nir.tif" wrongly matching the old "ir.tif" rule).
    ms_bands = ("_g.tif", "_g.tiff", "_r.tif", "_r.tiff",
                "_re.tif", "_re.tiff", "_nir.tif", "_nir.tiff",
                "_red.tif", "_green.tif", "_blue.tif",
                "_rededge.tif", "_red-edge.tif")
    if any(f.endswith(s) for s in ms_bands):
        return "Multispectral"
    if any(f.endswith(s) for s in ("_t.jpg", "_t.jpeg", "_t.tif", "_t.tiff",
                                    "_thm.jpg", "_thm.jpeg", "_thermal.jpg",
                                    "_thermal.tif", "_thermal.tiff",
                                    "_ir.tif", "_ir.tiff")):
        return "Thermal"
    if "thermal" in f or "r-jpeg" in f or "rjpeg" in f:
        return "Thermal"
    if any(f.endswith(s) for s in ("_rgb.jpg", "_rgb.jpeg", "_d.jpg", "_d.jpeg")):
        return "RGB"

    if bn:
        if "thermal" in bn or "lwir" in bn or bn == "ir":
            return "Thermal"
        return "Multispectral"

    for code in _THERMAL_MODELS:
        if code in m:
            return "Thermal"
    for code in _MULTISPECTRAL_MODELS:
        if code in m:
            return "Multispectral"

    if f.endswith((".jpg", ".jpeg")) and ("DJI" in mk or m.startswith("FC")):
        return "RGB"
    if f.endswith((".jpg", ".jpeg")):
        return "RGB"
    return "Unknown"


def transfer(src: Path, dst: Path, mode: str):
    """mode is 'copy', 'move', 'symlink', or 'dry'."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "dry":
        return
    if dst.exists():
        # Add a numeric suffix so we never overwrite. Keeps the operation safe.
        stem, suf = dst.stem, dst.suffix
        i = 1
        while True:
            cand = dst.with_name(f"{stem}__{i}{suf}")
            if not cand.exists():
                dst = cand
                break
            i += 1
    if mode == "copy":
        shutil.copy2(src, dst)
    elif mode == "move":
        shutil.move(str(src), str(dst))
    elif mode == "symlink":
        # Use absolute path so symlinks survive even if user later moves the
        # sorted folder around.
        dst.symlink_to(src.resolve())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("source", help="Folder of drone photos to sort")
    ap.add_argument("-o", "--out", default=None,
                    help="Output folder for sorted subfolders (default: <source>_sorted)")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--copy", action="store_true",
                     help="(default) Copy files into the sorted subfolders")
    grp.add_argument("--move", action="store_true",
                     help="Move files instead of copying (originals leave the source folder)")
    grp.add_argument("--symlink", action="store_true",
                     help="Create symlinks instead of copies (saves disk space; macOS/Linux only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the plan but don't touch the disk")
    ap.add_argument("--recursive", action="store_true",
                    help="Recurse into subfolders of the source")
    args = ap.parse_args()

    src = Path(args.source).expanduser().resolve()
    if not src.is_dir():
        sys.exit(f"Not a directory: {src}")

    out = (Path(args.out).expanduser().resolve()
           if args.out else src.with_name(src.name + "_sorted"))

    if args.move:        mode = "move"
    elif args.symlink:   mode = "symlink"
    else:                mode = "copy"
    if args.dry_run:
        mode = "dry"

    iterator = src.rglob("*") if args.recursive else src.iterdir()
    files = sorted(p for p in iterator
                   if p.is_file()
                   and p.suffix.lower() in SUPPORTED_EXT
                   and not p.name.startswith("."))
    if not files:
        sys.exit(f"No image files found under {src}")

    sys.stderr.write(f"Source: {src}\n")
    sys.stderr.write(f"Output: {out}\n")
    sys.stderr.write(f"Mode:   {mode.upper()}"
                     + (" (no disk writes)" if mode == "dry" else "")
                     + ("  [Pillow available — full XMP support]" if _HAS_PIL
                        else "  [Pillow missing — using filename + EXIF model only]") + "\n\n")

    counts = {"RGB": 0, "Multispectral": 0, "Thermal": 0, "Unknown": 0}
    for i, path in enumerate(files, 1):
        # Empty-file safety: PIL chokes on 0-byte stubs, classify by filename only
        if path.stat().st_size == 0:
            label = classify_sensor(path.name, "", "", "")
        else:
            make, model, band = _read_image_metadata(path)
            label = classify_sensor(path.name, make, model, band)
        counts[label] = counts.get(label, 0) + 1
        target = out / label / path.name
        rel = path.relative_to(src) if args.recursive else path.name
        action = {"copy": "→", "move": "»", "symlink": "↪", "dry": "·"}[mode]
        sys.stderr.write(f"  {action} {label:<13}  {rel}\n")
        try:
            transfer(path, target, mode)
        except Exception as e:
            sys.stderr.write(f"    ! FAILED: {e}\n")

    sys.stderr.write("\nSummary:\n")
    total = sum(counts.values())
    for label, n in counts.items():
        if n:
            sys.stderr.write(f"  {label:<13} {n:>4}  ({100*n/total:5.1f}%)\n")
    if not args.dry_run:
        past = {"copy": "copied", "move": "moved", "symlink": "symlinked"}[mode]
        sys.stderr.write(f"\nDone. {total} files {past} into {out}\n")
    else:
        sys.stderr.write(f"\nDRY RUN — no files were changed.\n")


if __name__ == "__main__":
    main()
