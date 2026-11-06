#!/usr/bin/env python3
"""
ローカルで投稿フォームとつぶやき一覧を提供する使い捨てサーバー。

使い方:
    python3 compose_server.py を実行(または Tweet.app をダブルクリック)して
    ブラウザで http://localhost:8765/ を開く。上の欄に書いて「投稿」を押すと
    追記され、下の一覧では各つぶやきの削除ができる。投稿でも削除でも
    git pull → tweets.txt の更新 → サイト生成 → commit・push まで自動で行う
    (スマホ編集などでリモートが進んでいても自動的に取り込んでからコミット
    する)。しばらく操作がない場合はタイムアウトでサーバーが自動終了する。

    この画面はローカルからしか開けない。公開されるサイトには削除ボタンは
    付かない。
"""
import http.server
import json
import re
import socketserver
import subprocess
import threading
from pathlib import Path

import generate

PORT = 8765
ROOT = Path(__file__).resolve().parent
IDLE_TIMEOUT_SEC = 15 * 60

# サイト本体のCSSと画像をこのサーバーからも配れるようにする
# (一覧を公開サイトと同じ見た目で表示するため)
STATIC_TYPES = {
    "/style.css": "text/css; charset=utf-8",
    "/icon.jpg": "image/jpeg",
}
IMAGE_PATH_RE = re.compile(r"^/images/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)$")
IMAGE_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "webp": "image/webp",
}

PAGE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>つぶやきの投稿と削除</title>
<link rel="stylesheet" href="/style.css">
<link rel="icon" href="/icon.jpg">
<style>
  /* 投稿欄。サイト本体にはない画面なので、ここだけ個別に書く */
  .compose { padding:16px; border-bottom:1px solid var(--border); }
  .compose textarea { width:100%; min-height:120px; font-size:16px; padding:12px;
             border:1px solid var(--border); border-radius:8px; box-sizing:border-box;
             resize:vertical; font-family:inherit; }
  .compose textarea:focus { outline:2px solid var(--blue); }
  .compose button { margin-top:12px; background:var(--blue); color:#fff; border:none;
           padding:10px 24px; border-radius:20px; font-size:15px; font-weight:bold;
           cursor:pointer; }
  .compose button:disabled { opacity:0.5; cursor:default; }
  #status { margin-top:12px; font-size:14px; color:var(--sub); white-space:pre-wrap; }
  #status.error { color:#e0245e; }

  /* 一覧。つぶやき1件ごとに、右上へ削除ボタンを重ねる */
  .tweet-row { position:relative; }
  .tweet-row .del { position:absolute; top:10px; right:10px;
           display:flex; align-items:center; justify-content:center;
           width:32px; height:32px; padding:0; border:none; border-radius:50%;
           background:transparent; color:var(--sub); cursor:pointer; }
  .tweet-row .del:hover { background:#fde8ef; color:#e0245e; }
  .tweet-row .del:disabled { opacity:0.4; cursor:default; }
  .tweet-row .del svg { width:18px; height:18px; fill:currentColor; }
  #listStatus { padding:16px; font-size:14px; color:var(--sub); }
</style>
</head>
<body>
<div class="container">
  <header class="site-header site-top">
    <div class="site-title">
      <h1>つぶやき</h1>
      <p class="tweet-count" id="count"></p>
    </div>
  </header>

  <div class="compose">
    <textarea id="text" placeholder="いまどうしてる?" autofocus></textarea><br>
    <button id="postBtn" onclick="post()">投稿</button>
    <div id="status"></div>
  </div>

  <div id="listStatus">読み込み中...</div>
  <main class="timeline" id="list"></main>
</div>

<script>
const TRASH = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zM6 9h12l-1 12H7L6 9zm3 2v8h2v-8H9zm4 0v8h2v-8h-2z"/></svg>';

function setStatus(msg, isError) {
  const el = document.getElementById('status');
  el.className = isError ? 'error' : '';
  el.textContent = msg;
}

async function loadList() {
  const listStatus = document.getElementById('listStatus');
  try {
    const res = await fetch('/tweets');
    const data = await res.json();
    if (!data.ok) { throw new Error(data.error); }
    document.getElementById('count').textContent = data.items.length + '件のツイート';
    const list = document.getElementById('list');
    list.innerHTML = '';
    for (const item of data.items) {
      const row = document.createElement('div');
      row.className = 'tweet-row';
      row.innerHTML = item.html;
      const btn = document.createElement('button');
      btn.className = 'del';
      btn.title = '削除';
      btn.setAttribute('aria-label', 'このつぶやきを削除');
      btn.innerHTML = TRASH;
      btn.addEventListener('click', () => del(item.index, item.text, btn));
      row.appendChild(btn);
      list.appendChild(row);
    }
    listStatus.hidden = true;
  } catch (e) {
    listStatus.hidden = false;
    listStatus.textContent = '一覧を読み込めませんでした: ' + e;
  }
}

async function del(index, text, btn) {
  const head = text.length > 40 ? text.slice(0, 40) + '…' : text;
  if (!confirm('このつぶやきを削除します。元に戻せません。\\n\\n' + head)) { return; }
  btn.disabled = true;
  setStatus('削除中...');
  try {
    const res = await fetch('/delete', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({index, text})
    });
    const data = await res.json();
    if (data.ok) {
      setStatus('削除しました。');
      await loadList();
    } else {
      setStatus('エラー: ' + data.error, true);
      btn.disabled = false;
    }
  } catch (e) {
    setStatus('通信エラー: ' + e, true);
    btn.disabled = false;
  }
}

