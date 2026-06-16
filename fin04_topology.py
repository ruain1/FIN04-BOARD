#!/usr/bin/env python3
"""
fin04_topology.py  -  FIN04 Koski topology generator

Single source of truth for the energisation/permit board's structure. Every POD
in the FIN3005 SLDs is electrically identical, so the POD is defined ONCE as a
template and instantiated 32 times. This avoids hand-transcribing ~30 components
across 32 near-identical drawing sheets (which is how errors get in).

Output: topology.json, in the shape the board and acc_poller.py already read,
extended with two fields that the multi-tier board needs:
  - tier        : "site" | "ring" | "pod" | "board"   (which view a node lives in)
  - childLayout : the layout used when this node is drilled into (or null)
  - pod / label : provenance back to the EPOD id and the SLD's "POD x.y" label

WHAT IS SOLID (read directly off the LV sheets, identical on all 32):
  - 32 PODs EPOD01..EPOD32; the POD-internal arrangement below.
WHAT NEEDS VERIFICATION AGAINST THE DRAWINGS (do not trust blindly):
  - RING_DEF: ring membership, the A/B source-injection points, and above all the
    NORMAL-OPEN point on each ring. These are read off the dense MV sheet + the
    "From POD / To POD" labels and are the inputs the conflict engine depends on.
    Edit RING_DEF, re-run, done.
"""

import json
import datetime as dt

# Parsed downstream schedules (FIN3005 61001/61002/61003). Optional: the
# generator still runs without it (downstream tiers just stay empty).
try:
    DOWN = json.load(open("downstream.json", encoding="utf-8"))
except FileNotFoundError:
    DOWN = {}

# ----------------------------------------------------------------------------
# EPOD id  ->  SLD functional label.  Three numbering schemes that do not line
# up; EPOD id is the asset key, the label is what the room/drawing calls it.
# ----------------------------------------------------------------------------
POD_LABEL = {}
for i in range(1, 9):   POD_LABEL[f"EPOD{i:02d}"] = f"POD {i}.1"          # 1.1..8.1
for i in range(9, 17):  POD_LABEL[f"EPOD{i:02d}"] = f"POD {i}.1"          # 9.1..16.1
# .2 train is labelled in descending order on the sheets:
for n, lbl in zip(range(17, 25), [8, 7, 6, 5, 4, 3, 2, 1]):
    POD_LABEL[f"EPOD{n:02d}"] = f"POD {lbl}.2"                            # EPOD17->8.2 .. EPOD24->1.2
for n, lbl in zip(range(25, 33), [16, 15, 14, 13, 12, 11, 10, 9]):
    POD_LABEL[f"EPOD{n:02d}"] = f"POD {lbl}.2"                            # EPOD25->16.2 .. EPOD32->9.2

# ----------------------------------------------------------------------------
# RING_DEF  --  DRAWING-DERIVED from FIN3005-DCS-...-SCE61100 (LV single line,
# one page per POD) cross-checked against SCE60100 (MV single line). Each of the
# four MV rings is run as TWO radial chains, each fed from MV Building A at one
# end and MV Building B at the other, normally open at a mid point so every POD
# sits on one source. The chain ORDER is the real adjacency off the "From POD
# x.y" ties; it is NOT the sequential 1..8 the old guess assumed.
#   chains[].seq      : EPOD ids head(A end) -> tail(B end)
#   chains[].no_after : index after which the ring switch is normally OPEN.
#                       (Midpoint per chain. INFERRED normal-operating state;
#                        the A/B feeds and adjacency are read directly, the open
#                        point should still be confirmed against ring-switch
#                        states on the SLD. It drives every cross-POD conflict.)
# ----------------------------------------------------------------------------
RING_DEF = {
    "RING-1": {"chains": [
        {"seq": ["EPOD01", "EPOD02", "EPOD07", "EPOD08"], "no_after": 1},
        {"seq": ["EPOD03", "EPOD04", "EPOD05", "EPOD06"], "no_after": 1}]},
    "RING-2": {"chains": [
        {"seq": ["EPOD09", "EPOD10", "EPOD15", "EPOD16"], "no_after": 1},
        {"seq": ["EPOD11", "EPOD12", "EPOD13", "EPOD14"], "no_after": 1}]},
    "RING-3": {"chains": [
        {"seq": ["EPOD17", "EPOD18", "EPOD23", "EPOD24"], "no_after": 1},
        {"seq": ["EPOD19", "EPOD20", "EPOD21", "EPOD22"], "no_after": 1}]},
    "RING-4": {"chains": [
        {"seq": ["EPOD25", "EPOD26", "EPOD31", "EPOD32"], "no_after": 1},
        {"seq": ["EPOD27", "EPOD28", "EPOD29", "EPOD30"], "no_after": 1}]},
}

