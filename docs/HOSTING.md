# Hosting Drone Mission Review

The whole app is a single 419 KB self-contained HTML file — everything
(Leaflet, MarkerCluster, exifr, the sample dataset) is inlined. You can
host it anywhere that serves static files.

This guide covers four common deployment paths, plus one critical caveat
about HTTPS.

---

## Option 1 — GitHub Pages (recommended for public class use)

Free, permanent URL, updates by push. Best if the repo is already on GitHub.

1. Push this repo to GitHub if it isn't there yet.
2. In the repo, go to **Settings → Pages → Build and deployment**.
3. Set **Source** to *Deploy from a branch*.
4. Set **Branch** to `main` and **Folder** to `/` (root) or `/docs` — see below.
5. Copy the standalone file so Pages can serve it as `index.html`:

   ```bash
   # Option A: serve from repo root
   cp dist/drone-mission-review-standalone.html index.html
   git add index.html && git commit -m "publish" && git push

   # Option B: serve from /docs (keeps things tidy)
   cp dist/drone-mission-review-standalone.html docs/index.html
   git add docs/index.html && git commit -m "publish" && git push
   # then set Folder → /docs in the Pages settings
   ```

6. Students visit `https://<yourname>.github.io/<reponame>/`.

Pages URLs are HTTPS by default, so the "Write sensor folders" button (which
needs a secure context) will work.

## Option 2 — Netlify / Cloudflare Pages / Vercel

Drag-and-drop the `dist/` folder into any of these services and you get a URL
within minutes. Free tier is fine. All three serve HTTPS.

Netlify quick path:

1. Sign in at [netlify.com](https://www.netlify.com/) with your GitHub account.
2. **Add new site → Deploy manually**.
3. Drop the `dist/` folder into the drop zone.
4. Rename `drone-mission-review-standalone.html` to `index.html` inside the deployed
   site, or set the site's default page to the current filename via
   `_redirects`.

## Option 3 — Institutional web hosting (e.g. `sites.tufts.edu`)

Most universities offer static web hosting under a `.edu` subdomain. This is
often the cleanest option for classroom use because the URL is visibly
institutional.

Steps for a typical Apache-style personal-hosting setup:

1. Get your web-hosting quota enabled (Tufts: ITS request; other schools
   vary).
2. Upload `dist/drone-mission-review-standalone.html` via SFTP or the school's file
   manager to your `public_html/dronedb/` folder.
3. Rename to `index.html` inside that folder for a clean URL.
4. Share `https://yourname.sites.tufts.edu/dronedb/`.

Verify the URL starts with `https://` — see the caveat below.

## Option 4 — Local network / offline

You don't need a server at all. Copy the standalone file to a USB drive,
share it via Google Drive / Box / Dropbox, or email it. It works from
`file://` — students just double-click it.

Downsides: no shortcut URL, harder to push updates, but the offline story is
airtight.

---

## Critical caveat: HTTPS and the File System Access API

The **Write sensor folders** button uses `window.showDirectoryPicker`, which
Chrome and Edge only expose in a **secure context**:

| URL scheme | showDirectoryPicker works? |
| --- | --- |
| `https://…` | Yes |
| `http://localhost` | Yes |
| `http://<any-other-domain>` | **No** — button gracefully falls back to a "use the Python script instead" message |
| `file:///…` | Yes |

GitHub Pages, Netlify, Cloudflare Pages, and Vercel all serve HTTPS by
default. Institutional hosting varies — verify your published URL begins
with `https://`.

If your hosting only offers HTTP, direct students to either:

- Use Chrome or Edge and download the HTML file first (`file://` works),
  **or**
- Use the included `sort_by_sensor.py` script (works everywhere Python does).

---

## Custom domain

All the hosted options above support custom domains via a `CNAME` DNS record.
Point a subdomain (e.g. `dronedb.example.edu`) at your Pages / Netlify site
and put the HTML at the root. Most academic domains support this via ITS.

## Updating the deployed app

After changing anything in `src/drone-mission-review.html`:

```bash
python3 src/_build_standalone.py           # regenerate dist/drone-mission-review-standalone.html
git add dist/drone-mission-review-standalone.html
git commit -m "update app"
git push
```

Users see the new version on their next page load. Browsers cache aggressively
by URL, so if a student reports they're still seeing an old version:

- Hard-reload (Cmd+Shift+R / Ctrl+Shift+R), or
- Version the link in whatever hand-out you gave them: `dronedb.html?v=15`.

## Bandwidth and scale

The standalone is ~420 KB served, ~130 KB gzipped. A whole class hitting it
at once is trivial for any of the hosts above — even the smallest free
Netlify tier serves 100 GB / month, enough for 750,000 loads.

## Map tile providers

Once loaded, the app requests tiles from three third-party providers:

- **Esri World Street Map** (streets) — free for educational and most
  non-commercial use; no API key needed.
- **Esri World Imagery** (satellite) — free for educational and most
  non-commercial use; no API key needed.
- **USGS National Map** (topo) — free, US-focused.

These are the only outbound requests the app makes at runtime (plus optional
OpenTopoData or USGS EPQS calls when a user clicks **Refine with terrain**).
Nothing else phones home. If a student's institutional network blocks one
tile provider, they can switch to another in the basemap picker in the
upper-right of the map.

## Removing the sample dataset (optional)

The embedded sample dataset is ~75 KB of the total 419 KB. If you want to
ship a smaller file with no sample, edit `src/_build_standalone.py` to skip
the sample-injection step, or rebuild with an empty `sample_index.json`.
The **Load sample dataset** button will still render (harmlessly disabled
once you set the block to `{"projects": []}`).

## Analytics

The app has no built-in analytics. If you want to measure classroom usage,
wrap your hosted HTML with your host's analytics (GitHub Pages: none by
default; Netlify: built-in for paid tiers; Cloudflare: Web Analytics free
tier). Do NOT insert third-party tracking scripts that would fetch code
from other origins — it would defeat the "no external dependencies at
runtime" property that makes the app auditable.
