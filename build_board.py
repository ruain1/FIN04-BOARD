#!/usr/bin/env python3
"""
build_board.py  -  inject topology.json + a demo overlay into board_template.html
to produce a single self-contained fin04_board.html.

The demo conflicts are computed here with SWITCH-AWARE COUPLING (only closed
feed/bypass edges conduct; open and normal_open edges are cut, and direction is
respected so coupling = one asset supplies the other). This is the corrected
rule the live poller should adopt; see acc_poller.py notes.
"""
import json
from collections import defaultdict, deque

TOPO = json.load(open("topology.json"))
ID = {a["id"]: a for a in TOPO["assets"]}

# ---- demo overlay -----------------------------------------------------------
ENERG = {
    "EPOD01.UPS001": "conditional",
    "EPOD01.DB003":  "deenergised",
    "EPOD03.MV-TX001": "deenergised",
    "EPOD03.DB001":  "conditional",
    "EPOD03":        "conditional",
}
PERMITS = [
    {"id":"PTW-8540","asset":"EPOD01.UPS001","status":"active","type":"Electrical energy isolation",
     "contractor":"Velox","from":"2026-06-15","to":"2026-06-18","title":"UPS module swap"},
    {"id":"PTW-8531","asset":"EPOD01.DB003","status":"active","type":"Electrical energy isolation",
     "contractor":"Velox","from":"2026-06-15","to":"2026-06-20","title":"No-break DB maintenance"},
    {"id":"PTW-8502","asset":"EPOD01.DB001","status":"issued","type":"Other work activity",
     "contractor":"Velox","from":"2026-06-16","to":"2026-06-22","title":"POD 1.1 board preparation"},
    {"id":"PTW-8524","asset":"EPOD03.MV-TX001","status":"active","type":"Electrical energy isolation",
     "contractor":"Nordic EPC","from":"2026-06-15","to":"2026-06-17","title":"Transformer maintenance"},
    {"id":"PTW-8519","asset":"EPOD05.CHLR","status":"suspended","type":"Mechanical work",
     "contractor":"Velox","from":"2026-06-12","to":"2026-06-19","title":"Chiller works"},
]
LIVE = {"active", "issued", "suspended"}

# ---- switch-aware coupling --------------------------------------------------
# directed supply graph over CLOSED conducting edges only
CONDUCT = {"feed", "bypass", "ring", "tie", "alternative"}
fwd, rev = defaultdict(list), defaultdict(list)
for e in TOPO["edges"]:
    if e.get("state") == "closed" and e["type"] in CONDUCT:
        fwd[e["from"]].append(e["to"])
        rev[e["to"]].append(e["from"])

def reaches(a, b):
    """True if a supplies b (b reachable downstream of a) over closed edges."""
    seen, q = {a}, deque([a])
    while q:
        x = q.popleft()
        if x == b: return True
        for y in fwd[x]:
            if y not in seen: seen.add(y); q.append(y)
    return b in seen

def coupled(a, b):
    if a == b: return True, "same asset"
    if reaches(a, b): return True, f"{ID[a]['name']} supplies {ID[b]['name']} through closed switches"
    if reaches(b, a): return True, f"{ID[b]['name']} supplies {ID[a]['name']} through closed switches"
    return False, ""

live = [p for p in PERMITS if p["status"] in LIVE]
conflicts = []
for i in range(len(live)):
    for j in range(i + 1, len(live)):
        ok, reason = coupled(live[i]["asset"], live[j]["asset"])
        if ok:
            conflicts.append({
                "assets": sorted({live[i]["asset"], live[j]["asset"]}),
                "permits": [live[i]["id"], live[j]["id"]],
                "reason": reason,
                "severity": "high",
            })

OVERLAY = {"permits": PERMITS, "energisation": ENERG, "conflicts": conflicts}

# ---- inject -----------------------------------------------------------------
tpl = open("board_template.html", encoding="utf-8").read()
tpl = tpl.replace("/*__TOPOLOGY__*/ null", "/*__TOPOLOGY__*/ " + json.dumps(TOPO, separators=(",", ":")))
tpl = tpl.replace("/*__OVERLAY__*/ {permits:[],energisation:{},conflicts:[]}",
                  "/*__OVERLAY__*/ " + json.dumps(OVERLAY, separators=(",", ":")))
open("fin04_board.html", "w", encoding="utf-8").write(tpl)
# keep the GitHub Pages site (docs/index.html) in sync when the repo layout is present
import os
if os.path.isdir("docs"):
    open(os.path.join("docs", "index.html"), "w", encoding="utf-8").write(tpl)

# also emit a snapshot.json the poller/board can consume live
snap = json.loads(json.dumps(TOPO))
for k, v in ENERG.items():
    if k in ID: ID[k]["energisation"] = v
# rebuild assets list with overrides applied
for a in snap["assets"]:
    if a["id"] in ENERG: a["energisation"] = ENERG[a["id"]]
snap["permits"] = PERMITS
snap["conflicts"] = conflicts
json.dump(snap, open("snapshot.json", "w"), indent=2)
if os.path.isdir("docs"):
    json.dump(snap, open(os.path.join("docs", "snapshot.json"), "w"), indent=2)

print(f"built fin04_board.html  ({len(tpl)//1024} KB)")
print(f"demo conflicts: {len(conflicts)}")
for c in conflicts:
    print("  -", " + ".join(c['assets']), "::", c['reason'])
