# FIN04 Koski - Energisation and Permit Board

An interactive single-file board for energisation state and permit-to-work conflict
detection across the 32 EPODs at FIN04 Koski, generated from the electrical SLDs and
distribution schedules. It is a static web page: no server, no build step on the host,
no internet access required at runtime.

Live site (after you deploy, see below):
`https://<your-username>.github.io/<your-repo>/`

## Repository layout

```
.
├── docs/
│   ├── index.html         the deployable board  (GitHub Pages serves this)
│   └── .nojekyll          tells Pages to serve the file as-is
├── board_template.html    viewer template (SVG/JS); build_board.py injects data into it
├── build_board.py         injects topology + demo overlay -> fin04_board.html and docs/index.html
├── fin04_topology.py      builds topology.json; the single source of truth for structure
├── parse_downstream.py    parses the FIN3005 load schedules into downstream.json
├── downstream.json        parsed per-board load categories, FCU tags and cables
├── topology.json          generated structure consumed by the board
├── snapshot.json          generated demo overlay (energisation, permits, conflicts)
├── fin04_board.html       convenience copy of the board at the repo root
├── .gitignore
└── README.md
```

## Use it locally

Open `docs/index.html` (or `fin04_board.html`) in any browser. Drill:
FIN04 site overview -> MV ring -> POD -> board -> load group -> circuit. Click any asset
for its full tag, supply, and any permits or conflicts.

## Deploy to GitHub Pages

The board is one static HTML file, so GitHub Pages hosts it directly.

1. Create a repository on GitHub (github.com/new). A public repo gets Pages for free;
   a private repo needs GitHub Pro/Team/Enterprise for Pages.
2. From this folder, push the contents:
   ```bash
   git init
   git add .
   git commit -m "FIN04 board: initial revision"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
3. In the repo on GitHub: Settings -> Pages.
   - Source: "Deploy from a branch"
   - Branch: `main`, folder: `/docs`
   - Save.
4. Wait about a minute. The site goes live at
   `https://<your-username>.github.io/<your-repo>/`.

The `docs/.nojekyll` file is included so Pages serves the HTML untouched (no Jekyll
processing). Nothing else is needed; there is no build pipeline for GitHub to run.

### Updating the deployed board

`build_board.py` writes both `fin04_board.html` and `docs/index.html`, so after any
change just rebuild and push:

```bash
python3 fin04_topology.py      # if structure changed
python3 build_board.py         # refreshes docs/index.html
git commit -am "Update board"
git push
```

Pages redeploys automatically on push.

### Live sync (the Sync button)

The board has a **Sync** button at the top right. It fetches `snapshot.json` from the
same folder as the page and applies the latest energisation, permits and conflicts over
the embedded topology, then updates the snapshot time. `build_board.py` publishes
`docs/snapshot.json` alongside `docs/index.html`, so on the deployed site the button
pulls whatever `snapshot.json` is currently committed there. In production, have the
poller (ACC Assets) write a fresh `docs/snapshot.json` and the button (or a timer)
refreshes the live state without rebuilding the page. Opened straight from disk the
fetch is blocked by the browser, so it falls back to the embedded snapshot and says so.

## Regenerate from the drawings

The board is generated, not hand-built. Full pipeline (the source PDFs must be on disk
where parse_downstream.py expects them):

```bash
python3 parse_downstream.py    # PDFs            -> downstream.json
python3 fin04_topology.py      # downstream.json -> topology.json
python3 build_board.py         # topology.json   -> fin04_board.html, docs/index.html, snapshot.json
```

Dependency: `pdfplumber` (for parse_downstream.py only; `pip install pdfplumber`).
fin04_topology.py and build_board.py use the standard library only.

## What is drawing-derived vs assumed

Solid, read directly off the drawings (208000-EL-SYS-102, SCE60100, SCE61100, and the
FIN3005 61001/61002/61003 schedules):
- POD internals, identical across all 32 PODs, with full asset tags
  (FIN04.01.L0.EPODxx.* for EPOD assets, FIN04.01.L1.CG01.CHLR0nn / CHWP0nn for the
  shared chiller group, FIN04.01.L1.TRxx.DB001 for the hall NB boards).
- The EPOD main switchboard schedule: chiller on XQ101 (short-break), chiller water
  pump on XQ204 (no-break), XQ102 an equipped spare.
- The four MV rings: membership, A/B injection points, two radial chains per ring.
  MV is 22 kV.
- Downstream loads: NB boards one per POD (about 14 FCUs each), SB boards zoned one per
  POD pair, three distinct landlord boards.

Assumed or not yet modelled:
- Ring normal-open points are set at each chain mid point; confirm against the ring
  switch states before trusting the conflict output.
- Cross-POD genset coupling is not modelled (the sharing map is not on any sheet in the
  project). The genset is a per-POD placeholder.
- FCUs are single-fed per the available schedules.

## Overlay

`snapshot.json` is a demo overlay (sample permits and the conflicts they raise) to show
the mechanism. In production the energisation state and permits come from the live
source (ACC Assets / the poller), not the SLD.
