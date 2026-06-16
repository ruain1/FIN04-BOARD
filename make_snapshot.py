#!/usr/bin/env python3
"""
make_snapshot.py - build the board's snapshot.json from a CSV export of permits.

This is the export-driven path (no ACC API). Whatever produces permits.csv (a
Tampermonkey scrape of the Forms page, a UI export, or hand entry) is interchangeable;
this script is the single place that knows the board's contract and computes conflicts.

Inputs (same folder, or pass paths via env):
  topology.json          the structure (already in the repo)
  permits.csv            columns: permit_id,title,asset_tag,status,from,to
  energisation.csv       OPTIONAL columns: asset_tag,state   (energised|deenergised|conditional)

Output:
  snapshot.json          (and docs/snapshot.json if a docs/ folder exists)

Run:  python3 make_snapshot.py
"""
import csv, json, os, sys, re, datetime as dt
from collections import deque, defaultdict

TOPO = os.environ.get("TOPO_PATH", "topology.json")
PERMITS = os.environ.get("PERMITS_CSV", "permits.csv")
ENERG = os.environ.get("ENERG_CSV", "energisation.csv")
OUT = os.environ.get("SNAPSHOT_OUT", "snapshot.json")

# Map whatever your export puts in the status column onto the board's states.
# The board treats active/issued/suspended as LIVE (they raise conflicts);
# draft/closed do not. Keys are matched case-insensitively. Extend as needed.
STATUS_MAP = {
    "issued": "issued", "active": "active", "in progress": "active",
    "inprogress": "active", "open": "active", "suspended": "suspended",
    "in review": "issued", "inreview": "issued", "submitted": "issued",
    "draft": "draft", "closed": "closed", "complete": "closed", "completed": "closed",
}
BOARD_STATES = {"active", "issued", "suspended", "draft", "closed"}
CONDUCT = {"feed", "bypass", "ring", "tie", "alternative"}

def norm_status(raw):
    s = (raw or "").strip().lower()
    if s in BOARD_STATES: return s
    return STATUS_MAP.get(s, "issued")   # unknown -> treat as live, and warn

def compute_conflicts(topo, permits):
    fwd = defaultdict(list)
    for e in topo["edges"]:
        if e.get("state") == "closed" and e["type"] in CONDUCT:
            fwd[e["from"]].append(e["to"])
    def reach(a, b):
        seen = {a}; q = deque([a])
        while q:
            x = q.popleft()
            if x == b: return True
            for y in fwd[x]:
                if y not in seen: seen.add(y); q.append(y)
        return False
    coupled = lambda a, b: reach(a, b) or reach(b, a)
    name = {a["id"]: a["name"] for a in topo["assets"]}
    live = [p for p in permits if p["status"] in ("active", "issued", "suspended")]
    out = []
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            a, b = live[i]["asset"], live[j]["asset"]
            if a and b and a != b and coupled(a, b):
                out.append({
                    "assets": [a, b], "severity": "high",
                    "reason": f"{name.get(a, a)} is electrically coupled to "
                              f"{name.get(b, b)} through closed switches",
                    "permits": [live[i]["id"], live[j]["id"]],
                })
    return out


def build_maps(topo):
    """Derive (asset display name -> ref) and (POD label -> EPOD id) from the
    topology, so the dropdown options never drift from the board."""
    name2ref, label2id = {}, {}
    for a in topo["assets"]:
        if a.get("tier") == "pod" and a.get("pod") == "EPOD01":
            name2ref[a["name"].strip().lower()] = a["ref"]
        if a.get("type") == "pod" and a.get("label"):
            label2id[a["label"].strip().lower()] = a["id"]
    return name2ref, label2id

def resolve_tag(r, name2ref, label2id):
    """Accept either an explicit asset_tag, or the two dropdown columns
    pod + asset (e.g. 'EPOD07 \u2014 POD 7.1' and 'NB DB') and rebuild the id."""
    tag = (r.get("asset_tag") or "").strip()
    if tag:
        return tag
    pod = (r.get("pod") or "").strip()
    asset = (r.get("asset") or "").strip()
    if not pod or not asset:
        return ""
    m = re.search(r"EPOD\d+", pod, re.I)
    epod = m.group(0).upper() if m else label2id.get(pod.lower(), "")
    ref = name2ref.get(asset.lower())
    return f"{epod}.{ref}" if (epod and ref) else ""

def read_csv(path):
    if not os.path.exists(path): return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def main():
    topo = json.load(open(TOPO, encoding="utf-8"))
    ids = {a["id"] for a in topo["assets"]}
    name2ref, label2id = build_maps(topo)

    permits, unmatched, unmapped = [], set(), set()
    for r in read_csv(PERMITS):
        tag = resolve_tag(r, name2ref, label2id)
        raw = (r.get("status") or "").strip()
        st = norm_status(raw)
        if raw and raw.strip().lower() not in STATUS_MAP and st == "issued" \
           and raw.strip().lower() not in BOARD_STATES:
            unmapped.add(raw)
        if tag and tag not in ids: unmatched.add(tag)
        permits.append({
            "id": (r.get("permit_id") or "").strip() or f"PTW-{len(permits)+1}",
            "title": (r.get("title") or "Permit to work").strip(),
            "asset": tag, "status": st,
            "from": (r.get("from") or "").strip() or None,
            "to": (r.get("to") or "").strip() or None,
        })

    energ = {}
    for r in read_csv(ENERG):
        tag = (r.get("asset_tag") or "").strip()
        state = (r.get("state") or "").strip().lower()
        if tag: energ[tag] = state

    snap = json.loads(json.dumps(topo))
    by = {a["id"]: a for a in snap["assets"]}
    for tag, st in energ.items():
        if tag in by: by[tag]["energisation"] = st
    snap["permits"] = permits
    snap["conflicts"] = compute_conflicts(topo, permits)
    snap["meta"]["generated"] = dt.datetime.now(dt.timezone.utc).isoformat()
    snap["meta"]["source"] = "ACC export"
    json.dump(snap, open(OUT, "w"), indent=2)
    if os.path.isdir("docs"):
        json.dump(snap, open(os.path.join("docs", "snapshot.json"), "w"), indent=2)

    print(f"wrote {OUT}: {len(permits)} permits, {len(snap['conflicts'])} conflicts")
    if unmapped:  print("  WARNING unmapped status values (defaulted to 'issued'):", sorted(unmapped), file=sys.stderr)
    if unmatched: print("  WARNING asset tags not found in topology:", sorted(unmatched), file=sys.stderr)

if __name__ == "__main__":
    main()
