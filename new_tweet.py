#!/usr/bin/env python3
"""
ターミナルでその場で新しいつぶやきを入力し、tweets.txt に追記するスクリプト。
複数行の入力に対応(空行で入力終了)。tweets.txt の実際の生成・commit・push は
行わない(それは post.sh の役割)。
"""
import sys

import generate


def read_multiline():
    print("新しいツイートを入力してください(複数行OK)。")
    print("入力し終えたら空行でEnter。何も入力せず空行だけEnterで中止します。")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


def append_tweet(text):
    path = generate.TWEET_FILE
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    if content and not content.endswith("\n"):
        content += "\n"
    if content and not content.endswith("\n\n"):
        content += "\n"
    content += text.rstrip("\n") + "\n"
    path.write_text(content, encoding="utf-8")


def main():
    text = read_multiline()
    if not text.strip():
        print("入力がなかったので中止しました。")
        sys.exit(1)

    print("\n----- 投稿内容 -----")
    print(text)
    print("--------------------")
    ans = input("この内容を投稿しますか? [y/N]: ").strip().lower()
    if ans != "y":
        print("中止しました。")
        sys.exit(1)

    append_tweet(text)
    print("tweets.txt に追記しました。続けてサイトを更新します。")


if __name__ == "__main__":
    main()