async function post() {
  const textEl = document.getElementById('text');
  const text = textEl.value;
  if (!text.trim()) { return; }
  const btn = document.getElementById('postBtn');
  btn.disabled = true;
  setStatus('投稿中...');
  try {
    const res = await fetch('/post', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    });
    const data = await res.json();
    if (data.ok) {
      setStatus('投稿しました。続けて次のツイートを書けます。');
      textEl.value = '';
      textEl.focus();
      await loadList();
    } else {
      setStatus('エラー: ' + data.error, true);
    }
  } catch (e) {
    setStatus('通信エラー: ' + e, true);
  }
  btn.disabled = false;
}

document.getElementById('text').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { post(); }
});
loadList();
</script>
</body>
</html>
"""


def append_tweet(text):
    path = generate.TWEET_FILE
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    if content and not content.endswith("\n"):
        content += "\n"
    if content and not content.endswith("\n\n"):
        content += "\n"
    content += text.rstrip("\n") + "\n"
    path.write_text(content, encoding="utf-8")


def run_generate():
    subprocess.run(
        ["python3", "generate.py"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    )


def load_tweets_with_timestamps():
    """(本文, 投稿日時) の組を古い順に返す。日時がまだ割り当てられていない
    つぶやきがある場合は、先に generate.py を実行して割り当てさせる。"""
    tweets = generate.load_tweets()
    timestamps = generate.load_state().get("timestamps", [])
    if len(timestamps) < len(tweets):
        run_generate()
        tweets = generate.load_tweets()
        timestamps = generate.load_state().get("timestamps", [])
    return list(zip(tweets, timestamps))


def list_payload():
    """一覧に出すデータ。新しいものが先頭。index は tweets.txt での位置
    (古いものが0)で、削除のときにそのまま送り返す。"""
    pairs = load_tweets_with_timestamps()
    items = []
    for i in range(len(pairs) - 1, -1, -1):
        text, ts = pairs[i]
        items.append(
            {
                "index": i,
                "text": text,
                "html": generate.render_tweet_html(text, ts, "/icon.jpg", "/"),
            }
        )
    return {"ok": True, "items": items}


def delete_tweet(index, text):
    """tweets.txt と state.json から、同じ位置の本文と日時を取り除く。

    state.json の日時はつぶやきの順番と1対1で対応している。本文だけを消すと
    generate.py が末尾の日時を切り捨てるため、それ以降の日付がすべてずれる。
    必ず両方から同じ位置を取り除くこと。"""
    tweets = generate.load_tweets()
    state = generate.load_state()
    timestamps = state.get("timestamps", [])
    if len(timestamps) != len(tweets):
        raise ValueError(
            "tweets.txt と state.json の件数が合いません。"
            "先に generate.py を実行してください。"
        )
    if not (0 <= index < len(tweets)) or tweets[index] != text:
        # 一覧を開いたあとに順番が変わっていた場合に備えて、本文で探し直す
        matches = [i for i, t in enumerate(tweets) if t == text]
        if len(matches) != 1:
            raise ValueError(
                "削除するつぶやきを特定できません。画面を再読み込みしてください。"
            )
        index = matches[0]

    removed = tweets.pop(index)
    timestamps.pop(index)
    generate.TWEET_FILE.write_text(
        ("\n\n".join(tweets) + "\n") if tweets else "", encoding="utf-8"
    )
    state["timestamps"] = timestamps
    generate.save_state(state)
    return removed


class ReusableServer(socketserver.TCPServer):
    allow_reuse_address = True


def reset_idle_timer(httpd):
    old = getattr(httpd, "idle_timer", None)
    if old is not None:
        old.cancel()
    timer = threading.Timer(IDLE_TIMEOUT_SEC, httpd.shutdown)
    timer.daemon = True
    timer.start()
    httpd.idle_timer = timer


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_bytes(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, status=200):
        self._send_bytes(
            json.dumps(obj, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
            status,
        )

    def _send_file(self, rel_path, content_type):
        path = ROOT / rel_path
        if not path.is_file():
            self.send_response(404)
            self.end_headers()
            return
        self._send_bytes(path.read_bytes(), content_type)

    def do_GET(self):
        if self.path == "/":
            self._send_bytes(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path in STATIC_TYPES:
            self._send_file(self.path.lstrip("/"), STATIC_TYPES[self.path])
            return
        if IMAGE_PATH_RE.match(self.path):
            ext = self.path.rsplit(".", 1)[1].lower()
            self._send_file(self.path.lstrip("/"), IMAGE_TYPES[ext])
            return
        if self.path == "/tweets":
            try:
                self._send_json(list_payload())
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)
            finally:
                reset_idle_timer(self.server)
            return
        self.send_response(404)
        self.end_headers()

    def _git(self, *args):
        subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        )

    def _publish(self, message):
        """サイトを生成しなおして、コミットとpushまで行う。"""
        run_generate()
        self._git("add", "-A")
        self._git("commit", "-m", message)
        self._git("push")

    def do_POST(self):
        if self.path not in ("/post", "/delete"):
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        try:
            data = json.loads(raw.decode("utf-8"))

            # スマホ編集などでリモートが進んでいる場合に備え、
            # 手を加える前に最新の状態を取り込んでおく
            self._git("pull", "--no-rebase")

            if self.path == "/post":
                text = data.get("text", "").strip()
                if not text:
                    raise ValueError("投稿内容が空です")
                append_tweet(text)
                self._publish("つぶやきを追加(webフォーム)")
            else:
                text = data.get("text", "")
                index = data.get("index")
                if not isinstance(index, int):
                    raise ValueError("削除する位置が指定されていません")
                delete_tweet(index, text)
                self._publish("つぶやきを削除(webフォーム)")

            self._send_json({"ok": True})
            reset_idle_timer(self.server)
        except subprocess.CalledProcessError as e:
            self._send_json(
                {"ok": False, "error": f"{e.cmd}: {e.stderr or e.stdout}"},
                status=500,
            )
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)}, status=500)


def main():
    with ReusableServer(("127.0.0.1", PORT), Handler) as httpd:
        reset_idle_timer(httpd)
        print(f"http://localhost:{PORT}/ を開いてください")
        try:
            httpd.serve_forever()
        finally:
            httpd.idle_timer.cancel()


if __name__ == "__main__":
    main()
