#!/bin/bash
cd "$(dirname "$0")"

echo "GitHubから最新の状態を取得します..."
echo ""

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ローカルに未コミットの変更があります。先にコミットしてから取得します。"
  git add -A
  git commit -m "ローカルの変更を保存 $(date '+%Y-%m-%d %H:%M')"
  echo ""
fi

git pull

echo ""
read -p "完了しました。Enterキーを押すとウィンドウを閉じます..." dummy
