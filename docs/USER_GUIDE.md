# Drone Mission Review

A tiny tool for mapping geotagged drone photos. Drop in your JPGs and see them
plotted on a map by their GPS coordinates, grouped into projects, with the
flight path drawn between them.

## Getting started (60 seconds)

1. **Download** `drone-mission-review-standalone.html` from Canvas.
2. **Double-click** the file. It opens in your browser. No install. No account.
3. Click **Load sample dataset** in the bottom-left toolbar to explore an
   example flight.
4. To use your own photos, drag a folder onto the dropzone, or click
   **Choose folder**.

That's it. The app runs entirely in your browser — your photos never leave
your computer.

## What it shows you

For every JPG with GPS EXIF tags, you get:

- A colored pin on the map at the photo's coordinates.
- A clickable popup with the thumbnail, GPS, altitude (both relative-to-takeoff
  and absolute), timestamp, and camera info.
- Photos grouped by their parent folder into "projects" — each project gets its
  own color, eye toggle, and dashed flight-path line connecting the photos in
  time order.
- Dense stacks of pins collapse into a numbered cluster that fans out as you
  zoom in.
- Click any photo on the map or in the sidebar and the app draws the
  approximate **ground footprint** of that image — the rectangle on the
  ground that the camera captured. Computed from gimbal yaw, relative
  altitude (height above takeoff), and the 35 mm-equivalent focal length.
  Only shown for near-nadir shots (within 20° of straight-down); strongly
  oblique photos are skipped because flat-ground projection doesn't apply.

- A basemap switcher in the upper-right lets you flip between three styles:
  a street view (Esri World Street Map),
  satellite imagery (Esri World Imagery), and topographic maps
  (USGS National Map — best for terrain context). You can also toggle a
  place-and-road labels overlay on top of the satellite view.

Use **Export CSV** to dump the extracted metadata for downstream analysis.
The file is named `Flights_YYYY-MM-DD.csv`, using the date you export it.
**Export GeoJSON** writes a `.geojson` file containing both photo points and
footprint polygons, ready to drag straight into QGIS or ArcGIS.

## More tricks the toolbar can do

- **Time slider** — a slider appears at the bottom of the map after photos
  load. Drag it to step through the flight chronologically, or hit ▶ to play
  it as a short animation.
- **Show all footprints** — render every photo's footprint at once for a
  coverage view (great for spotting gaps or overlap problems in a mapping
  flight).
- **Refine with terrain** — fetches ground elevations from OpenTopoData and
  re-computes footprints using height above terrain instead of height above
  takeoff. Helpful in hilly areas; needs internet for the one-time fetch.
- **Filter** — the search box above the project list filters by filename,
  and the "GPS only" checkbox hides photos without coordinates.
- **Flight statistics** — click "Flight statistics" in the sidebar to see
  duration, path length, altitude, photo cadence, and total footprint area
  per project and overall.
- **Detect missions** — auto-group photos into separate "missions" using
  time-gap clustering. Click the button, pick a minutes-gap (default 10) and
  a metres-gap (default 500), and consecutive photos exceeding either gap
  start a new mission. Useful when one folder contains several flights from
  the same day, or when you've loaded a whole drive of mixed footage. Click
  **Restore folders** to go back to the original folder-based grouping.

- **Larger photo viewer** — click the thumbnail inside any popup to see the
  full-size photo in a lightbox (works only for photos you uploaded directly;
  index.json datasets show the embedded thumbnail).

The app also remembers your basemap choice and which toggles were on, so
you don't have to set them again next time you open the file.

## Privacy

The app does not upload anything. It loads three JavaScript libraries
(Leaflet, MarkerCluster, exifr) directly inside the HTML file, parses EXIF in
your browser, and only fetches map tiles from OpenStreetMap when you scroll
the map. If you're working offline, EXIF + sidebar still work; the map will
just be blank tiles.

## Sample dataset

The "Load sample dataset" button loads a small flight from two projects so
you can see the UI in action without bringing your own data. The photos are
embedded inside the HTML file.

## For advanced students

## Sorting photos into sensor-type folders

Two ways to physically organize a folder of mixed-sensor photos into
`RGB/`, `Multispectral/`, and `Thermal/` subfolders:

**In the app** — click **Write sensor folders…** in the toolbar. The app
will ask which folder to write into, then drop a copy of each loaded photo
into a subfolder named after its sensor type. This only works in Chrome
or Edge (browsers that support the File System Access API), and only for
photos uploaded directly via drag-drop or Choose folder — index.json-loaded
photos only carry thumbnails, not the original bytes.

**From the command line** (works anywhere Python runs):

```bash
# preview the plan
python3 sort_by_sensor.py /path/to/photos --dry-run

# copy into /path/to/photos_sorted/{RGB,Multispectral,Thermal,Unknown}/
python3 sort_by_sensor.py /path/to/photos

# or write to an explicit output folder
python3 sort_by_sensor.py /path/to/photos -o /somewhere/sorted

# or move (faster, but originals leave the source folder)
python3 sort_by_sensor.py /path/to/photos --move
```

The script copies by default — your originals are safe. Use `--move` to
relocate, or `--symlink` (macOS/Linux) for zero-byte references.

If you want to package a large dataset for instant loading (skipping the
in-browser EXIF parse), use `build_index.py`:

```bash
pip install --user Pillow
python3 build_index.py /path/to/photos -o index.json
```

That walks a folder of drone photos, extracts EXIF + XMP (DJI's
`RelativeAltitude` tag is supported), generates 96-px thumbnails, and writes
a single portable `index.json` file. You can then load it via the
**Load index.json** button in the app.

## Supported photos

- JPEG / TIFF with GPS EXIF (most consumer drones write these by default).
- DJI photos additionally get `RelativeAltitude` from the XMP packet, which is
  the height above takeoff — usually more meaningful than the absolute number.
- Photos without GPS still show up in the sidebar, just without a map pin.

## Troubleshooting

- **Photos appear but no pins on the map** — the photos don't have GPS EXIF.
  Some apps strip GPS on export. Check the sidebar — photos without GPS get a
  red "NO GPS" badge.
- **Map is blank gray squares** — you're offline. The map tiles need internet;
  the rest of the app does not.
- **A tile provider blocks you / shows an error** — try switching basemaps in
  the upper-right (Streets / Satellite / Topo). All three come from different
  hosts; if one is rate-limited on your network, another will usually work.
- **App won't open** — your browser may have downloaded the file as `.html.txt`
  or similar. Rename so the extension is exactly `.html` and try again.

---

Built with Leaflet, Leaflet.markercluster, and exifr. Open in any modern
browser (Chrome, Firefox, Safari, Edge).
