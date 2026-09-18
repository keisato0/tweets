#!/bin/bash
cd "$(dirname "$0")"

(python3 compose_server.py > /tmp/tweets_compose_server.log 2>&1 &)
sleep 1
open "http://localhost:8765/"

# ブラウザを開いたら、このターミナルウィンドウ自体を閉じる(サーバーは裏で動き続ける)
MY_TTY=$(tty)
osascript <<EOF
tell application "Terminal"
  repeat with w in windows
    repeat with t in tabs of w
      if tty of t is "$MY_TTY" then
        close w
      end if
    end repeat
  end repeat
end tell
EOF
