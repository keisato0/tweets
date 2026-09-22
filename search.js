// 検索ページ(search.html)の処理。generate.py が書き出す search.json(全ツイート)を対象に、
// 上部の検索ボックスで Enter を押したときに絞り込んで表示する(入力中は何もしない)。
// スペース区切りで複数語を入れるとすべてを含むツイートに絞る(AND検索)。
// 全角/半角・大文字/小文字は区別しない。検索語は URL の ?q= に反映される。
(function () {
  const ROOT = new URL('.', document.currentScript.src).href;
  const ROOT_TOKEN = '__ROOT__';

  const form = document.querySelector('.search-bar .search');
  const input = form && form.querySelector('input[name="q"]');
  const statusEl = document.querySelector('.search-status');
  const listEl = document.querySelector('.search-list');
  if (!input || !statusEl || !listEl) return;

  let index = null;      // [{ t, h, n }]  n は正規化済みの本文
  let loading = null;

  function normalize(s) {
    return s.normalize('NFKC').toLowerCase();
  }

  function loadIndex() {
    if (!loading) {
      loading = fetch(ROOT + 'search.json', { cache: 'no-cache' })
        .then(res => {
          if (!res.ok) throw new Error(res.status);
          return res.json();
        })
        .then(items => {
          index = items.map(it => ({ t: it.t, h: it.h.split(ROOT_TOKEN).join(ROOT), n: normalize(it.t) }));
          return index;
        })
        .catch(err => {
          loading = null;  // 次の検索で再試行する
          throw err;
        });
    }
    return loading;
  }

  function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  // 本文中の一致箇所を <mark> で囲む(リンク等のタグは壊さないよう文字部分だけを対象にする)
  function highlight(root, words) {
    const re = new RegExp(words.map(escapeRegExp).join('|'), 'gi');
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const text = node.nodeValue;
      re.lastIndex = 0;
      if (!re.test(text)) continue;
      re.lastIndex = 0;
      const frag = document.createDocumentFragment();
      let last = 0, m;
      while ((m = re.exec(text))) {
        if (m[0] === '') { re.lastIndex++; continue; }
        frag.append(text.slice(last, m.index));
        const mark = document.createElement('mark');
        mark.textContent = m[0];
        frag.append(mark);
        last = m.index + m[0].length;
      }
      frag.append(text.slice(last));
      node.replaceWith(frag);
    }
  }

  function setStatus(text) {
    statusEl.textContent = text;
    statusEl.hidden = !text;
  }

  function updateUrl(q) {
    const url = new URL(location.href);
    if (q) url.searchParams.set('q', q); else url.searchParams.delete('q');
    history.replaceState(history.state, '', url);
  }

  let seq = 0;
  async function search(raw) {
    const q = raw.trim();
    updateUrl(q);
    const my = ++seq;
    const words = normalize(q).split(/\s+/).filter(Boolean);
    if (!words.length) {
      setStatus('');
      listEl.innerHTML = '';
      return;
    }

    if (!index) {
      setStatus('検索中...');
      listEl.innerHTML = '';
      try {
        await loadIndex();
      } catch (e) {
        if (my === seq) setStatus('検索データを読み込めませんでした。');
        return;
      }
    }
    if (my !== seq) return;  // 読み込み中に別の検索が始まった

    const hits = index.filter(it => words.every(w => it.n.includes(w)));
    setStatus(hits.length
      ? `「${q}」の検索結果: ${hits.length.toLocaleString()}件`
      : `「${q}」に一致するツイートはありません。`);
    listEl.innerHTML = hits.map(it => it.h).join('');
    const rawWords = q.split(/\s+/).filter(Boolean);
    listEl.querySelectorAll('.tweet-body').forEach(el => highlight(el, rawWords));
  }

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && input.value) {
      input.value = '';
      search('');
    }
  });
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    search(input.value);
    input.blur();  // スマホではキーボードを閉じる
  });

  // 戻るボタン: サイト内から来たときはブラウザの「戻る」で元のページ(スクロール位置も)に戻す
  const back = document.querySelector('.search-back');
  if (back) {
    back.addEventListener('click', (e) => {
      let fromSite = false;
      try { fromSite = new URL(document.referrer).origin === location.origin; } catch (err) { /* 直接開いた */ }
      if (fromSite && history.length > 1) {
        e.preventDefault();
        history.back();
      }
    });
  }

  loadIndex().catch(() => {});  // 入力を待たずに読み込んでおく

  // ?q= 付きで開かれたらその語で検索する
  const initial = new URL(location.href).searchParams.get('q');
  if (initial) {
    input.value = initial;
    search(initial);
  } else {
    input.focus();
  }
})();