def ring_members(ring):
    return [pod for ch in RING_DEF[ring]["chains"] for pod in ch["seq"]]

RING_OF = {pod: ring for ring in RING_DEF for pod in ring_members(ring)}

# ----------------------------------------------------------------------------
# POD TEMPLATE.  One POD's internal nodes and edges, with coordinates for the
# POD-tier SVG (canvas 900 x 600). Instantiated per POD with the EPOD prefix.
#   (suffix, name, type, childLayout, x, y)
# DB001 carries childLayout="board" so drilling it shows the CBxx schedule.
# ----------------------------------------------------------------------------
POD_NODES = [
    ("RMU001",   "RMU 22 kV",          "switchgear",  None,    480,  56),
    ("MV-TX001", "TX 2.5 MVA",         "transformer", None,    480, 150),
    ("GEN001",   "Standby genset",     "source",      None,    160, 150),
    ("DB001",    "LV main board",      "bus",         "board", 480, 256),
    ("UPS001",   "UPS 1.7 MVA",        "ups",         None,    170, 392),
    ("BW002",    "Gray-space busway",  "busway",      None,    400, 392),
    ("CHLR",     "Chiller",            "cooling",     None,    620, 392),
    ("CHWP",     "Chiller water pump", "cooling",     None,    820, 392),
    ("DB003",    "NB DB",              "board",       None,    170, 512),
    ("DB002",    "SB DB",              "board",       None,    400, 512),
    ("BLDG-SB",  "Mechanical NB-DB",   "board",       None,    620, 512),
    ("BLDG-NB",  "Building NB DB",     "board",       None,    820, 512),
    # CRAHs: 2 Daikin units per POD, no-break fed off DB003 (=462.110) via
    # XF225/XF226. They cool the EPOD electrical rooms (read off 208000-EL-SYS-102
    # sheet 20 "CRAH" / NB DB sheet 462.110/10). Identical on all 32 PODs.
    ("CRAH001",  "CRAH 1"           ,    "cooling",     None,    300, 590),
    ("CRAH002",  "CRAH 2"           ,    "cooling",     None,    520, 590),
]
# device designation / equipment tag per POD node (metadata, NOT shown on graphic)
POD_DEVICE = {
    "RMU001": "=421.100", "MV-TX001": "TX 2.5 MVA", "DB001": "=431.100",
    "UPS001": "=462.100", "DB003": "=462.110", "DB002": "=433.160",
    "BLDG-SB": "Mechanical NB-DB", "BLDG-NB": "Building NB DB",
    "CRAH001": "IK001", "CRAH002": "IK002",
    "CHLR": "=432.100", "CHWP": "=462.100",
}
# supply note per POD node (metadata for the detail panel)
POD_FED = {
    "CHLR": "XQ101 (CB007), 3P 800A NS800L, off LV main board short-break bus =432.100",
    "CHWP": "XQ204 (CB018), 4P 250A NSX250L, off LV main board no-break bus =462.100",
}
POD_NOTE = {
    "CHWP": "On the no-break (UPS) bus so chilled-water circulation rides through a supply interruption. Distinct from the landlord/yard pumps.",
}
POD_EDGES = [
    ("RMU001",   "MV-TX001", "feed",        "closed"),
    ("MV-TX001", "DB001",    "feed",        "closed"),   # CB001 utility incomer
    ("GEN001",   "DB001",    "alternative", "open"),     # CB002/ATS, standby
    ("DB001",    "UPS001",   "feed",        "closed"),   # CB003 to UPS (SB)
    ("UPS001",   "DB003",    "feed",        "closed"),   # UPS -> no-break bus
    ("DB001",    "DB003",    "bypass",      "open"),     # CB006 Castell bypass
    ("DB001",    "DB002",    "feed",        "closed"),
    ("DB001",    "BW002",    "feed",        "closed"),
    ("DB001",    "CHLR",     "feed",        "closed"),
    ("DB001",    "CHWP",     "feed",        "closed"),
    ("DB001",    "BLDG-SB",  "feed",        "closed"),
    ("DB001",    "BLDG-NB",  "feed",        "closed"),
    ("DB003",    "CRAH001",  "feed",        "closed"),   # XF225, no-break
    ("DB003",    "CRAH002",  "feed",        "closed"),   # XF226, no-break
]

