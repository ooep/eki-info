#!/usr/bin/env bash
cd /home/user/Doubao/chats/38445328544708610/eki-info
while pgrep -f "scripts/scrape.py" > /dev/null; do sleep 60; done
echo "[watcher] scrape finished at $(date)" >> watcher.log
python3 scripts/build.py >> watcher.log 2>&1
git add data/
git -c user.email="bot@local" -c user.name="eki-bot" commit -q -m "data: 全量抓取完成 $(date -u +%Y-%m-%d)" >> watcher.log 2>&1 || echo "[watcher] nothing to commit" >> watcher.log
git push origin main >> watcher.log 2>&1
echo "[watcher] push done at $(date)" >> watcher.log
