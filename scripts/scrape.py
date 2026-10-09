#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape.py — 全量抓取 ecomo-rakuraku 车站信息（带断点续传）

输入: data/master_stations.json (由 fetch_master.py 生成)
输出: cache/<sanitized_name>.json  每站一个缓存文件（断点续传）

行为:
  - 对每个站先试 /ja/station/<站名>/；404 时尝试去括号等变体。
  - 已存在 cache 文件的站跳过（--force 可重抓）。
  - 礼貌限速 0.6s/请求；失败自动重试 1 次。
  - 运行结束打印成功/失败统计。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

ECOMO_BASE = "https://www.ecomo-rakuraku.jp/ja/station/{}/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
INTERVAL = 0.6
CACHE_DIR = "cache"


# ---------------------------------------------------------------- fetch
def fetch(url, retries=1, timeout=20):
    headers = {"User-Agent": UA, "Accept-Language": "ja,en;q=0.9"}
    last = None
    for i in range(retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.text
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(INTERVAL * (i + 2))
    return None


def candidate_urls(name):
    """ecomo URL 候选：原名、去括号名、去 JR 前缀名。
    网站主清单里部分站带 'JR' 前缀消歧（JR淡路 vs 阪急淡路），
    ecomo 实际 URL 不带该前缀；京成/京急/京王 等前缀是正式站名，不去。
    """
    variants = [name]
    if name.startswith("JR"):
        variants.append(name[2:])
    m = re.match(r"^(.*?)[（(][^）)]*[）)]$", name)
    if m:
        variants.append(m.group(1))
        if m.group(1).startswith("JR"):
            variants.append(m.group(1)[2:])
    seen, out = set(), []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return [(v, ECOMO_BASE.format(quote(v))) for v in out]


# ------------------------------------------------------- icon semantics
def icon_value(dd):
    if dd is None:
        return None
    img = dd.find("img")
    if img is not None:
        alt = (img.get("alt") or "").strip()
        if not alt:
            return None
        if "あります" in alt:
            return True
        if "情報はありません" in alt or "情報がありません" in alt:
            return None
        if "ありません" in alt:
            return False
        if "介助が必要" in alt:
            return "介助が必要"
        return alt
    return dd.get_text(" ", strip=True) or None


def dl_rows(dl):
    rows = []
    for dt in dl.find_all("dt", recursive=False):
        dd = dt.find_next_sibling("dd")
        while dd is not None:
            rows.append((dt.get_text(" ", strip=True), dd))
            nxt = dd.find_next_sibling()
            while nxt is not None and nxt.name not in ("dt", "dd"):
                nxt = nxt.find_next_sibling()
            if nxt is None or nxt.name == "dt":
                break
            dd = nxt
    return rows


def parse_section(section):
    rec = {"operator": "", "lines": [], "basic": {}, "wheelchair": {},
           "toilets": {"inside": {}, "outside": {}}, "platform": {},
           "step": {}, "floorPlan": None, "operatorUrl": None}
    h3 = section.select_one("h3.content-station-ttl")
    if h3:
        text = h3.get_text(" ", strip=True)
        groups = re.findall(r"【(.*?)】", text)
        if groups:
            rec["lines"] = [x.strip() for x in re.split(r"[・/]", groups[0]) if x.strip()]
            rec["operator"] = groups[-1].strip()
    for dl in section.find_all("dl"):
        h4 = dl.find_previous("h4")
        title = h4.get_text(" ", strip=True) if h4 else ""
        if title == "基本情報":
            for dt, dd in dl_rows(dl):
                if dt == "所在地":
                    rec["basic"]["address"] = dd.get_text(" ", strip=True)
                elif dt == "連絡先":
                    rec["basic"]["tel"] = dd.get_text(" ", strip=True)
            continue
        if "車椅子での移動情報" in title:
            for dt, dd in dl_rows(dl):
                if dt == "利用に関して":
                    rec["wheelchair"]["note"] = icon_value(dd)
                elif dt:
                    rec["wheelchair"][dt] = icon_value(dd)
            continue
        if "トイレ" in title:
            for row in dl.select(".toilet-list.bottom"):
                nm = row.select_one("dt").get_text(" ", strip=True)
                dds = row.select("dd")
                rec["toilets"]["inside"][nm] = icon_value(dds[0]) if len(dds) > 0 else None
                rec["toilets"]["outside"][nm] = icon_value(dds[1]) if len(dds) > 1 else None
            sup = dl.select_one(".station-height dd")
            if sup and sup.get_text(strip=True):
                rec["toilets"]["note"] = sup.get_text(" ", strip=True)
            continue
        if "ホームドア" in title:
            for dt, dd in dl_rows(dl):
                if dt:
                    rec["platform"][dt] = icon_value(dd)
            continue
        if "段差" in title or "隙間" in title:
            for dt, dd in dl_rows(dl):
                if dt:
                    rec["step"][dt] = icon_value(dd)
            continue
    for h4 in section.find_all("h4"):
        if "構内図" in h4.get_text(" ", strip=True):
            block_text, a, img = "", None, None
            node = h4.find_next_sibling()
            while node is not None and node.name != "h4":
                block_text += node.get_text(" ", strip=True) + " "
                if a is None:
                    a = node.find("a")
                if img is None:
                    img = node.find("img")
                node = node.find_next_sibling()
            if "ございません" not in block_text:
                href = a.get("href") if a else None
                src = img.get("src") if img else None
                if src and src.startswith("/static/"):
                    src = None
                rec["floorPlan"] = {"pageUrl": href, "imageUrl": src,
                                    "note": block_text.strip()[:80] or None}
            break
    for h4 in section.find_all("h4"):
        if "関連するホームページ" in h4.get_text(" ", strip=True):
            block = h4.find_next_sibling()
            a = block.find("a") if block else None
            rec["operatorUrl"] = a.get("href") if a else None
            break
    return rec


def parse_html(html):
    soup = BeautifulSoup(html, "lxml")
    sections = soup.select("section.station")
    if not sections:
        return None, []
    out = []
    for s in sections:
        out.append(parse_section(s))
    name = None
    h3 = sections[0].select_one("h3.content-station-ttl")
    if h3:
        text = h3.get_text(" ", strip=True)
        groups = re.findall(r"【(.*?)】", text)
        if groups:
            inner = text
            for g in groups:
                inner = inner.replace(f"【{g}】", "", 1)
            name = inner.strip() or groups[0]
    return name, out


def cache_path(name):
    h = hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^\w\-]", "_", name)
    return os.path.join(CACHE_DIR, f"{h}_{safe}.json")


