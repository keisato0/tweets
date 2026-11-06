#!/bin/bash
# tweet_launcher.swift から Tweet.app の中身を作り直す。
# ソースを直したらこれを実行すること(コンパイル + 署名まで行う)。
set -euo pipefail
cd "$(dirname "$0")"
swiftc -O -o Tweet.app/Contents/MacOS/Tweet tweet_launcher.swift
codesign -f -s - Tweet.app
echo "Tweet.app を作り直しました"
