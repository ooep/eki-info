#!/usr/bin/env python3
"""Concurrent floor-plan enrichment: fetch each station's station_map page
and extract the /static/stationmap/map/<id>.jpg floor plan image."""
import os, re, json, hashlib, urllib.request, urllib.parse, glob
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_DIR = 'cache'
MAP_CACHE = 'cache_map'
os.makedirs(MAP_CACHE, exist_ok=True)

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'ignore')

def safe_name(name):
    h = hashlib.md5(name.encode('utf-8')).hexdigest()[:10]
    return os.path.join(MAP_CACHE, f'{h}_{re.sub(r"[^\w\-]", "_", name)}.json')

stations = []
for cp in glob.glob(os.path.join(CACHE_DIR, '*.json')):
    try:
        d = json.load(open(cp, encoding='utf-8'))
    except Exception:
        continue
    if d.get('status') != 'ok':
        continue
    name = d.get('station')
    if name:
        stations.append(name)
stations = sorted(set(stations))
print(f'stations to enrich: {len(stations)}', flush=True)

def process(name):
    mcp = safe_name(name)
    if os.path.exists(mcp):
        try:
            d = json.load(open(mcp, encoding='utf-8'))
            return name, d.get('imageUrl') is not None
        except Exception:
            pass
    try:
        enc = urllib.parse.quote(name)
        page = http_get(f'https://www.ecomo-rakuraku.jp/ja/station/{enc}/')
        # pick the station-specific map link, not the generic ?aiueo= entry
        cands = re.findall(r'station_map/([^?"\'>\s/]+)', page)
        m = cands[0] if cands else None
        if m:
            sm_url = f'https://www.ecomo-rakuraku.jp/ja/station_map/{m}/'
            sm = http_get(sm_url)
            img = re.search(r'stationmap/map/\d+\.(?:jpg|png)', sm)
            pdf = re.search(r'stationmap/pdf/\d+\.pdf', sm)
            img_url = ('https://www.ecomo-rakuraku.jp/static/' + img.group(0)) if img else None
            pdf_url = ('https://www.ecomo-rakuraku.jp/static/' + pdf.group(0)) if pdf else None
        else:
            img_url = pdf_url = sm_url = None
        json.dump({'name': name, 'imageUrl': img_url, 'pdfUrl': pdf_url, 'mapPageUrl': sm_url},
                  open(mcp, 'w', encoding='utf-8'), ensure_ascii=False)
        return name, img_url is not None
    except Exception as e:
        json.dump({'name': name, 'imageUrl': None, 'error': str(e)[:100]},
                  open(mcp, 'w', encoding='utf-8'), ensure_ascii=False)
        return name, False

done = 0; have_img = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(process, n): n for n in stations}
    for fut in as_completed(futs):
        name, ok = fut.result()
        done += 1
        if ok: have_img += 1
        if done % 500 == 0:
            print(f'progress {done}/{len(stations)}, with_image={have_img}', flush=True)

print(f'DONE: {done} stations, {have_img} with floor plan image', flush=True)
