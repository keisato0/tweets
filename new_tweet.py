#!/usr/bin/env python3
"""
TextEditで新しいつぶやきを作文し、ダイアログの「投稿」ボタンを押すだけで
tweets.txt に追記するスクリプト。ターミナルでの直接入力は行わない。
tweets.txt の実際の生成・commit・push は行わない(それは post.sh の役割)。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import generate


def run_osascript(script):
    return subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True
    )


def ask_compose():
    """TextEditを開き、投稿確認ダイアログを表示する。投稿ならTrue、中止ならFalse。"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    tmp.close()
    tmp_path = Path(tmp.name)

    subprocess.run(["open", "-e", str(tmp_path)])

    dialog_script = (
        'display dialog '
        '"TextEditが開きました。つぶやきを入力し、⌘S で保存してから'
        '「投稿」を押してください。" & return & return & '
        '"(複数行OK。キャンセルで中止します)" '
        'buttons {"キャンセル", "投稿"} default button "投稿" '
        'with title "新しいツイート" with icon note'
    )
    result = run_osascript(dialog_script)
    posted = result.returncode == 0 and "投稿" in result.stdout and "キャンセル" not in result.stdout

    # TextEditのウィンドウを閉じる(失敗しても無視)
    close_script = (
        f'tell application "TextEdit" to try\n'
        f'close (every document whose path is "{tmp_path}") saving no\n'
        f'end try'
    )
    subprocess.run(["osascript", "-e", close_script], capture_output=True, text=True)

    text = ""
    if posted and tmp_path.exists():
        text = tmp_path.read_text(encoding="utf-8").rstrip("\n")

    if tmp_path.exists():
        tmp_path.unlink()

    return (posted, text)


def append_tweet(text):
    path = generate.TWEET_FILE
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    if content and not content.endswith("\n"):
        content += "\n"
    if content and not content.endswith("\n\n"):
        content += "\n"
    content += text.rstrip("\n") + "\n"
    path.write_text(content, encoding="utf-8")


def notify(message):
    run_osascript(f'display notification "{message}" with title "つぶやき"')


def main():
    posted, text = ask_compose()
    if not posted:
        print("中止しました。")
        sys.exit(1)

    if not text.strip():
        print("入力が空だったので中止しました。")
        notify("入力が空だったので中止しました")
        sys.exit(1)

    print("----- 投稿内容 -----")
    print(text)
    print("--------------------")

    append_tweet(text)
    print("tweets.txt に追記しました。続けてサイトを更新します。")


if __name__ == "__main__":
    main()
