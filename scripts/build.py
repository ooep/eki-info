#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — 聚合 cache/ 为最终交付 JSON

输出:
  data/station-guide.full.json  前端「指南」tab 直接消费（按站名索引）
  data/mapping.json             与 mini-japanrail-3d 的键映射 + 坐标/事业者
"""
import hashlib
import json
import os
import re
import sys
import time


def cache_path(name):
    h = hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^\w\-]", "_", name)
    return os.path.join("cache", f"{h}_{safe}.json")


def map_cache_path(name):
    h = hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^\w\-]", "_", name)
    return os.path.join("cache_map", f"{h}_{safe}.json")


def pick_record(records, operators):
    """多事业者共站时，优先选 operators 里命中的 section。"""
    if not records:
        return None
    if operators:
        for want in operators:
            for r in records:
                if want and want in (r.get("operator") or ""):
                    return r
    return records[0]


def main():
    stations = json.load(open("data/master_stations.json", encoding="utf-8"))
    out = {"schema": "station-guide/v2",
           "generatedAt": time.strftime("%Y-%m-%d"),
           "source": "ecomo-rakuraku (公益財団法人交通エコロジー・モビリティ財団)",
           "stations": {}}
    mapping = {}
    ok = miss = 0

    for st in stations:
        name = st["station"]
        cp = cache_path(name)
        m = {"coord": st["coord"], "operators": st["operators"],
             "lines": st["lines"], "hasGuide": False}
        rec = None
        if os.path.exists(cp):
            cache = json.load(open(cp, encoding="utf-8"))
            if cache.get("status") == "ok":
                rec = pick_record(cache.get("records", []), st["operators"])
                m["ecomoUrl"] = cache.get("ecomoUrl")
                m["ecomoSlug"] = cache.get("ecomoSlug")
        if rec is None:
            miss += 1
        else:
            ok += 1
            m["hasGuide"] = True
            entry = {
                "name": cache.get("officialName") or name,
                "key": name,
                "operator": rec.get("operator") or (st["operators"][0] if st["operators"] else ""),
                "lines": rec.get("lines") or st["lines"],
                "basic": rec.get("basic") or {},
                "wheelchair": rec.get("wheelchair") or {},
                "toilets": rec.get("toilets") or {},
                "platform": rec.get("platform") or {},
                "step": rec.get("step") or {},
                "floorPlan": rec.get("floorPlan"),
                "links": {"ecomo": cache.get("ecomoUrl"),
                          "operator": rec.get("operatorUrl")},
                "sources": ["ecomo-rakuraku"],
                "updatedAt": cache.get("fetchedAt", "")[:10],
            }
            # normalize any relative /ecomo URL to absolute (avoid broken links on our site)
            def _abs(u):
                if u and isinstance(u, str) and u.startswith("/"):
                    return "https://www.ecomo-rakuraku.jp" + u
                return u
            if isinstance(entry.get("floorPlan"), dict):
                fp = dict(entry["floorPlan"])
                fp["pageUrl"] = _abs(fp.get("pageUrl"))
                entry["floorPlan"] = fp
            # overlay floor-plan image (with exits labeled) from cache_map
            mcp = map_cache_path(name)
            if os.path.exists(mcp):
                try:
                    md = json.load(open(mcp, encoding="utf-8"))
                    fp = dict(entry.get("floorPlan") or {})
                    if md.get("imageUrl"): fp["imageUrl"] = md["imageUrl"]
                    if md.get("pdfUrl"): fp["pdfUrl"] = md["pdfUrl"]
                    if md.get("mapPageUrl") and not fp.get("pageUrl"):
                        fp["pageUrl"] = md["mapPageUrl"]
                    # normalize relative URLs to absolute ecomo URLs
                    def _abs(u):
                        if u and isinstance(u, str) and u.startswith("/"):
                            return "https://www.ecomo-rakuraku.jp" + u
                        return u
                    fp["pageUrl"] = _abs(fp.get("pageUrl"))
                    entry["floorPlan"] = fp
                except Exception:
                    pass
            out["stations"][name] = entry
        mapping[name] = m

    with open("data/station-guide.full.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    with open("data/mapping.json", "w", encoding="utf-8") as f:
        json.dump({"generatedAt": time.strftime("%Y-%m-%d"),
                   "site": "https://ooep.github.io/floral-salad-8734/mini-japanrail-3d/",
                   "keyField": "station名(=网站 normName)",
                   "stations": mapping}, f, ensure_ascii=False, separators=(",", ":"))

    print(f"build: {ok} stations with guide / {miss} without / {len(stations)} total")
    print(" -> data/station-guide.full.json")
    print(" -> data/mapping.json")


if __name__ == "__main__":
    sys.exit(main())
