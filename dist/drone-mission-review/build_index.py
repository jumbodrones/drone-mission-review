#!/usr/bin/env python3
"""
build_index.py — Build a portable index.json for DroneDB Lite.

Walks a folder of drone photos, extracts EXIF (GPS, altitude, datetime,
camera make/model), generates embedded base64 thumbnails, and writes a
single index.json file that dronedb_lite.html can load instantly via
the "Load index.json" button.

Photos are grouped into "projects" by their top-level subfolder under
the root directory you point this at. Photos directly inside the root
go into a project called "Loose files".

Usage:
    python3 build_index.py <photos_root> [-o index.json] [--thumb-size 96] [--quality 70]

Requires: Pillow  (pip install --user Pillow)
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ExifTags
except ImportError:
    sys.stderr.write("ERROR: Pillow is required. Install with:\n  pip install --user Pillow\n")
    sys.exit(1)


SUPPORTED_EXT = {".jpg", ".jpeg", ".tif", ".tiff"}

# Cache reverse-lookups
_TAG_NAME = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_NAME = {v: k for k, v in ExifTags.GPSTAGS.items()}


def _dms_to_decimal(dms, ref):
    """Convert ((d, m, s)) + 'N'/'S'/'E'/'W' to signed decimal degrees."""
    if not dms:
        return None
    try:
        d, m, s = [float(x) for x in dms]
    except Exception:
        return None
    val = d + m / 60.0 + s / 3600.0
    if ref in ("S", "W"):
        val = -val
    return val


def _safe_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        try:
            return float(v[0]) / float(v[1])
        except Exception:
            return None


def _parse_datetime(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue
    return None


def _find_xmp_value(xmp, key_suffix):
    """Depth-first search the XMP dict tree for any key ending in key_suffix.

    Pillow's getxmp() nests RDF/Description/<field>; DJI tags appear as
    'AbsoluteAltitude', 'RelativeAltitude' under the drone-dji namespace.
    We also tolerate the namespaced 'drone-dji:RelativeAltitude' form just in case.
    """
    if isinstance(xmp, dict):
        for k, v in xmp.items():
            ks = str(k)
            if ks == key_suffix or ks.endswith(":" + key_suffix):
                if isinstance(v, (str, int, float)):
                    return v
            found = _find_xmp_value(v, key_suffix)
            if found is not None:
                return found
    elif isinstance(xmp, list):
        for item in xmp:
            found = _find_xmp_value(item, key_suffix)
            if found is not None:
                return found
    return None


def _parse_signed_float(s):
    """Parse '+19.80', '-177.70', '19.8', or numeric — return float or None."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    try:
        return float(str(s).strip().lstrip("+"))
    except Exception:
        return None


def extract_metadata(img):
    """Return dict with lat, lon, altitudes, datetime, camera info, and the
    fields needed to compute image footprints on the ground.

    absAlt comes from XMP drone-dji:AbsoluteAltitude when available, else EXIF
    GPSAltitude. relAlt comes from XMP drone-dji:RelativeAltitude (DJI-only).

    Footprint fields (all DJI XMP):
      gimbalYaw / gimbalPitch / gimbalRoll  — camera orientation in degrees
      flightYaw                              — drone body heading (fallback for yaw)

    Camera FOV fields (mostly EXIF):
      focalLength  — focal length in mm
      focal35      — 35mm-equivalent focal length in mm (lets us derive FOV
                     without knowing the physical sensor size)
      imgWidth / imgHeight — pixel dimensions, needed for aspect ratio
    """
    out = {
        "lat": None, "lon": None,
        "absAlt": None, "relAlt": None,
        "dateTime": None, "make": "", "model": "",
        "gimbalYaw": None, "gimbalPitch": None, "gimbalRoll": None,
        "flightYaw": None,
        "focalLength": None, "focal35": None,
        "imgWidth": None, "imgHeight": None,
    }
    # Image pixel size — Pillow always knows this
    try:
        out["imgWidth"], out["imgHeight"] = img.size
    except Exception:
        pass

    # ---- EXIF ----
    try:
        raw = img._getexif() or {}
    except Exception:
        raw = {}
    tags = {ExifTags.TAGS.get(k, k): v for k, v in raw.items()}

    out["make"] = str(tags.get("Make", "")).strip("\x00 ").strip()
    out["model"] = str(tags.get("Model", "")).strip("\x00 ").strip()
    out["dateTime"] = (_parse_datetime(tags.get("DateTimeOriginal"))
                       or _parse_datetime(tags.get("DateTimeDigitized"))
                       or _parse_datetime(tags.get("DateTime")))
    # FOV-related EXIF
    out["focalLength"] = _safe_float(tags.get("FocalLength"))
    # PIL/EXIF spec name is "FocalLengthIn35mmFilm"; some tools call it "...Format"
    out["focal35"] = _safe_float(tags.get("FocalLengthIn35mmFilm")
                                  or tags.get("FocalLengthIn35mmFormat"))
    # Prefer EXIF-declared pixel dimensions if present (they reflect the source
    # pixel grid before any orientation flag is applied); fall back to PIL size.
    ew = tags.get("ExifImageWidth")
    eh = tags.get("ExifImageHeight")
    if ew and eh:
        try:
            out["imgWidth"] = int(ew)
            out["imgHeight"] = int(eh)
        except Exception:
            pass

    gps_raw = tags.get("GPSInfo")
    if gps_raw:
        gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_raw.items()}
        out["lat"] = _dms_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
        out["lon"] = _dms_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
        # GPSAltitudeRef is unreliable on DJI; we'll prefer XMP below.
        exif_alt = _safe_float(gps.get("GPSAltitude"))
        if exif_alt is not None:
            out["absAlt"] = exif_alt  # tentative — XMP may overwrite

    # ---- XMP (DJI: AbsoluteAltitude / RelativeAltitude) ----
    try:
        xmp = img.getxmp() if hasattr(img, "getxmp") else None
    except Exception:
        xmp = None
    if xmp:
        abs_alt = _parse_signed_float(_find_xmp_value(xmp, "AbsoluteAltitude"))
        rel_alt = _parse_signed_float(_find_xmp_value(xmp, "RelativeAltitude"))
        if abs_alt is not None:
            out["absAlt"] = abs_alt
        if rel_alt is not None:
            out["relAlt"] = rel_alt
        # Camera (gimbal) and drone-body (flight) orientation, in degrees.
        for k_src, k_dst in [
            ("GimbalYawDegree", "gimbalYaw"),
            ("GimbalPitchDegree", "gimbalPitch"),
            ("GimbalRollDegree", "gimbalRoll"),
            ("FlightYawDegree", "flightYaw"),
        ]:
            val = _parse_signed_float(_find_xmp_value(xmp, k_src))
            if val is not None:
                out[k_dst] = val

    return out


