#!/usr/bin/env python3
"""
ローカルで投稿フォームを提供する使い捨てサーバー。

使い方:
    python3 compose_server.py を実行(または compose.command をダブルクリック)
    してブラウザで http://localhost:8765/ を開き、テキストエリアに書いて
    「投稿」を押す。投稿のたびに git pull → tweets.txt への追記 → サイト生成 →
    commit・push まで自動で行われる(スマホ編集などでリモートが進んでいても
    自動的に取り込んでからコミットする)。投稿後もそのまま続けて次のツイート
    を書けるが、しばらく操作がない場合はタイムアウトでサーバーが自動終了する。
"""
import http.server
import json
import socketserver
import subprocess
import threading
from pathlib import Path

import generate

PORT = 8765
ROOT = Path(__file__).resolve().parent
IDLE_TIMEOUT_SEC = 15 * 60

PAGE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>新しいツイート</title>
<style>
  body { font-family: -apple-system, "Hiragino Sans", "Hiragino Kaku Gothic ProN", sans-serif;
         background:#e6ecf0; margin:0; padding:24px; }
  .box { max-width:600px; margin:0 auto; background:#fff; border:1px solid #e1e8ed;
         border-radius:12px; padding:20px; }
  h1 { font-size:18px; margin:0 0 16px; color:#14171a; }
  textarea { width:100%; min-height:160px; font-size:16px; padding:12px;
             border:1px solid #e1e8ed; border-radius:8px; box-sizing:border-box;
             resize:vertical; font-family:inherit; }
  textarea:focus { outline:2px solid #1b95e0; }
  button { margin-top:12px; background:#1b95e0; color:#fff; border:none;
           padding:10px 24px; border-radius:20px; font-size:15px; font-weight:bold;
           cursor:pointer; }
  button:disabled { opacity:0.5; cursor:default; }
  #status { margin-top:12px; font-size:14px; color:#657786; white-space:pre-wrap; }
  #status.error { color:#e0245e; }
</style>
</head>
<body>
<div class="box">
  <h1>新しいツイート</h1>
  <textarea id="text" placeholder="いまどうしてる?" autofocus></textarea><br>
  <button id="postBtn" onclick="post()">投稿</button>
  <div id="status"></div>
</div>
<script>
async function post() {
  const textEl = document.getElementById('text');
  const text = textEl.value;
  if (!text.trim()) { return; }
  const btn = document.getElementById('postBtn');
  const status = document.getElementById('status');
  btn.disabled = true;
  status.className = '';
  status.textContent = '投稿中...';
  try {
    const res = await fetch('/post', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    });
    const data = await res.json();
    if (data.ok) {
      status.textContent = '投稿しました。続けて次のツイートを書けます。';
      textEl.value = '';
      btn.disabled = false;
      textEl.focus();
    } else {
      status.className = 'error';
      status.textContent = 'エラー: ' + data.error;
      btn.disabled = false;
    }
  } catch (e) {
    status.className = 'error';
    status.textContent = '通信エラー: ' + e;
    btn.disabled = false;
  }
}
textAreaKeydown = (e) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { post(); }
};
document.getElementById('text').addEventListener('keydown', textAreaKeydown);
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

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/post":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        try:
            data = json.loads(raw.decode("utf-8"))
            text = data.get("text", "").strip()
            if not text:
                raise ValueError("投稿内容が空です")

            # スマホ編集などでリモートが進んでいる場合に備え、
            # 追記する前に最新の状態を取り込んでおく
            subprocess.run(
                ["git", "pull", "--no-rebase"], cwd=ROOT, check=True,
                capture_output=True, text=True,
            )

            append_tweet(text)
            subprocess.run(
                ["python3", "generate.py"], cwd=ROOT, check=True,
                capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "add", "-A"], cwd=ROOT, check=True,
                capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "つぶやきを追加(webフォーム)"],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "push"], cwd=ROOT, check=True,
                capture_output=True, text=True,
            )
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
