# Drone Mission Review

A single-file, offline-capable web app for mapping and organizing drone photos.
Drop your JPGs in and the app plots them on a map, groups them into missions,
detects RGB / Multispectral / Thermal sensors from EXIF metadata, computes
image ground footprints, and can write sorted subfolders back to disk.

Everything runs in the browser. No install. No account. Your photos never
leave your machine.

Built for teaching and small-scale field work; the entire runtime is a single
HTML file with Leaflet, MarkerCluster, and exifr inlined.

## Try it

**Open the app:** <https://jumbodrones.github.io/drone-mission-review/>

- Works in any modern browser (Chrome, Firefox, Safari, Edge). Nothing to
  install, and your photos stay on your computer.
- Click **Load sample dataset** in the toolbar to explore with 43 sample photos
  from a Mavic 3 mapping flight.
- Then drop your own JPGs on the sidebar and go.
- For **Write sensor folders**, use Chrome or Edge.

**Working offline?** Download
[drone-mission-review_v17.zip](https://github.com/jumbodrones/drone-mission-review/raw/main/dist/drone-mission-review_v17.zip),
unzip it, and double-click `drone-mission-review.html`.

## Features

**Map and visualisation**

- Three switchable basemaps: streets (Esri World Street Map), satellite (Esri World
  Imagery), and topographic (USGS National Map)
- Auto-zoom to the extent of loaded photos
- Marker clustering that breaks apart into individual direction-arrow markers
  at high zoom
- Time-ordered flight-path polylines per project
- Image ground-footprint polygons computed from gimbal yaw, altitude, and
  35 mm-equivalent focal length

**Photo grouping**

- **By folder** (default) — one project per source subfolder
- **By mission** — time-gap clustering with configurable thresholds
- **By sensor type** — automatic RGB / Multispectral / Thermal detection

**Data management**

- Search / filter by filename and GPS presence
- Flight statistics: duration, path length, speed, altitude range, area covered
- Timeline scrubber to play a flight back chronologically
- Export CSV and GeoJSON (points + footprints) for QGIS / ArcGIS
- Terrain-refined footprint heights via OpenTopoData (global) or USGS EPQS (US)
- Sort photos into `RGB/`, `Multispectral/`, `Thermal/` subfolders on disk

**Everything else**

- All processing client-side — no server, no upload
- Works offline (map tiles need internet, everything else does not)
- Persistent UI state (basemap choice, toggles) via `localStorage`
- Full-size photo lightbox for directly-uploaded files

## Documentation

- **[User Guide](docs/USER_GUIDE.md)** — for people using the app
- **[Hosting Guide](docs/HOSTING.md)** — for people deploying it (GitHub
  Pages, Netlify, institutional hosting)

## Repository layout

    README.md               this file
    LICENSE                 MIT
    docs/
      USER_GUIDE.md         end-user documentation
      HOSTING.md            deployment instructions
    src/
      drone-mission-review.html     the source app (uses CDN libraries)
      build_index.py        pre-build an index.json from a photo folder
      sort_by_sensor.py     copy/move photos into sensor-named subfolders
      _build_standalone.py  bundle inline JS/CSS + sample data into dist/
    dist/
      drone-mission-review-standalone.html         built, self-contained app
      drone-mission-review_v*.zip   student-facing zip bundles
    archive/                older bundles kept for reference

## Building from source

Requires Python 3.9+ and Node.js only for the build step (not at runtime).

```bash
# One-time: install the JS libraries the standalone inlines
mkdir -p ../outputs/libs && cd ../outputs/libs && npm init -y
npm install leaflet@1.9.4 leaflet.markercluster@1.5.3 exifr@7.1.3
cd -

# Bundle
python3 src/_build_standalone.py

# Result: dist/drone-mission-review-standalone.html
```

The build script inlines Leaflet, Leaflet.markercluster, and exifr from
`node_modules`, and embeds a sample dataset (see `src/_build_standalone.py`
for paths) as a `<script type="application/json">` block.

To pre-build a class dataset that students can browse instantly (no in-browser
EXIF parse):

```bash
pip install --user Pillow
python3 src/build_index.py /path/to/photos -o /path/to/photos/index.json
```

## Supported cameras

Any camera that writes GPS + timestamp EXIF works for map placement. The
sensor-type classifier and footprint math are tuned for DJI's file naming
and XMP conventions, and the following model codes are recognised:

- Thermal: FC4382 (Mavic 3T), FC350 (H20T), XT2, XTR, XT, FLIR Tau/Boson/Vue Pro
- Multispectral: FC4396 (Mavic 3M), FC6310M (P4M), MicaSense Altum / RedEdge,
  Parrot Sequoia, MS600 Pro

Everything else is treated as RGB or Unknown; footprints still work as long
as the file carries `FocalLengthIn35mmFilm`, image dimensions, and GPS.

## License

MIT — see [LICENSE](LICENSE).
