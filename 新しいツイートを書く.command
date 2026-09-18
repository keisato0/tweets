#!/bin/bash
cd "$(dirname "$0")"

python3 new_tweet.py
status=$?

echo ""
if [ $status -ne 0 ]; then
  read -p "Enterキーを押すとウィンドウを閉じます..." dummy
  exit 0
fi

./post.sh

echo ""
read -p "完了しました。Enterキーを押すとウィンドウを閉じます..." dummy
