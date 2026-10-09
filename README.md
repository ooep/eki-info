# eki-info

全日本车站综合指南数据仓库 —— 为 [Mini JapanRail 3D](https://ooep.github.io/floral-salad-8734/mini-japanrail-3d/) 的「指南」tab 提供改札口・窓口・トイレ・バリアフリー・構内図・基本情報数据。

## 数据覆盖

- **车站主清单**：直接从网站 Pages 拉取 `data/stations3d.geojson`（当前 **8074 个独立车站**，含 JR 各社 / 私铁 / 地铁 / 第三部门）。
- **主数据源**：[ecomo-rakuraku](https://www.ecomo-rakuraku.jp/ja/station/)（公益財団法人交通エコロジー・モビリティ財団），字段统一覆盖全事业者：
  - 基本情報（所在地・連絡先）
  - 車椅子での移動情報（地上出入口～改札口 / 改札口～各ホーム / 各ホーム間）
  - トイレ（改札内・改札外 × トイレ / 車椅子対応 / オストメイト / ベビーベッド）
  - ホームドア設置状況・段差・隙間
  - 構内図外链/图片
- **覆盖率**：直连命中率约 90%（已实测样本）；其余为 ecomo 未收录或站名有歧义的小站，自动标记 `hasGuide: false`，前端优雅降级。

## 仓库结构

```
├── scripts/
│   ├── fetch_master.py     # 从网站 Pages 拉取车站主清单 → data/master_stations.json
│   ├── scrape.py           # 全量抓 ecomo（断点续传，cache/<hash>_<站名>.json）
│   └── build.py            # 聚合 cache → 最终 JSON
├── data/                   # 最终交付数据（入库）
│   ├── station-guide.full.json   # 前端直接消费，按站名索引
│   └── mapping.json              # 与网站的键映射 + 坐标/事业者
├── .github/workflows/update.yml  # 手动/每月自动全量重抓
└── requirements.txt
```

## 数据格式

```jsonc
// data/station-guide.full.json
{
  "schema": "station-guide/v2",
  "stations": {
    "新宿": {
      "name": "新宿",
      "key": "新宿",                    // = 网站 normName 站名
      "operator": "東日本旅客鉄道（JR東日本）",
      "lines": ["中央線"],
      "basic": { "address": "...", "tel": "..." },
      "wheelchair": { "地上出入口～改札口": true, ... },
      "toilets": { "inside":  {"トイレ": true, "車椅子対応": true, ...},
                   "outside": { ... } },
      "platform": { "ホームドア種別": ... },
      "step": { ... },
      "floorPlan": { "pageUrl": "...", "imageUrl": "..." },
      "links": { "ecomo": "...", "operator": "..." },
      "sources": ["ecomo-rakuraku"],
      "updatedAt": "2026-10-09"
    }
  }
}
```

## 本地跑

```bash
pip install -r requirements.txt
python3 scripts/fetch_master.py      # 拉主清单
python3 scripts/scrape.py            # 抓全量（断点续传，可中断重跑）
python3 scripts/build.py             # 聚合输出
```

## GitHub Action 手动更新

仓库页 → **Actions** → **全量更新车站指南数据** → **Run workflow**。

- 手动触发后约 1.5–3 小时跑完，自动把新的 `data/` 提交回 main。
- 每月 1 号 UTC 02:00 自动跑一次（可改 cron）。
- 全程限速 0.6s/请求，对源站友好。

## 前端接入

```js
// 站点抽屉打开时：
const guide = STATION_GUIDE.stations[stationName];   // 网站当前站名（normName 后）
if (guide) renderStationGuide(document.querySelector('#shBodyGuide'), guide);
```

## 合规

- 仅做只读抓取，限速请求；数据版权归各来源方（页面已保留 ecomo 与事业者官网链接）。
- 仓库不存抓取缓存，每次 Action 全新抓取，避免数据陈旧。
