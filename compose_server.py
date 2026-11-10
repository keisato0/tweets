#!/usr/bin/env python3
"""
ローカルで投稿フォームとつぶやき一覧を提供する使い捨てサーバー。

使い方:
    python3 compose_server.py を実行(または Tweet.app をダブルクリック)して
    ブラウザで http://localhost:8765/ を開く。上の欄に書いて「投稿」を押すと
    追記され、下の一覧では各つぶやきの削除ができる。投稿でも削除でも
    git pull → tweets.txt の更新 → サイト生成 → commit・push まで自動で行う
    (スマホ編集などでリモートが進んでいても自動的に取り込んでからコミット
    する)。一覧を出すときも先に git pull して、スマホからの投稿を反映する。
    しばらく操作がない場合はタイムアウトでサーバーが自動終了する。

    この画面はローカルからしか開けない。公開されるサイトには削除ボタンは
    付かない。
"""
import base64
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
# 一覧を開くときの git pull を待つ上限(秒)。超えたらローカルの内容で一覧を出す
PULL_TIMEOUT_SEC = 10

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
<title>つぶやき</title>
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

  /* 引用するつぶやきを選んでいるときに、投稿欄の上に出すプレビュー */
  .quoting { display:flex; align-items:flex-start; gap:8px; margin-bottom:10px;
           padding:8px 10px; border:1px solid var(--border); border-radius:12px;
           background:#f5f8fa; font-size:14px; }
  .quoting .label { color:var(--sub); font-size:13px; white-space:nowrap; }
  .quoting .body { flex:1; min-width:0; overflow-wrap:anywhere; }
  .quoting .cancel { border:none; background:transparent; color:var(--sub);
           font-size:18px; line-height:1; padding:0 4px; cursor:pointer; }

  /* 添付画像。web版(post.html)と同じ見た目・同じ処理にそろえる */
  .compose-actions { display:flex; align-items:center; gap:12px; margin-top:12px; }
  .compose-actions button { margin-top:0; }
  label.attach { color:var(--blue); font-size:15px; cursor:pointer; padding:8px 4px; }
  label.attach.disabled { opacity:0.4; cursor:default; }
  #fileInput { display:none; }
  #previews { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
  #previews:empty { display:none; }
  .preview { position:relative; width:80px; height:80px; }
  .preview img { width:80px; height:80px; object-fit:cover; border-radius:8px;
           border:1px solid var(--border); }
  .preview .remove { position:absolute; top:2px; right:2px; margin:0; padding:0;
           width:22px; height:22px; border:none; border-radius:50%;
           background:rgba(0,0,0,0.6); color:#fff; font-size:14px; line-height:22px;
           font-weight:bold; cursor:pointer; }
  .preview .size { position:absolute; left:4px; bottom:4px; font-size:10px; color:#fff;
           background:rgba(0,0,0,0.6); border-radius:4px; padding:0 3px; }

  /* その場での編集 */
  .editing { padding:12px 16px; }
  .editing textarea { width:100%; min-height:80px; font-size:16px; padding:10px;
           border:1px solid var(--border); border-radius:8px; box-sizing:border-box;
           resize:vertical; font-family:inherit; }
  .editing textarea:focus { outline:2px solid var(--blue); }
  .edit-images { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
  .edit-images:empty { display:none; }
  .edit-quote { margin-top:8px; font-size:13px; color:var(--sub);
           display:flex; align-items:center; gap:6px; }
  .edit-quote:empty { display:none; }
  .edit-actions { display:flex; align-items:center; gap:12px; margin-top:10px; }
  .edit-actions button { background:var(--blue); color:#fff; border:none;
           padding:8px 20px; border-radius:18px; font-size:14px; font-weight:bold;
           cursor:pointer; font-family:inherit; }
  .edit-actions button:disabled { opacity:0.5; cursor:default; }
  .edit-actions button.plain { background:transparent; color:var(--sub);
           font-weight:normal; padding:8px 4px; }
  .edit-actions label.attach { margin-left:auto; }
  .tweet-row .edit { width:32px; border-radius:50%; }
  .tweet-row .edit:hover { background:#e8f5fd; color:var(--blue); }
  .tweet-row .edit svg { width:18px; height:18px; fill:currentColor; }

  /* 一覧。つぶやき1件ごとに、右上へ操作ボタンを重ねる */
  .tweet-row { position:relative; }
  .tweet-row .actions { position:absolute; top:10px; right:10px;
           display:flex; align-items:center; gap:4px; }
  .tweet-row .actions button { display:flex; align-items:center; justify-content:center;
           height:32px; padding:0; border:none; background:transparent;
           color:var(--sub); cursor:pointer; }
  .tweet-row .actions button:disabled { opacity:0.4; cursor:default; }
  .tweet-row .quote { width:32px; border-radius:50%; }
  .tweet-row .quote:hover { background:#e8f5fd; color:var(--blue); }
  .tweet-row .quote svg { width:18px; height:18px; fill:currentColor; }
  .tweet-row .del { width:32px; border-radius:50%; }
  .tweet-row .del:hover { background:#fde8ef; color:#e0245e; }
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
    <div class="quoting" id="quoting" hidden>
      <span class="label">引用:</span>
      <span class="body" id="quotingBody"></span>
      <button class="cancel" id="quotingCancel" title="引用をやめる"
              aria-label="引用をやめる">&times;</button>
    </div>
    <textarea id="text" placeholder="いまどうしてる?" autofocus></textarea>
    <div id="previews"></div>
    <div class="compose-actions">
      <button id="postBtn" onclick="post()">投稿</button>
      <label class="attach" id="attachLabel">画像を追加
        <input type="file" id="fileInput" accept="image/*" multiple>
      </label>
    </div>
    <div id="status"></div>
  </div>

  <div id="listStatus">読み込み中...</div>
  <main class="timeline" id="list"></main>
</div>

<script>
const RETWEET = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z"/></svg>';
const TRASH = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3h6l1 2h4v2H4V5h4l1-2zM6 9h12l-1 12H7L6 9zm3 2v8h2v-8H9zm4 0v8h2v-8h-2z"/></svg>';

function setStatus(msg, isError) {
  const el = document.getElementById('status');
  el.className = isError ? 'error' : '';
  el.textContent = msg;
}

let quoting = null;   // {id, text} 引用するつぶやきを選んでいる間だけ入る

function shorten(text, max) {
  return text.length > max ? text.slice(0, max) + '…' : text;
}

function setQuoting(item) {
  quoting = item ? {id: item.id, preview: item.preview} : null;
  const box = document.getElementById('quoting');
  if (quoting) {
    document.getElementById('quotingBody').textContent = shorten(quoting.preview, 60);
    box.hidden = false;
    document.getElementById('text').focus();
  } else {
    box.hidden = true;
  }
}

const PENCIL = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>';

let editing = null;   // 編集中のつぶやきの通し番号(同時に1件だけ)

// つぶやき1件ぶんの行を組み立てる
function buildRow(item) {
  const row = document.createElement('div');
  row.className = 'tweet-row';
  row.innerHTML = item.html;

  const actions = document.createElement('div');
  actions.className = 'actions';

  const editBtn = document.createElement('button');
  editBtn.className = 'edit';
  editBtn.innerHTML = PENCIL;
  editBtn.title = 'このつぶやきを編集';
  editBtn.setAttribute('aria-label', 'このつぶやきを編集');
  editBtn.addEventListener('click', () => startEdit(item, row));
  actions.appendChild(editBtn);

  const quoteBtn = document.createElement('button');
  quoteBtn.className = 'quote';
  quoteBtn.innerHTML = RETWEET;
  quoteBtn.title = 'このつぶやきを引用して書く';
  quoteBtn.setAttribute('aria-label', 'このつぶやきを引用して書く');
  quoteBtn.addEventListener('click', () => setQuoting(item));
  actions.appendChild(quoteBtn);

  const delBtn = document.createElement('button');
  delBtn.className = 'del';
  delBtn.innerHTML = TRASH;
  delBtn.title = '削除';
  delBtn.setAttribute('aria-label', 'このつぶやきを削除');
  delBtn.addEventListener('click', () => del(item, delBtn));
  actions.appendChild(delBtn);

  row.appendChild(actions);
  return row;
}

// 行をその場で編集欄に差し替える。本文だけを直せるようにして、画像と引用は
// 別に並べて外せるようにする([img:] や [rt:] の行を手で触らせない)
function startEdit(item, row) {
  if (editing !== null) {
    setStatus('ほかのつぶやきを編集中です。先にそちらを終えてください。', true);
    return;
  }
  editing = item.id;
  const keep = item.images.slice();     // 残す既存の画像
  const added = [];                     // 新しく足す画像 { blob, url }
  let quoteId = item.quote_id;

  row.innerHTML = '';
  const box = document.createElement('div');
  box.className = 'editing';

  const ta = document.createElement('textarea');
  ta.value = item.preview;
  box.appendChild(ta);

  const thumbs = document.createElement('div');
  thumbs.className = 'edit-images';
  box.appendChild(thumbs);

  const quoteBox = document.createElement('div');
  quoteBox.className = 'edit-quote';
  box.appendChild(quoteBox);

  const acts = document.createElement('div');
  acts.className = 'edit-actions';
  const saveBtn = document.createElement('button');
  saveBtn.textContent = '保存';
  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'plain';
  cancelBtn.textContent = 'やめる';
  const label = document.createElement('label');
  label.className = 'attach';
  label.textContent = '画像を追加';
  const fileIn = document.createElement('input');
  fileIn.type = 'file';
  fileIn.accept = 'image/*';
  fileIn.multiple = true;
  fileIn.style.display = 'none';
  label.appendChild(fileIn);
  acts.append(saveBtn, cancelBtn, label);
  box.appendChild(acts);
  row.appendChild(box);

  function thumb(src, onRemove, note) {
    const d = document.createElement('div');
    d.className = 'preview';
    const img = document.createElement('img');
    img.src = src;
    const rm = document.createElement('button');
    rm.className = 'remove';
    rm.textContent = '×';
    rm.title = 'この画像を外す';
    rm.onclick = onRemove;
    d.append(img, rm);
    if (note) {
      const s = document.createElement('span');
      s.className = 'size';
      s.textContent = note;
      d.appendChild(s);
    }
    return d;
  }

  function redraw() {
    thumbs.innerHTML = '';
    keep.forEach((path, i) => thumbs.appendChild(
      thumb('/' + path, () => { keep.splice(i, 1); redraw(); })));
    added.forEach((a, i) => thumbs.appendChild(
      thumb(a.url, () => { URL.revokeObjectURL(a.url); added.splice(i, 1); redraw(); },
            Math.round(a.blob.size / 1024) + 'KB')));
    const full = keep.length + added.length >= MAX_IMAGES;
    fileIn.disabled = full;
    label.classList.toggle('disabled', full);

    quoteBox.innerHTML = '';
    if (quoteId !== null && quoteId !== undefined) {
      const span = document.createElement('span');
      span.textContent = '引用: 通し番号 ' + quoteId;
      const rm = document.createElement('button');
      rm.className = 'plain';
      rm.style.padding = '0 4px';
      rm.textContent = '×';
      rm.title = '引用を外す';
      rm.onclick = () => { quoteId = null; redraw(); };
      quoteBox.append(span, rm);
    }
  }
  redraw();

  function finish() {
    editing = null;
    added.forEach(a => URL.revokeObjectURL(a.url));
  }

  fileIn.addEventListener('change', async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = '';
    const room = MAX_IMAGES - (keep.length + added.length);
    if (files.length > room) { setStatus(`画像は${MAX_IMAGES}枚までです。`, true); }
    for (const f of files.slice(0, room)) {
      setStatus('画像を処理中...');
      try {
        const blob = await processImage(f);
        added.push({ blob, url: URL.createObjectURL(blob) });
        setStatus('');
      } catch (err) {
        setStatus('画像を読み込めませんでした: ' + (err.message || err), true);
      }
    }
    redraw();
  });

  cancelBtn.addEventListener('click', () => {
    finish();
    row.replaceWith(buildRow(item));
    setStatus('');
  });

  saveBtn.addEventListener('click', async () => {
    saveBtn.disabled = true;
    cancelBtn.disabled = true;
    setStatus('保存中...');
    try {
      const newImages = [];
      for (let i = 0; i < added.length; i++) {
        newImages.push({ name: imageFileName(i), data: await blobToBase64(added[i].blob) });
      }
      const res = await fetch('/edit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          index: item.index,
          original_text: item.text,
          body: ta.value,
          keep_images: keep,
          new_images: newImages,
          quote_id: quoteId === undefined ? null : quoteId
        })
      });
      const data = await res.json();
      if (data.ok) {
        finish();
        setStatus('保存しました。');
        await loadList();
      } else {
        setStatus('エラー: ' + data.error, true);
        saveBtn.disabled = false;
        cancelBtn.disabled = false;
      }
    } catch (e) {
      setStatus('通信エラー: ' + e, true);
      saveBtn.disabled = false;
      cancelBtn.disabled = false;
    }
  });

  ta.focus();
}

async function loadList() {
  const listStatus = document.getElementById('listStatus');
  try {
    const res = await fetch('/tweets');
    const data = await res.json();
    if (!data.ok) { throw new Error(data.error); }
    editing = null;
    document.getElementById('count').textContent = data.items.length + '件のツイート';
    const list = document.getElementById('list');
    list.innerHTML = '';
    for (const item of data.items) { list.appendChild(buildRow(item)); }
    listStatus.hidden = true;
  } catch (e) {
    listStatus.hidden = false;
    listStatus.textContent = '一覧を読み込めませんでした: ' + e;
  }
}

async function del(item, btn) {
  let msg = 'このつぶやきを削除します。元に戻せません。\\n\\n' + shorten(item.preview, 40);
  if (item.quoted_by > 0) {
    msg += '\\n\\nこのつぶやきは' + item.quoted_by +
           '件から引用されています。引用側は「このつぶやきは削除されました」に変わります。';
  }
  if (!confirm(msg)) { return; }
  if (quoting && quoting.id === item.id) { setQuoting(null); }
  btn.disabled = true;
  setStatus('削除中...');
  try {
    const res = await fetch('/delete', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({index: item.index, text: item.text})
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

// ---- 添付画像の処理 ----
// web版(post.html)とまったく同じ手順にしてある。選ばれた画像は、大きさに
// かかわらず必ずcanvasに描き直してJPEGとして書き出す。これで長辺が
// MAX_EDGE以下に縮み、元ファイルのEXIF(GPS位置情報・撮影日時・機種名など)は
// 引き継がれない。さらに書き出したJPEGからJFIF以外のメタデータ領域を取り除き、
// 残っていないことを確かめてからでないとサーバーに送らない。

const MAX_IMAGES = 4;
const MAX_EDGE = 1600;        // 長辺の最大ピクセル数
const JPEG_QUALITY = 0.85;

let attachments = [];         // { blob, url }

async function decodeImage(file) {
  // imageOrientation: 'from-image' で、写真の向き(EXIF Orientation)を
  // ピクセルに反映した状態で読み込む(縦向き写真が横倒しにならない)
  if (window.createImageBitmap) {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' });
    } catch (e) { /* 下のフォールバックへ */ }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function processImage(file) {
  const src = await decodeImage(file);
  const w0 = src.width, h0 = src.height;
  const scale = Math.min(1, MAX_EDGE / Math.max(w0, h0));
  const w = Math.max(1, Math.round(w0 * scale));
  const h = Math.max(1, Math.round(h0 * scale));

  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#fff';   // 透過PNGの透明部分は白にする(JPEGは透過できない)
  ctx.fillRect(0, 0, w, h);
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(src, 0, 0, w, h);
  if (src.close) src.close();

  const blob = await new Promise((resolve, reject) =>
    canvas.toBlob(b => b ? resolve(b) : reject(new Error('JPEGへの変換に失敗しました')),
                  'image/jpeg', JPEG_QUALITY));
  const bytes = stripJpegMetadata(new Uint8Array(await blob.arrayBuffer()));
  assertNoMetadata(bytes);
  return new Blob([bytes], { type: 'image/jpeg' });
}

// JPEGのSOSより前にあるAPP1〜APP15(EXIF, XMP, ICC, IPTCなど)と
// COM(コメント)セグメントを取り除く。APP0(JFIF)と画像データは残す。
function stripJpegMetadata(b) {
  if (b[0] !== 0xFF || b[1] !== 0xD8) throw new Error('JPEGではありません');
  const out = [b.subarray(0, 2)];
  let i = 2;
  while (i < b.length) {
    if (b[i] !== 0xFF) throw new Error('JPEGの構造が不正です');
    const marker = b[i + 1];
    if (marker === 0xFF) { i++; continue; }
    if (marker === 0xDA) { out.push(b.subarray(i)); break; }
    const len = (b[i + 2] << 8) | b[i + 3];
    const seg = b.subarray(i, i + 2 + len);
    const isMeta = (marker >= 0xE1 && marker <= 0xEF) || marker === 0xFE;
    if (!isMeta) out.push(seg);
    i += 2 + len;
  }
  const total = out.reduce((n, a) => n + a.length, 0);
  const res = new Uint8Array(total);
  let off = 0;
  for (const a of out) { res.set(a, off); off += a.length; }
  return res;
}

// 取り除いた結果にメタデータ領域が残っていないことを確かめる
function assertNoMetadata(b) {
  let i = 2;
  while (i < b.length) {
    const marker = b[i + 1];
    if (marker === 0xDA) return;
    if ((marker >= 0xE1 && marker <= 0xEF) || marker === 0xFE) {
      throw new Error('画像のメタデータを削除できませんでした。この画像は投稿できません。');
    }
    i += 2 + ((b[i + 2] << 8) | b[i + 3]);
  }
}

function imageFileName(n) {
  const d = new Date();
  const p = x => String(x).padStart(2, '0');
  const stamp = `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-` +
                `${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
  const rand = Math.random().toString(36).slice(2, 8);
  return `images/${stamp}-${n + 1}-${rand}.jpg`;
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result.split(',')[1]);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

function renderPreviews() {
  const box = document.getElementById('previews');
  box.innerHTML = '';
  attachments.forEach((a, idx) => {
    const d = document.createElement('div');
    d.className = 'preview';
    const img = document.createElement('img');
    img.src = a.url;
    const size = document.createElement('span');
    size.className = 'size';
    size.textContent = Math.round(a.blob.size / 1024) + 'KB';
    const rm = document.createElement('button');
    rm.className = 'remove';
    rm.textContent = '×';
    rm.title = 'この画像を外す';
    rm.onclick = () => {
      URL.revokeObjectURL(a.url);
      attachments.splice(idx, 1);
      renderPreviews();
    };
    d.append(img, size, rm);
    box.appendChild(d);
  });
  const full = attachments.length >= MAX_IMAGES;
  document.getElementById('fileInput').disabled = full;
  document.getElementById('attachLabel').classList.toggle('disabled', full);
}

function clearAttachments() {
  attachments.forEach(a => URL.revokeObjectURL(a.url));
  attachments = [];
  renderPreviews();
}

async function onFilesSelected(e) {
  const files = Array.from(e.target.files || []);
  e.target.value = '';
  const room = MAX_IMAGES - attachments.length;
  if (files.length > room) {
    setStatus(`画像は${MAX_IMAGES}枚までです。`, true);
  }
  for (const file of files.slice(0, room)) {
    setStatus('画像を処理中...');
    try {
      const blob = await processImage(file);
      attachments.push({ blob, url: URL.createObjectURL(blob) });
      setStatus('');
    } catch (err) {
      setStatus('画像を読み込めませんでした: ' + (err.message || err), true);
    }
  }
  renderPreviews();
}

async function post() {
  const textEl = document.getElementById('text');
  const text = textEl.value;
  if (!text.trim() && attachments.length === 0) { return; }
  const btn = document.getElementById('postBtn');
  btn.disabled = true;
  setStatus('投稿中...');
  try {
    const images = [];
    for (let i = 0; i < attachments.length; i++) {
      images.push({
        name: imageFileName(i),
        data: await blobToBase64(attachments[i].blob)
      });
    }
    const res = await fetch('/post', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, images, quote_id: quoting ? quoting.id : null})
    });
    const data = await res.json();
    if (data.ok) {
      setStatus('投稿しました。続けて次のツイートを書けます。');
      textEl.value = '';
      clearAttachments();
      setQuoting(null);
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
document.getElementById('quotingCancel').addEventListener('click', () => setQuoting(null));
document.getElementById('fileInput').addEventListener('change', onFilesSelected);
loadList();
</script>
</body>
</html>
"""


# 添付画像として受け取れるファイル名。画面側が付ける名前の形に限定して、
# images/ の外に書き出されることがないようにする
IMAGE_NAME_RE = re.compile(r"^images/[A-Za-z0-9_-]+\.jpg$")
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def save_images(images):
    """画面から届いた画像を images/ に書き出し、本文に足す行を返す。
    画像はブラウザ側でJPEGに変換され、メタデータも除かれている。"""
    if not images:
        return []
    if len(images) > MAX_IMAGES:
        raise ValueError(f"画像は{MAX_IMAGES}枚までです")
    (ROOT / "images").mkdir(exist_ok=True)
    lines = []
    for item in images:
        name = item.get("name", "")
        if not IMAGE_NAME_RE.match(name):
            raise ValueError(f"画像のファイル名が不正です: {name}")
        raw = base64.b64decode(item.get("data", ""), validate=True)
        if not raw:
            raise ValueError("画像が空です")
        if len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("画像が大きすぎます")
        if raw[:2] != b"\xff\xd8":
            raise ValueError("JPEGではありません")
        (ROOT / name).write_bytes(raw)
        lines.append(f"[img:{name}]")
    return lines


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


def load_tweets_with_meta():
    """(本文, 投稿日時, 通し番号) の組を古い順に返す。日時や番号がまだ
    割り当てられていないつぶやきがある場合は、先に generate.py を実行させる。"""
    tweets = generate.load_tweets()
    state = generate.load_state()
    if (
        len(state.get("timestamps", [])) < len(tweets)
        or len(state.get("ids", [])) < len(tweets)
    ):
        run_generate()
        tweets = generate.load_tweets()
        state = generate.load_state()
    return list(zip(tweets, state["timestamps"], state["ids"]))


def count_quotes(triples):
    """番号ごとに、何件のつぶやきから引用されているかを数える。"""
    counts = {}
    for text, _ts, _tid in triples:
        body, _ = generate.split_images(text)
        _body, quote_id = generate.split_quote(body)
        if quote_id is not None:
            counts[quote_id] = counts.get(quote_id, 0) + 1
    return counts


def build_quote_index(triples):
    """引用カードを描くための対応表。generate.py と同じ中身を作る。"""
    total = len(triples)
    quotes = {}
    for i, (text, ts, tid) in enumerate(triples):
        body, images = generate.split_images(text)
        body, _ = generate.split_quote(body)
        quotes[tid] = {
            "body": body,
            "images": images,
            "date": generate.format_date(ts),
            "loc": generate.tweet_location(i, total),
        }
    return quotes


def list_payload():
    """一覧に出すデータ。新しいものが先頭。index は tweets.txt での位置
    (古いものが0)で、削除のときにそのまま送り返す。id は引用に使う通し番号。"""
    triples = load_tweets_with_meta()
    quotes = build_quote_index(triples)
    counts = count_quotes(triples)
    items = []
    for i in range(len(triples) - 1, -1, -1):
        text, ts, tid = triples[i]
        body, images = generate.split_images(text)
        body, quote_id = generate.split_quote(body)
        items.append(
            {
                "index": i,
                "id": tid,
                "images": images,
                "quote_id": quote_id,
                # text は tweets.txt の生のかたまり(削除時の照合に使う)、
                # preview は画像行や引用行を除いた本文(画面に出す用)
                "text": text,
                "preview": body,
                "quoted_by": counts.get(tid, 0),
                "html": generate.render_tweet_html(
                    text, ts, "/icon.jpg", "/", tid, quotes
                ),
            }
        )
    return {"ok": True, "items": items}


def quote_marker(quote_id):
    """引用元の番号を確かめて、本文の末尾に足す行を返す。"""
    ids = generate.load_state().get("ids", [])
    if quote_id not in ids:
        raise ValueError("引用するつぶやきが見つかりません。画面を再読み込みしてください。")
    # 空行をはさむと別のつぶやきとして分かれてしまうので、改行は1つにする
    # (tweets.txt は空行区切りで1件ずつに分かれる)
    return f"\n[rt:{quote_id}]"


# つぶやきは空行で区切られるので、本文の中に空行があると
# 1件が2件に分かれてしまう(日時や通し番号との対応が崩れる)
BLANK_LINE_RE = re.compile(r"\n[ \t]*\n")


def locate_tweet(tweets, index, text):
    """位置と本文の両方で照合して、書き換える場所を決める。
    一覧を開いたあとに順番が変わっていた場合は、本文で探し直す。"""
    if 0 <= index < len(tweets) and tweets[index] == text:
        return index
    matches = [i for i, t in enumerate(tweets) if t == text]
    if len(matches) != 1:
        raise ValueError(
            "対象のつぶやきを特定できません。画面を再読み込みしてください。"
        )
    return matches[0]


def edit_tweet(index, original_text, body, keep_images, new_image_lines, quote_id):
    """つぶやきの中身を書き換える。件数は変わらないので、state.json の
    timestamps と ids には手を触れない(投稿日時も通し番号もそのまま)。"""
    tweets = generate.load_tweets()
    state = generate.load_state()
    if (len(state.get("timestamps", [])) != len(tweets)
            or len(state.get("ids", [])) != len(tweets)):
        raise ValueError(
            "tweets.txt と state.json の件数が合いません。"
            "先に generate.py を実行してください。"
        )
    index = locate_tweet(tweets, index, original_text)

    body = body.strip()
    if BLANK_LINE_RE.search(body):
        raise ValueError(
            "本文の中に空行は置けません(空行はつぶやきの区切りに使われます)。"
        )
    for line in body.split("\n"):
        stripped = line.strip()
        if (generate.IMAGE_LINE_RE.match(stripped)
                or generate.QUOTE_LINE_RE.match(stripped)):
            raise ValueError(
                "本文に [img:...] や [rt:...] の行は書けません"
                "(画像と引用はボタンで操作してください)。"
            )

    # 画像は、元のつぶやきに入っていたものだけ残せる
    _, original_images = generate.split_images(original_text)
    for img in keep_images:
        if img not in original_images:
            raise ValueError(f"元のつぶやきにない画像です: {img}")

    lines = [body] if body else []
    lines += [f"[img:{path}]" for path in keep_images] + new_image_lines
    if quote_id is not None:
        if quote_id not in state.get("ids", []):
            raise ValueError("引用元のつぶやきが見つかりません。")
        lines.append(f"[rt:{quote_id}]")
    if not lines:
        raise ValueError("本文も画像もない状態にはできません")

    tweets[index] = "\n".join(lines)
    generate.TWEET_FILE.write_text("\n\n".join(tweets) + "\n", encoding="utf-8")


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
    index = locate_tweet(tweets, index, text)

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
                # スマホPWAの投稿はGitHubに直接コミットされるため、
                # 一覧を作る前に取り込んでおく。オフラインなどで失敗しても
                # 一覧はローカルの内容で出す
                try:
                    self._git("pull", "--no-rebase", timeout=PULL_TIMEOUT_SEC)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass
                self._send_json(list_payload())
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)
            finally:
                reset_idle_timer(self.server)
            return
        self.send_response(404)
        self.end_headers()

    def _git(self, *args, timeout=None):
        subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _publish(self, message):
        """サイトを生成しなおして、コミットとpushまで行う。"""
        run_generate()
        self._git("add", "-A")
        self._git("commit", "-m", message)
        self._git("push")

    def do_POST(self):
        if self.path not in ("/post", "/edit", "/delete"):
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
                image_lines = save_images(data.get("images") or [])
                if not text and not image_lines:
                    raise ValueError("投稿内容が空です")
                # 本文のあとに画像の行を並べる(web版と同じ並び)
                text = "\n".join([text] + image_lines).strip("\n")
                quote_id = data.get("quote_id")
                if quote_id is not None:
                    if not isinstance(quote_id, int):
                        raise ValueError("引用元の指定が正しくありません")
                    text += quote_marker(quote_id)
                append_tweet(text)
                self._publish(
                    "つぶやきを引用して追加(webフォーム)"
                    if quote_id is not None
                    else "つぶやきを追加(webフォーム)"
                )
            elif self.path == "/edit":
                index = data.get("index")
                if not isinstance(index, int):
                    raise ValueError("編集する位置が指定されていません")
                quote_id = data.get("quote_id")
                if quote_id is not None and not isinstance(quote_id, int):
                    raise ValueError("引用元の指定が正しくありません")
                keep_images = data.get("keep_images") or []
                if not isinstance(keep_images, list):
                    raise ValueError("残す画像の指定が正しくありません")
                new_image_lines = save_images(data.get("new_images") or [])
                edit_tweet(
                    index,
                    data.get("original_text", ""),
                    data.get("body", ""),
                    keep_images,
                    new_image_lines,
                    quote_id,
                )
                self._publish("つぶやきを編集(webフォーム)")
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