def make_thumbnail(img, size, quality):
    """Return a base64 data URI for a JPEG thumbnail."""
    thumb = img.copy()
    thumb.thumbnail((size, size), Image.LANCZOS)
    if thumb.mode != "RGB":
        thumb = thumb.convert("RGB")
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def project_name_for(path: Path, root: Path) -> str:
    """Top-level subfolder under root, or 'Loose files' if directly in root."""
    rel = path.relative_to(root)
    parts = rel.parts
    return parts[0] if len(parts) > 1 else "Loose files"


def build_index(root: Path, thumb_size: int, quality: int):
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXT and not p.name.startswith(".")
    )
    if not files:
        sys.stderr.write(f"No supported image files under {root}\n")
        return None

    projects: dict[str, list[dict]] = {}
    total = len(files)
    skipped = 0

    for i, path in enumerate(files, 1):
        proj = project_name_for(path, root)
        try:
            with Image.open(path) as img:
                img.load()
                meta = extract_metadata(img)
                thumb = make_thumbnail(img, thumb_size, quality)
        except Exception as e:
            sys.stderr.write(f"  ! Skipped {path.name}: {e}\n")
            skipped += 1
            continue

        photo = {
            "name": path.name,
            "lat": meta["lat"],
            "lon": meta["lon"],
            "absAlt": meta["absAlt"],
            "relAlt": meta["relAlt"],
            "dateTime": meta["dateTime"],
            "make": meta["make"],
            "model": meta["model"],
            # Fields used for image-footprint computation in the app
            "gimbalYaw": meta["gimbalYaw"],
            "gimbalPitch": meta["gimbalPitch"],
            "gimbalRoll": meta["gimbalRoll"],
            "flightYaw": meta["flightYaw"],
            "focalLength": meta["focalLength"],
            "focal35": meta["focal35"],
            "imgWidth": meta["imgWidth"],
            "imgHeight": meta["imgHeight"],
            "thumb": thumb,
        }
        projects.setdefault(proj, []).append(photo)

        if i % 10 == 0 or i == total:
            sys.stderr.write(f"  [{i}/{total}] {proj} :: {path.name}\n")

    index = {
        "version": 1,
        "built": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "projects": [
            {"name": name, "photos": photos}
            for name, photos in projects.items()
        ],
    }
    sys.stderr.write(
        f"\nDone: {total - skipped} photos in {len(projects)} project(s)"
        + (f"; skipped {skipped}\n" if skipped else "\n")
    )
    return index


def main():
    ap = argparse.ArgumentParser(description="Build index.json for DroneDB Lite")
    ap.add_argument("root", help="Folder of drone photos to index")
    ap.add_argument("-o", "--output", default=None,
                    help="Output JSON path (default: <root>/index.json)")
    ap.add_argument("--thumb-size", type=int, default=96,
                    help="Thumbnail edge in px (default 96)")
    ap.add_argument("--quality", type=int, default=70,
                    help="JPEG thumbnail quality 1-95 (default 70)")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    out_path = Path(args.output).expanduser().resolve() if args.output else root / "index.json"

    sys.stderr.write(f"Indexing {root}\n  thumb {args.thumb_size}px, quality {args.quality}\n")
    index = build_index(root, args.thumb_size, args.quality)
    if index is None:
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    size_kb = out_path.stat().st_size / 1024
    sys.stderr.write(f"Wrote {out_path}  ({size_kb:.1f} KB)\n")


if __name__ == "__main__":
    main()
