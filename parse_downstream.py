#!/usr/bin/env python3
"""Parse FIN3005 downstream schedules (61001 SB, 61002 NB, 61003 landlord) into
per-board load categories + per-circuit metadata. Load labels are rotated text;
pdfplumber returns them reversed, so we un-reverse before matching. One board per
page. A single discriminating keyword per category gives one count per way."""
import pdfplumber, re, json, collections
SRC="/mnt/project/"
DOCS=[("NB","FIN3005DCSB100SHE61002.pdf"),
      ("SB","FIN3005DCSB100SHE61001.pdf"),
      ("LL","FIN3005DCSB100SHE61003.pdf")]
CATS=[("Fan-coil units","FCU"),("Smoke extract/damper","Smoke"),("Motorized buffer valve","Buffer"),
      ("Flow sensors","Flow"),("Security/BMS rack","Security"),("AHU","AHU"),("Leak detection","Leak"),
      ("Heat trace","Trace|EPH"),("VESDA","VESDA"),("Sprinkler","Sprinkler"),("Fire suppression","Suppress|Extinguish"),
      ("VAV controller","VAV"),("Fire/smoke damper","Damper"),("Lighting","Light"),("Small power/socket","Small Power|Socket"),
      ("Water/sewage","Water"),("Car charger/EV","Charger"),("Elevator","Elevat|Lift"),("Chiller/pump","Chiller|Pump"),
      ("AC unit","AC Unit"),("Spare (equipped)","Spare"),("Spare (space)","Space")]
rev=lambda s:s[::-1]
final={}
for typ,fn in DOCS:
    with pdfplumber.open(SRC+fn) as pdf:
        for i,pg in enumerate(pdf.pages,1):
            ws=pg.extract_words(extra_attrs=["upright"])
            up=" ".join(w["text"] for w in ws if w.get("upright"))
            rot=" ".join(rev(w["text"]) for w in ws if not w.get("upright"))
            podm=re.search(r"POD\s?(\d+\.\d)", up)
            if not podm and typ!="LL": continue
            cats={n:len(re.findall(p,rot,re.I)) for n,p in CATS}
            cats={k:v for k,v in cats.items() if v}
            if not cats: continue
            area_c=collections.Counter(re.findall(r"(TR\d{2}|OS\d{2}|GH\d{2}|CG\d{2})", up+" "+rot))
            area=area_c.most_common(1)[0][0] if area_c else None
            if typ in ("NB","SB") and area:
                stem_s=f"FIN04.01.L1.{area}.DB001"
            else:
                m=(re.search(r"FIN04\.01\.L[01]\.(?:OS\d+|GH\d+|CG\d+|TR\d+)\.DB001", up+" "+rot)
                   or re.search(r"FIN04\.01\.L[01]\.(?:OS\d+|GH\d+|CG\d+|TR\d+)\.DB\d+", up+" "+rot))
                stem_s=m.group(0) if m else (f"FIN04.01.L0.{area}.DB001" if area else None)
            src =re.search(r"(EPOD\d+)\.DB001", up+rot)
            fcu = sorted(set("FCU%03d"%int(m) for m in re.findall(r"FCU(\d+)", rot)), key=lambda s:int(s[3:]))
            fwc = sorted(set("FW%d"%int(m) for m in re.findall(r"\bFW(\d+)", rot)), key=lambda s:int(s[2:]))
            if podm:
                scope="POD"+podm.group(1)
            else:  # landlord: group pages by their real board (floor/section)
                if re.search(r"First Floor", up):       scope="First Floor DB"
                elif re.search(r"Ground Floor", up):     scope="Ground Floor DB"
                else:                                    scope="Main DB"
            key=f"{typ}:{scope}"
            rec=final.get(key)
            if rec is None:
                rec={"type":typ,"pod":(podm.group(1) if podm else None),
                     "ways":0,"categories":collections.Counter(),
                     "device":stem_s,
                     "source":(src.group(1) if src else None),
                     "fcu_tags":fcu,"fcu_cables":fwc}
                final[key]=rec
            rec["categories"].update(cats); rec["ways"]+=sum(cats.values())
json.dump(final,open("downstream.json","w"),indent=1)
print(f"parsed {len(final)} downstream boards")
for typ in ("NB","SB","LL"):
    bs=[v for v in final.values() if v["type"]==typ]; tot=collections.Counter()
    for b in bs: tot.update(b["categories"])
    print(f"  {typ}: {len(bs)} boards, {sum(tot.values())} ways")
ex=final.get("NB:POD2.1")
print("example NB POD2.1: device=%s source=%s fcu=%s..%s(%d) cables=%s.."%(
      ex["device"],ex["source"],ex["fcu_tags"][0],ex["fcu_tags"][-1],len(ex["fcu_tags"]),ex["fcu_cables"][:2]))
