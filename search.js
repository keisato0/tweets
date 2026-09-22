// サイト内検索。generate.py が書き出す search.json(全ツイート)を対象に、
// ヘッダーの検索ボックスの入力に合わせてその場で絞り込んで表示する。
// スペース区切りで複数語を入れるとすべてを含むツイートに絞る(AND検索)。
// 全角/半角・大文字/小文字は区別しない。検索語は URL の ?q= に反映される。
(function () {
  const ROOT = new URL('.', document.currentScript.src).href;
  const ROOT_TOKEN = '__ROOT__';

  const form = document.querySelector('.site-header .search');
  const input = form && form.querySelector('input[name="q"]');
  const timeline = document.querySelector('.timeline');
  if (!input || !timeline) return;

  // 検索中は隠す、通常のタイムライン部分
  const normalParts = [timeline, ...document.querySelectorAll('.archive-list, .pager')];

  const results = document.createElement('section');
  results.className = 'search-results';
  results.hidden = true;
  results.innerHTML = '<div class="search-status" role="status"></div><div class="search-list"></div>';
  timeline.after(results);
  const statusEl = results.querySelector('.search-status');
  const listEl = results.querySelector('.search-list');

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
          loading = null;  // 次の入力で再試行する
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

  function showNormal() {
    results.hidden = true;
    listEl.innerHTML = '';
    normalParts.forEach(el => { el.hidden = false; });
  }

  function showResults() {
    normalParts.forEach(el => { el.hidden = true; });
    results.hidden = false;
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
    const words = normalize(q).split(/\s+/).filter(Boolean);
    if (!words.length) { showNormal(); return; }

    const my = ++seq;
    showResults();
    if (!index) {
      statusEl.textContent = '検索中...';
      listEl.innerHTML = '';
      try {
        await loadIndex();
      } catch (e) {
        if (my === seq) statusEl.textContent = '検索データを読み込めませんでした。';
        return;
      }
    }
    if (my !== seq) return;  // 読み込み中に入力が変わった

    const hits = index.filter(it => words.every(w => it.n.includes(w)));
    statusEl.textContent = hits.length
      ? `「${q}」の検索結果: ${hits.length.toLocaleString()}件`
      : `「${q}」に一致するツイートはありません。`;
    listEl.innerHTML = hits.map(it => it.h).join('');
    const rawWords = q.split(/\s+/).filter(Boolean);
    listEl.querySelectorAll('.tweet-body').forEach(el => highlight(el, rawWords));
  }

  let timer = null;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => search(input.value), 200);
  });
  input.addEventListener('focus', () => { loadIndex().catch(() => {}); }, { once: true });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && input.value) {
      input.value = '';
      search('');
    }
  });
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    clearTimeout(timer);
    search(input.value);
    input.blur();  // スマホではキーボードを閉じる
  });

  // ?q= 付きで開かれたらその語で検索する
  const initial = new URL(location.href).searchParams.get('q');
  if (initial) {
    input.value = initial;
    search(initial);
  }
})();