def scrape_one(station):
    """返回 cache dict。"""
    name = station["station"]
    for slug, url in candidate_urls(name):
        html = fetch(url)
        time.sleep(INTERVAL)
        if html is None:
            continue
        official_name, records = parse_html(html)
        if not records:
            continue
        return {
            "station": name,
            "status": "ok",
            "ecomoSlug": slug,
            "ecomoUrl": url,
            "officialName": official_name,
            "records": records,
            "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    return {
        "station": name, "status": "missing",
        "ecomoUrl": ECOMO_BASE.format(quote(name)),
        "records": [], "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="忽略已有缓存重抓")
    ap.add_argument("--limit", type=int, default=0, help="只抓前 N 个（调试用）")
    args = ap.parse_args()

    os.makedirs(CACHE_DIR, exist_ok=True)
    stations = json.load(open("data/master_stations.json", encoding="utf-8"))
    if args.limit:
        stations = stations[:args.limit]

    stats = {"ok": 0, "missing": 0, "cached": 0, "fail": 0}
    t0 = time.time()
    for i, st in enumerate(stations, 1):
        cp = cache_path(st["station"])
        if not args.force and os.path.exists(cp):
            stats["cached"] += 1
            continue
        rec = scrape_one(st)
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        stats[rec["status"]] = stats.get(rec["status"], 0) + 1
        if i % 25 == 0 or rec["status"] != "ok":
            el = time.time() - t0
            print(f"[{i}/{len(stations)}] {rec['station']}: {rec['status']} "
                  f"(elapsed {el/60:.1f}m, ok={stats['ok']} miss={stats['missing']})",
                  flush=True)

    print(f"\nDONE: ok={stats['ok']} missing={stats['missing']} cached={stats['cached']} "
          f"total={len(stations)} elapsed={(time.time()-t0)/60:.1f}min")


if __name__ == "__main__":
    sys.exit(main())
