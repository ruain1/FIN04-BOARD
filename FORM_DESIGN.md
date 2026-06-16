# ACC permit form design (build this before scraping)

The converter's one hard rule is that the asset reference matches a board id exactly.
A free-text field breaks that the first time someone types "Epod 7" or "UPS 1.7MVA",
and the permit is silently dropped or misplaced. So the fields the board depends on
must be single-select dropdowns with fixed options, not text. ACC's form builder
supports single-select (multiple-choice) dropdowns, which is all this needs.

You do NOT need dependent or conditional dropdowns. Every POD is electrically
identical, so the asset list is the same for all 32 PODs. Two plain dropdowns plus a
status dropdown cover it, and the converter rebuilds the tag from them.

## Fields to make dropdowns

1. POD (single select). Options in `form_dropdown_pod.txt`, 32 entries like
   `EPOD07 (POD 7.1)`. Paste the list straight into the field's choices.

2. Asset (single select). Options in `form_dropdown_asset.txt`, 14 entries
   (LV main board, UPS 1.7 MVA, NB DB, SB DB, Hall NB DB (FCUs), Chiller, etc.). The
   same list applies to every POD, so one fixed dropdown is correct.

3. Permit status (single select). Options in `form_dropdown_status.txt`:
   Issued, Active, Suspended, Closed. These map directly onto the board's states; the
   first three are live and raise conflicts, Closed does not. Do not let this be free
   text, and do not conflate it with the form's review lifecycle status if your
   template has one; pick the field that means the permit's operational state.

Two more fields, not dropdowns but still not free text where avoidable:
- Permit number: use the form's built-in number, or a controlled field. The scraper
  maps it to `permit_id`.
- From / To dates: use ACC date pickers, not text boxes.

## How the converter consumes them

The scrape produces a CSV with `pod` and `asset` columns holding the selected dropdown
text. `make_snapshot.py` rebuilds the id itself:

```
pod = "EPOD07 (POD 7.1)" , asset = "NB DB"   ->   EPOD07.DB003
```

It derives the asset-name-to-id mapping from `topology.json` at run time, so the
dropdown options must match the board's asset display names exactly. That is the one
coupling to remember: if you rename an asset on the board, regenerate
`form_dropdown_asset.txt` and update the form's options. Run the generator any time the
topology changes:

```
python3 - <<'PY'
import json,re
t=json.load(open("topology.json"))
pods=sorted([a for a in t["assets"] if a.get("type")=="pod"], key=lambda a:int(re.search(r"\d+",a["id"]).group()))
open("form_dropdown_pod.txt","w").write("".join(f"{a['id']} ({a.get('label','')})\n" for a in pods))
assets=[a for a in t["assets"] if a.get("tier")=="pod" and a.get("pod")=="EPOD01"]
open("form_dropdown_asset.txt","w").write("".join(a["name"]+"\n" for a in assets))
PY
```

The CSV may instead carry a single `asset_tag` column with the full id, if your form
stores that directly; the converter accepts either shape.

## If permits ever go to breaker level

If a permit applies to a single breaker rather than a whole asset, add a third fixed
dropdown of the breaker references (XQ001, XQ101, ...), again identical across PODs,
and extend `resolve_tag` to append `.DB001.<XQ>`. Asset level is the sensible default;
add breaker level only if your permits are written that finely.

## Landlord and shared boards

The dropdowns above cover the POD assets. If permits are ever raised against the
landlord or house boards, add those as extra options (POD dropdown gets a "Landlord"
entry, asset dropdown gets the landlord boards) and map them to their `OS03` ids the
same way.