# Main switchboard schedule (board tier), read off 208000-EL-SYS-102 (NordicEPOD
# EPOD as-built SLD, sheets 6 and 22-34). Identical across all 32 PODs. The 5th
# field is a load CATEGORY, so the board view can group ways into tiles instead
# of a flat card wall (the agreed "drill one category at a time" rule).
#   (ref, fn-tag, rating, function, category)
BREAKER_SCHEDULE = [
    ("XQ001", "=431.100", "4P 4000A MTZ2 40H2 ML6.0X",  "Transformer incomer (Castell)",       "Incomer"),
    ("XQ002", "=431.100", "4P 4000A MTZ2 40H2 ML5.0X",  "Generator / 2nd incomer",             "Incomer"),
    ("XQ010", "=432.100", "3P 3200A MTZ2 32H2 ML5.0X",  "UPS input",                           "UPS"),
    ("XQ003", "=432.100", "4P 3200A MTZ2 32H2 ML5.0X",  "UPS bypass (Castell, non-auto)",      "UPS"),
    ("XQ011", "=462.100", "4P 3200A MTZ2 32H2 ML5.0X",  "UPS output (to no-break bus)",        "UPS"),
    ("XQ101", "=432.100", "3P 800A NS800L ML5.0E",      "Chiller supply (chiller plant)",      "Cooling"),
    ("XQ102", "=432.100", "3P 800A NS800L ML5.0E",      "Spare (equipped)",                    "Spare"),
    ("XQ105", "=432.100", "4P 400A NSX400L ML5.3E",     "Temporary chiller feed",              "Cooling"),
    ("XQ202", "=462.100", "4P 2500A MTZ2 25H2 ML5.0X",  "Whitespace busway (IT load)",         "Whitespace"),
    ("XQ004", "=432.100", "4P 250A NSX250L ML5.2E",     "SB distribution board (=433.160)",    "Distribution"),
    ("XQ201", "=462.100", "4P 250A NSX250L ML5.2E",     "No-break feeder",                     "Distribution"),
    ("XQ203", "=462.100", "4P 250A NSX250L ML7.2E",     "No-break DB (=462.110, CRAHs)",       "Distribution"),
    ("XQ204", "=462.100", "4P 250A NSX250L ML7.2E",     "Chiller water pump (no-break)",       "Cooling"),
    ("XQ205", "=462.100", "4P 160A NSX160L ML7.2E",     "Local POD distribution (=462.110)",   "Distribution"),
    ("XQ106", "=432.100", "4P 160A NSX160L ML7.2E",     "Gen set aux supply",                  "ATS/Genset"),
    ("XQ107", "=432.100", "4P 160A NSX160L ML7.2E",     "POD local distribution board (ATS)",  "ATS/Genset"),
    ("XQ108", "=432.100", "4P 160A NSX160L ML7.2E",     "ATS supply",                          "ATS/Genset"),
    ("XS109", "=432.100", "4P 160A ATS TA16D4",         "Automatic transfer switch",           "ATS/Genset"),
    ("XQ005", "=432.100", "4P 25A NG125L",              "Secondary supply to ATS",             "ATS/Genset"),
    ("XQ103", "=432.100", "4P 160A NSX160L",            "Spare",                               "Spare"),
    ("XQ104", "=432.100", "4P 160A NSX160L",            "Spare",                               "Spare"),
    ("XQE004","=432.100", "PRD1 25r Type 1",            "Surge arrester",                      "Surge"),
    ("XQE201","=462.100", "PRD1 25r Type 1",            "Surge arrester (no-break)",           "Surge"),
]

# ----------------------------------------------------------------------------
# layout coordinates
# ----------------------------------------------------------------------------
SITE_W = 1040
RING_SLOTS_PER_ROW = 8


def site_layout():
    """Top-level overview: two MV buildings, four ring blocks, landlord."""
    nodes = []
    nodes.append(dict(id="MV-A", name="MV Building A", type="source",
                      parent=None, tier="site", childLayout=None,
                      x=300, y=70))
    nodes.append(dict(id="MV-B", name="MV Building B", type="source",
                      parent=None, tier="site", childLayout=None,
                      x=740, y=70))
    ring_xy = {"RING-1": (240, 230), "RING-2": (560, 230),
               "RING-3": (240, 400), "RING-4": (560, 400)}
    for ring, (x, y) in ring_xy.items():
        n = len(ring_members(ring))
        nodes.append(dict(id=ring, name=ring.replace('RING-', 'MV ring '),
                          type="ring", parent=None, tier="site",
                          childLayout="ring", x=x, y=y,
                          detail=f"{n} PODs (2 chains)"))
    nodes.append(dict(id="LANDLORD", name="Landlord supply", type="source",
                      parent=None, tier="site", childLayout="landlord",
                      x=880, y=320))
    return nodes


