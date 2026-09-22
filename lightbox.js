// タイムラインの添付画像をクリックしたときの拡大表示。
// 右上の×・背景のクリック・Escキー・ブラウザの「戻る」で閉じる。
// 複数枚の投稿は左右の矢印・キーボードの←→・スワイプで切り替えられる。
(function () {
  const ICON_CLOSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10.59 12L4.54 5.96l1.42-1.42L12 10.59l6.04-6.05 1.42 1.42L13.41 12l6.05 6.04-1.42 1.42L12 13.41l-6.04 6.05-1.42-1.42L10.59 12z"/></svg>';
  const ICON_PREV = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7.41 13l5.29 5.29-1.41 1.42L3.59 12l7.7-7.71 1.41 1.42L7.41 11H20v2H7.41z"/></svg>';
  const ICON_NEXT = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16.59 11L11.3 5.71l1.41-1.42L20.41 12l-7.7 7.71-1.41-1.42L16.59 13H4v-2h12.59z"/></svg>';

  const box = document.createElement('div');
  box.className = 'lightbox';
  box.hidden = true;
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-modal', 'true');
  box.innerHTML =
    '<img class="lightbox-img" alt="">' +
    '<button class="lightbox-btn lightbox-close" aria-label="閉じる">' + ICON_CLOSE + '</button>' +
    '<button class="lightbox-btn lightbox-prev" aria-label="前の画像">' + ICON_PREV + '</button>' +
    '<button class="lightbox-btn lightbox-next" aria-label="次の画像">' + ICON_NEXT + '</button>' +
    '<div class="lightbox-counter"></div>';
  document.body.appendChild(box);

  const img = box.querySelector('.lightbox-img');
  const prevBtn = box.querySelector('.lightbox-prev');
  const nextBtn = box.querySelector('.lightbox-next');
  const counter = box.querySelector('.lightbox-counter');

  let urls = [];
  let index = 0;
  let lastFocus = null;

  function show(i) {
    index = i;
    img.src = urls[index];
    const multi = urls.length > 1;
    prevBtn.hidden = !multi || index === 0;
    nextBtn.hidden = !multi || index === urls.length - 1;
    counter.textContent = multi ? (index + 1) + ' / ' + urls.length : '';
  }

  function open(list, i) {
    urls = list;
    lastFocus = document.activeElement;
    show(i);
    box.hidden = false;
    document.body.classList.add('lightbox-open');
    box.querySelector('.lightbox-close').focus();
    // スマホの「戻る」で閉じられるように履歴を1つ積む
    history.pushState({ lightbox: true }, '');
  }

  function hide() {
    box.hidden = true;
    img.removeAttribute('src');
    document.body.classList.remove('lightbox-open');
    if (lastFocus) lastFocus.focus();
  }

  function close() {
    if (box.hidden) return;
    if (history.state && history.state.lightbox) {
      history.back();  // popstate で hide() される
    } else {
      hide();
    }
  }

  window.addEventListener('popstate', () => { if (!box.hidden) hide(); });

  document.addEventListener('click', (e) => {
    const a = e.target.closest('.tweet-images a');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey) return;  // 修飾キー付きは新しいタブで開く
    e.preventDefault();
    const links = Array.from(a.closest('.tweet-images').querySelectorAll('a'));
    open(links.map(l => l.href), links.indexOf(a));
  });

  box.querySelector('.lightbox-close').addEventListener('click', close);
  prevBtn.addEventListener('click', (e) => { e.stopPropagation(); show(index - 1); });
  nextBtn.addEventListener('click', (e) => { e.stopPropagation(); show(index + 1); });
  box.addEventListener('click', (e) => { if (e.target === box) close(); });

  document.addEventListener('keydown', (e) => {
    if (box.hidden) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft' && index > 0) show(index - 1);
    else if (e.key === 'ArrowRight' && index < urls.length - 1) show(index + 1);
  });

  // 左右スワイプで画像を切り替える(ピンチ操作中は無視)
  let startX = null, startY = null;
  box.addEventListener('touchstart', (e) => {
    if (e.touches.length !== 1) { startX = null; return; }
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  }, { passive: true });
  box.addEventListener('touchend', (e) => {
    if (startX === null) return;
    const dx = e.changedTouches[0].clientX - startX;
    const dy = e.changedTouches[0].clientY - startY;
    startX = null;
    if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy)) return;
    if (dx < 0 && index < urls.length - 1) show(index + 1);
    else if (dx > 0 && index > 0) show(index - 1);
  });
})();
