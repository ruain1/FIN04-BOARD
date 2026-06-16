# Driving the board from ACC exports (no API)

You have ACC project admin but no API access, so the board is fed from an export of
the permit Forms rather than a live poll. The design has one stable seam: a CSV of
permits. Anything that produces that CSV is interchangeable, and `make_snapshot.py`
is the single place that knows the board's contract and computes conflicts.

```
ACC Forms (your logged-in session)
   |  scrape / export
   v
permits.csv  (+ optional energisation.csv)
   |  make_snapshot.py   (loads topology.json, computes conflicts)
   v
docs/snapshot.json   ->  commit/push  ->  board Sync button
```

## The CSV contract

`permits.csv`, one row per permit:

```
permit_id,title,asset_tag,status,from,to
PTW-8540,UPS battery replacement,EPOD07.UPS001,Issued,2026-06-16,2026-06-18
```

- `asset_tag` must equal a board asset id. The board id is the short form
  (`EPOD07.DB003`) or the full tag (`FIN04.01.L0.EPOD07.DB003`); use whichever your
  forms carry, but it has to match exactly or the permit is dropped. `make_snapshot.py`
  warns about any tag it cannot place, so a mismatch is visible, not silent.
- `status` is mapped onto the board's states by `STATUS_MAP` in `make_snapshot.py`
  (Issued, In Progress, In Review, Suspended, Draft, Closed are handled; extend the
  map for your wording). Active, issued and suspended are LIVE and raise conflicts;
  draft and closed do not.
- `from` / `to` are optional date strings.

`energisation.csv` is optional, `asset_tag,state` with state
`energised|deenergised|conditional`. Omit it and assets keep their topology default.

## Build and publish

```
python3 make_snapshot.py        # permits.csv (+ energisation.csv) -> docs/snapshot.json
git commit -am "snapshot $(date -u +%FT%TZ)"
git push
```

The Sync button on the live board then shows the new state. See
`permits.sample.csv` / `energisation.sample.csv` for a working example; copy them to
`permits.csv` / `energisation.csv` and run the script to see a conflict appear.

## Two ways to produce the CSV

1. Tampermonkey (`acc_forms_export.user.js`). Rides your logged-in ACC session and
   reads the rendered Forms list, no API. You map three selectors to your project's
   Forms table (the file marks them TODO), then an "Export permits.csv" button appears
   on the page. Fastest to stand up; the cost is that it depends on ACC's page markup,
   which Autodesk can change without notice, so treat it as something to re-check
   occasionally rather than set-and-forget.

2. Scheduled automation. If the Forms UI gives you a CSV/XLSX export, or you script the
   download with Power Automate Desktop, point a scheduled task at `make_snapshot.py`
   and a `git push`. More robust than DOM scraping, but it still needs a logged-in
   session to do the export.

Full hands-off is possible by having the userscript itself push `snapshot.json` to the
repo via the GitHub contents API with a fine-grained token, but that puts a write token
in a browser script on your machine; only do it if you accept that and scope the token
to this one repo.

## The caveat that matters

Forms gives you permits, not switching state. The conflict engine decides coupling from
the switch/edge states in `topology.json`, which are the assumed normal configuration
(and the ring normal-open points are inferred, not confirmed). So a flagged conflict
means "these two permitted assets are coupled under the assumed normal switching," which
is a sound planning-level warning but not a live electrical guarantee. To make conflicts
reflect the real plant you would also need live switch and energisation state, which a
permit form does not carry. Keep that limitation visible to anyone relying on the board
for isolation decisions.