def site_edges():
    e = []
    for ring, d in RING_DEF.items():
        e.append(dict(**{"from": "MV-A", "to": ring, "type": "feed", "state": "closed"}))
        e.append(dict(**{"from": "MV-B", "to": ring, "type": "feed", "state": "closed"}))
    return e


def ring_layout(ring):
    """One ring view: two radial chains, A feed at each head, B feed at each
    tail, normally open at the chain mid point."""
    nodes, edges = [], []
    chains = RING_DEF[ring]["chains"]
    ys = [230, 380]  # one row per chain
    for ci, ch in enumerate(chains):
        seq = ch["seq"]
        no_after = ch["no_after"]
        n = len(seq)
        gap = SITE_W / (n + 1)
        y = ys[ci] if ci < len(ys) else 230 + ci * 150
        for i, pod in enumerate(seq):
            nodes.append(dict(id=pod, name=POD_LABEL[pod], type="pod",
                              parent=ring, tier="ring", childLayout="pod",
                              x=round(gap * (i + 1)), y=y, pod=pod, label=POD_LABEL[pod],
                              tag=f"FIN04.01.L0.{pod}"))
        # conductor between consecutive PODs; the mid tie is normally open
        for i in range(n - 1):
            state = "normal_open" if i == no_after else "closed"
            edges.append(dict(**{"from": seq[i], "to": seq[i + 1], "type": "ring", "state": state}))
        # source injections: A onto the head, B onto the tail
        edges.append(dict(**{"from": "MV-A", "to": seq[0],  "type": "feed", "state": "closed"}))
        edges.append(dict(**{"from": "MV-B", "to": seq[-1], "type": "feed", "state": "closed"}))
    return nodes, edges


def pod_tag(ref, epod):
    """Full engineering asset tag for a POD child node, per the SLD scheme."""
    pl = POD_LABEL.get(epod, "POD 0.0")
    n = int(pl.split()[1].split(".")[0])          # POD-pair number
    if ref == "CHLR":     return f"FIN04.01.L1.CG01.CHLR{n:03d}"   # shared chiller group
    if ref == "CHWP":     return f"FIN04.01.L1.CG01.CHWP{n:03d}"
    if ref == "MV-TX001": return f"FIN04.01.L0.{epod}.TX001"
    return f"FIN04.01.L0.{epod}.{ref}"


def pod_layout(pod):
    """One POD's internal SLD from the template, prefixed with the EPOD id."""
    nodes, edges = [], []
    pid = lambda s: f"{pod}.{s}"
    for suffix, name, typ, child, x, y in POD_NODES:
        nodes.append(dict(id=pid(suffix), name=name, type=typ,
                          parent=pod, tier="pod", childLayout=child,
                          x=x, y=y, pod=pod, ref=suffix,
                          device=POD_DEVICE.get(suffix),
                          fed=POD_FED.get(suffix),
                          feed_note=POD_NOTE.get(suffix),
                          tag=pod_tag(suffix, pod)))
    for f, t, typ, st in POD_EDGES:
        edges.append(dict(**{"from": pid(f), "to": pid(t), "type": typ, "state": st}))
    return nodes, edges


def board_layout(pod):
    """DB001 breaker schedule for one POD, grid-laid."""
    nodes, edges = [], []
    board = f"{pod}.DB001"
    cols = 4
    x0, y0, dx, dy = 170, 130, 230, 96
    for i, (ref, fn_tag, rating, fn, cat) in enumerate(BREAKER_SCHEDULE):
        r, c = divmod(i, cols)
        nodes.append(dict(id=f"{board}.{ref}", name=ref, type="breaker",
                          parent=board, tier="board", childLayout=None,
                          x=x0 + c * dx, y=y0 + r * dy, pod=pod,
                          ref=ref, xq=fn_tag, rating=rating, fn=fn, cat=cat,
                          tag=f"FIN04.01.L0.{pod}.DB001.{ref}"))
        edges.append(dict(**{"from": board, "to": f"{board}.{ref}",
                            "type": "feed", "state": "closed"}))
    return nodes, edges


