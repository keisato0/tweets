#!/bin/bash
# 旧来投稿方法/tweets.txt の変更をサイトに反映して公開する。
# 使い方: 旧来投稿方法/tweets.txt を編集したら ./post.sh を実行するだけ。
set -e
cd "$(dirname "$0")"

python3 generate.py

git add -A
if git diff --cached --quiet; then
  echo "変更なし"
  exit 0
fi

git commit -m "つぶやきを追加 $(date '+%Y-%m-%d %H:%M')"
git push
