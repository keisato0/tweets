#!/bin/bash
cd "$(dirname "$0")"

finish() {
  echo ""
  read -p "$1 Enterキーを押すとウィンドウを閉じます..." dummy
  exit "${2:-0}"
}

conflict_help() {
  echo ""
  echo "次のファイルで競合が起きています:"
  git diff --name-only --diff-filter=U | sed 's/^/  - /'
  echo ""
  echo "壊れた状態をコミットしないよう、ここで止めました。"
  echo "取り込みをやめて元に戻すには、ターミナルで次を実行してください:"
  echo "  git merge --abort"
}

echo "GitHubから最新の状態を取得します..."
echo ""

# 前回の取り込みが競合で止まったままなら、何もコミットせずに止める
if git rev-parse -q --verify MERGE_HEAD >/dev/null || [ -n "$(git diff --name-only --diff-filter=U)" ]; then
  echo "前回の取り込みが競合したまま終わっていません。"
  conflict_help
  finish "中断しました。" 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ローカルに未コミットの変更があります。先にコミットしてから取得します。"
  git add -A
  # 競合マーカー(<<<<<<< など)が残ったファイルはコミットしない
  markers=$(git diff --cached -U0 | grep -E '^\+(<{7}|>{7}) ')
  if [ -n "$markers" ]; then
    echo ""
    echo "競合マーカーが残っているファイルがあります:"
    git diff --cached --name-only -G'^(<{7}|>{7}) ' | sed 's/^/  - /'
    git reset -q
    finish "コミットせずに中断しました。" 1
  fi
  if ! git commit -m "ローカルの変更を保存 $(date '+%Y-%m-%d %H:%M')"; then
    finish "コミットに失敗したため中断しました。" 1
  fi
  echo ""
fi

if ! git pull; then
  if git rev-parse -q --verify MERGE_HEAD >/dev/null; then
    conflict_help
  else
    echo ""
    echo "取得に失敗しました。上のメッセージを確認してください。"
  fi
  finish "中断しました。" 1
fi

finish "完了しました。"
