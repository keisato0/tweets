#!/usr/bin/env python3
"""
tweet.txt からつぶやきを読み込み、旧Twitter風の静的サイトを生成するスクリプト。

使い方:
    tweet.txt に空行区切りでつぶやきを追記してから、以下を実行する。

        python3 generate.py

    実行するたびに index.html と archive/pageN.html を再生成する。
    新しく追加されたつぶやきには「実行時刻」が投稿日時として割り当てられ、
    state.json に記録される(次回以降の実行では上書きされない)。
    state.json は必ずコミットすること。
"""
import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TWEET_FILE = ROOT / "tweet.txt"
STATE_FILE = ROOT / "state.json"
ARCHIVE_DIR = ROOT / "archive"
TZ = ZoneInfo("Asia/Tokyo")
PAGE_SIZE = 100

DISPLAY_NAME = "Kei Sato"
HANDLE = "@keisato0"
SITE_TITLE = "近況"


def load_tweets():
    if not TWEET_FILE.exists():
        return []
    text = TWEET_FILE.read_text(encoding="utf-8")
    blocks = [b.strip("\n") for b in text.split("\n\n")]
    # さらに空行がまとまっている場合に備えて、空要素と前後の空白を除去
    tweets = []
    for b in blocks:
        b = b.strip("\n")
        b = b.strip()
        if b:
            tweets.append(b)
    return tweets


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"timestamps": []}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sync_timestamps(tweets, state):
    timestamps = state.get("timestamps", [])
    # 末尾が削除/編集された場合はそのまま切り詰める(古いタイムスタンプは維持)
    if len(timestamps) > len(tweets):
        timestamps = timestamps[: len(tweets)]
    if len(timestamps) < len(tweets):
        now = datetime.now(TZ).isoformat()
        added = len(tweets) - len(timestamps)
        timestamps.extend([now] * added)
    state["timestamps"] = timestamps
    return timestamps


def format_datetime(iso_str):
    dt = datetime.fromisoformat(iso_str)
    return f"{dt.year}年{dt.month}月{dt.day}日 {dt.hour:02d}:{dt.minute:02d}"


def render_tweet_html(text, iso_str):
    body = html.escape(text).replace("\n", "<br>")
    date_label = format_datetime(iso_str)
    return f"""    <article class="tweet">
      <div class="tweet-header">
        <div class="avatar">{html.escape(DISPLAY_NAME[:1])}</div>
        <div class="tweet-names">
          <span class="name">{html.escape(DISPLAY_NAME)}</span>
          <span class="handle">{html.escape(HANDLE)}</span>
        </div>
      </div>
      <div class="tweet-body">{body}</div>
      <div class="tweet-date">{date_label}</div>
    </article>
"""


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{css_path}">
</head>
<body>
<div class="container">
  <header class="site-header">
    <h1>{site_title}</h1>
  </header>
  <main class="timeline">
{tweets_html}  </main>
{nav_html}
  <footer class="site-footer">
    <a href="{index_path}">&larr; 最新のつぶやきへ戻る</a>
  </footer>
</div>
</body>
</html>
"""


def build_page(tweets_with_ts, title, css_path, index_path, nav_html=""):
    tweets_html = "".join(
        render_tweet_html(text, ts) for text, ts in tweets_with_ts
    )
    return PAGE_TEMPLATE.format(
        title=html.escape(title),
        css_path=css_path,
        site_title=html.escape(SITE_TITLE),
        display_name=html.escape(DISPLAY_NAME),
        handle=html.escape(HANDLE),
        tweets_html=tweets_html,
        nav_html=nav_html,
        index_path=index_path,
    )


def main():
    tweets = load_tweets()
    state = load_state()
    timestamps = sync_timestamps(tweets, state)
    save_state(state)

    # 新しい順(最新が先頭)の (text, timestamp) タプル列
    newest_first = list(zip(tweets, timestamps))[::-1]

    latest = newest_first[:PAGE_SIZE]
    older = newest_first[PAGE_SIZE:]

    pages = []
    idx = 0
    while idx < len(older):
        pages.append(older[idx : idx + PAGE_SIZE])
        idx += PAGE_SIZE

    if ARCHIVE_DIR.exists():
        for f in ARCHIVE_DIR.glob("page*.html"):
            f.unlink()
    ARCHIVE_DIR.mkdir(exist_ok=True)

    # アーカイブページ本体を生成
    total_pages = len(pages)
    for i, page_tweets in enumerate(pages, start=2):  # page2, page3, ...
        first_no = PAGE_SIZE + (i - 2) * PAGE_SIZE + 1
        last_no = first_no + len(page_tweets) - 1
        prev_link = (
            f'../index.html' if i == 2 else f'page{i - 1}.html'
        )
        next_link = f"page{i + 1}.html" if i - 2 < total_pages - 1 else None
        nav_parts = [f'<a href="{prev_link}">&laquo; 新しいつぶやき</a>']
        if next_link:
            nav_parts.append(f'<a href="{next_link}">古いつぶやき &raquo;</a>')
        nav_html = f'  <nav class="pager">{"".join(nav_parts)}</nav>\n'
        page_html = build_page(
            page_tweets,
            title=f"{SITE_TITLE} ({first_no}〜{last_no}件目)",
            css_path="../style.css",
            index_path="../index.html",
            nav_html=nav_html,
        )
        (ARCHIVE_DIR / f"page{i}.html").write_text(page_html, encoding="utf-8")

    # index.html 用: 最新100件のあとにアーカイブリンク一覧
    archive_links_html = ""
    if pages:
        items = []
        for i, page_tweets in enumerate(pages, start=2):
            first_no = PAGE_SIZE + (i - 2) * PAGE_SIZE + 1
            last_no = first_no + len(page_tweets) - 1
            oldest_date = format_datetime(page_tweets[-1][1])
            newest_date = format_datetime(page_tweets[0][1])
            items.append(
                f'      <li><a href="archive/page{i}.html">'
                f"{first_no}〜{last_no}件目 "
                f"({oldest_date} 〜 {newest_date})</a></li>\n"
            )
        archive_links_html = (
            '  <section class="archive-list">\n'
            "    <h2>過去のつぶやき</h2>\n"
            "    <ul>\n" + "".join(items) + "    </ul>\n"
            "  </section>\n"
        )

    index_tweets_html = "".join(
        render_tweet_html(text, ts) for text, ts in latest
    )
    index_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(SITE_TITLE)}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<div class="container">
  <header class="site-header">
    <h1>{html.escape(SITE_TITLE)}</h1>
  </header>
  <main class="timeline">
{index_tweets_html}  </main>
{archive_links_html}</div>
</body>
</html>
"""
    (ROOT / "index.html").write_text(index_html, encoding="utf-8")

    print(f"tweets: {len(tweets)} 件 / archive pages: {len(pages)}")


if __name__ == "__main__":
    main()
