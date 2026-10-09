#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 877 个缺失站尝试变体 URL 补抓。"""
import json, re, time, urllib.parse, subprocess, os, sys
sys.path.insert(0, 'scripts')
from scrape import parse_html, ECOMO_BASE, UA

miss = json.load(open('/tmp/missing.json', encoding='utf-8'))
KNOWN = {
  'JR難波': ['大阪難波'], 'JR小倉': ['小倉'], 'JR長瀬': ['長瀬'],
  'さっぽろ': ['札幌'], 'ひばりが丘': ['ひばりヶ丘'],
  'リゾートゲートウェイ･ステーション': ['リゾートゲートウェイ・ステーション'],
  'ベイサイド･ステーション': ['ベイサイド・ステーション'],
  'モノレール浜松町': ['浜松町'],
}
def variants(name):
    vs = [name]
    if name in KNOWN: vs += KNOWN[name]
    vs.append(name.replace('･','・'))
    if name.startswith('JR'): vs.append(name[2:])
    m = re.match(r"^(.*?)[（(][^）)]*[）)]$", name)
    if m:
        vs.append(m.group(1))
        vs.append(m.group(1).replace('･','・'))
    seen, out = set(), []
    for v in vs:
        if v and v not in seen: seen.add(v); out.append(v)
    return out

import hashlib
def cache_path(name):
    h = hashlib.md5(name.encode()).hexdigest()[:10]
    safe = re.sub(r'[^\w\-]', '_', name)
    return f"cache/{h}_{safe}.json"

recovered = 0
for i, name in enumerate(miss):
    for v in variants(name):
        url = ECOMO_BASE.format(urllib.parse.quote(v))
        r = subprocess.run(['curl','-s','-w','\n%{http_code}','-A',UA,'--max-time','12',url],
                           capture_output=True, text=True)
        body, code = r.stdout.rsplit('\n', 1)
        if code.strip() == '200' and 'section class="station"' in body:
            official, records = parse_html(body)
            with open(cache_path(name), 'w', encoding='utf-8') as f:
                json.dump({'station': name, 'status': 'ok', 'ecomoSlug': v, 'ecomoUrl': url,
                           'officialName': official, 'records': records,
                           'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%S')}, f, ensure_ascii=False, indent=1)
            recovered += 1
            print(f"[{i+1}/{len(miss)}] RECOVERED {name} -> {v}", flush=True)
            break
        time.sleep(0.3)
    if (i+1) % 100 == 0:
        print(f"progress {i+1}/{len(miss)}, recovered={recovered}", flush=True)

print(f"DONE recovered={recovered}/{len(miss)}")