def landlord_layout():
    nodes, edges = [], []
    nodes.append(dict(id="GH01.MV-TX001", name="TX GH01 630 kVA", type="transformer",
                      parent="LANDLORD", tier="pod", childLayout=None, x=300, y=130))
    nodes.append(dict(id="GH02.MV-TX001", name="TX GH02 630 kVA", type="transformer",
                      parent="LANDLORD", tier="pod", childLayout=None, x=720, y=130))
    # one node per distinct landlord board parsed from 61003 (not duplicated)
    ll = [(k, v) for k, v in DOWN.items() if v.get("type") == "LL"]
    ll.sort(key=lambda kv: -kv[1]["ways"])
    n = len(ll) or 1
    for i, (k, v) in enumerate(ll):
        name = k.split(":", 1)[1]                 # "Ground Floor DB" etc.
        x = round(1040 / (n + 1) * (i + 1))
        nid = "OS03.DB001." + name.replace(" ", "")
        nodes.append(dict(id=nid, name="Landlord " + name, type="board",
                          parent="LANDLORD", tier="pod", childLayout="loadboard",
                          x=x, y=330, categories=v["categories"], ways=v["ways"],
                          device=v.get("device") or "=OS03.DB001",
                          tag=v.get("device") or "FIN04.01.L0.OS03.DB001",
                          fed="landlord / house services (shared site-level)"))
        src = "GH01.MV-TX001" if i % 2 == 0 else "GH02.MV-TX001"
        edges.append(dict(**{"from": src, "to": nid, "type": "feed", "state": "closed"}))
    return nodes, edges


def build():
    assets, edges = [], []
    assets += site_layout()
    edges += site_edges()
    for ring in RING_DEF:
        n, e = ring_layout(ring); assets += n; edges += e
    for pod in POD_LABEL:
        n, e = pod_layout(pod); assets += n; edges += e
        n, e = board_layout(pod); assets += n; edges += e
    n, e = landlord_layout(); assets += n; edges += e

    # ---- attach downstream load schedules (FIN3005 61001/61002/61003) --------
    # NB hall board (FCUs etc.) -> POD "BLDG-NB"; SB hall board (zoned, 1 per
    # pair) -> POD "BLDG-SB". Landlord boards are built directly in landlord_layout.
    nb_by_pod = {v["pod"]: v for k, v in DOWN.items() if v["type"] == "NB" and v.get("pod")}
    sb_by_pod = {v["pod"]: v for k, v in DOWN.items() if v["type"] == "SB" and v.get("pod")}

    def podnum(epod):  # "EPOD02" -> "2.1"
        return POD_LABEL.get(epod, "").replace("POD ", "")

    for a in assets:
        ref = a.get("ref")
        if ref == "BLDG-NB" and a.get("pod"):
            rec = nb_by_pod.get(podnum(a["pod"]))
            if rec:
                a["name"] = "Hall NB DB (FCUs)"
                a["childLayout"] = "loadboard"
                a["categories"] = rec["categories"]
                a["ways"] = rec["ways"]
                a["fed"] = "no-break (UPS), white-space cooling"
                a["device"] = rec.get("device") or a.get("device")
                a["tag"] = rec.get("device") or a.get("tag")
                a["source"] = rec.get("source")
                a["fcu_tags"] = rec.get("fcu_tags")
                a["fcu_cables"] = rec.get("fcu_cables")
                a["feed_note"] = ("single feed from this POD's NB board; "
                                  "no redundant B-feed appears in the available schedules")
        elif ref == "BLDG-SB" and a.get("pod"):
            rec = sb_by_pod.get(podnum(a["pod"]))
            if rec:
                a["name"] = "Hall SB DB"
                a["childLayout"] = "loadboard"
                a["categories"] = rec["categories"]
                a["ways"] = rec["ways"]
                a["fed"] = "short-break, hall services"
                a["device"] = rec.get("device") or a.get("device")
                a["tag"] = rec.get("device") or a.get("tag")
                a["source"] = rec.get("source")
            else:
                a["name"] = "Hall SB DB (zoned/shared)"
                a["detail"] = "fed from paired POD's SB board"

    # default energisation: live field, OWNED by ACC Assets, not the SLD. Seed
    # everything "energised"; the poller overwrites per asset at runtime.
    for a in assets:
        a.setdefault("energisation", "energised")

    return {
        "meta": {
            "project": "FIN04 Koski",
            "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "source": "topology generator (SLD-derived)",
            "tiers": ["site", "ring", "pod", "board", "loadboard"],
        },
        "assets": assets,
        "edges": edges,
        "permits": [],
        "conflicts": [],
    }


if __name__ == "__main__":
    topo = build()
    with open("topology.json", "w", encoding="utf-8") as f:
        json.dump(topo, f, indent=2)
    pods = sum(1 for a in topo["assets"] if a["type"] == "pod")
    print(f"wrote topology.json: {len(topo['assets'])} assets, "
          f"{len(topo['edges'])} edges, {pods} PODs, {len(RING_DEF)} rings")
