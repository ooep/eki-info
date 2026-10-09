#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_master.py — 从 mini-japanrail-3d 网站拉取车站主清单

数据源: 网站 Pages 上的 data/stations3d.geojson
  https://ooep.github.io/floral-salad-8734/mini-japanrail-3d/data/stations3d.geojson
每个 feature: properties={station, op, line}, geometry=Point([lng, lat])

输出: data/master_stations.json
  [{"station": "新宿", "operators": [...], "lines": [...], "coord": [lng, lat]}, ...]
同名站合并为一条（与网站 normName 主键一致），保留首个坐标；
多事业者共站的 operators 取并集，便于后续在 ecomo 多 section 里选对 section。
"""
import json
import sys
import urllib.request

SITE_BASE = "https://ooep.github.io/floral-salad-8734/mini-japanrail-3d"
GEOJSON_URL = f"{SITE_BASE}/data/stations3d.geojson"
UA = {"User-Agent": "eki-info-bot/1.0 (+https://github.com/ooep/eki-info)"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    print(f"[master] fetching {GEOJSON_URL} ...", flush=True)
    raw = fetch(GEOJSON_URL)
    gj = json.loads(raw.decode("utf-8"))
    feats = gj.get("features", [])
    print(f"[master] features: {len(feats)}", flush=True)

    agg = {}
    for f in feats:
        p = f.get("properties", {})
        name = (p.get("station") or "").strip()
        if not name:
            continue
        op = (p.get("op") or "").strip()
        line = (p.get("line") or "").strip()
        coord = f.get("geometry", {}).get("coordinates")
        e = agg.setdefault(name, {"station": name, "operators": set(),
                                  "lines": set(), "coord": coord})
        if op:
            e["operators"].add(op)
        if line:
            e["lines"].add(line)

    out = []
    for name, e in agg.items():
        out.append({
            "station": name,
            "operators": sorted(e["operators"]),
            "lines": sorted(e["lines"]),
            "coord": e["coord"],
        })
    out.sort(key=lambda x: x["station"])

    with open("data/master_stations.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[master] unique stations: {len(out)} -> data/master_stations.json", flush=True)


if __name__ == "__main__":
    sys.exit(main())
