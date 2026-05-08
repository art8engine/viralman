(function () {
  'use strict';

  const State = { candidates: [], query: '' };

  document.addEventListener('DOMContentLoaded', () => {
    const $query = document.getElementById('txr-query');
    const $keywords = document.getElementById('txr-keywords');
    const $lang = document.getElementById('txr-lang');
    const $max = document.getElementById('txr-max');
    const $min = document.getElementById('txr-min');
    const $rt = document.getElementById('txr-rt');
    const $scrape = document.getElementById('txr-scrape');
    const $reload = document.getElementById('txr-reload');
    const $meta = document.getElementById('txr-meta');
    const $summary = document.getElementById('txr-summary');
    const $cards = document.getElementById('txr-cards');
    const $empty = document.getElementById('txr-empty');

    loadCache();

    $scrape.addEventListener('click', async () => {
      const payload = {
        query: $query.value.trim(),
        keywords: $keywords.value.trim(),
        lang: $lang.value,
        max_candidates: parseInt($max.value, 10) || 20,
        min_engagement: parseInt($min.value, 10) || 0,
        include_retweets: $rt.checked,
      };
      if (!payload.query && !payload.keywords) {
        VM.toast(VM.T('txr.need_query') || 'enter a query or keywords', 'error');
        return;
      }
      $scrape.disabled = true;
      $meta.textContent = (VM.T('txr.scraping') || 'scraping') + '…';
      const r = await VM.fetchJSON('/api/twitter-reply/scrape', { method: 'POST', body: payload });
      $scrape.disabled = false;
      if (!r.ok || !r.data || !r.data.ok) {
        const msg = (r.data && r.data.error) || 'scrape failed';
        $meta.textContent = msg;
        VM.toast(msg, 'error');
        return;
      }
      State.candidates = r.data.candidates || [];
      State.query = r.data.query || '';
      $meta.textContent = (VM.T('txr.scraped') || 'scraped') + ` — ${State.candidates.length}`;
      renderCards();
    });

    $reload.addEventListener('click', loadCache);

    async function loadCache() {
      const r = await VM.fetchJSON('/api/twitter-reply/cache');
      if (r.ok && r.data && r.data.ok) {
        State.candidates = r.data.candidates || [];
        State.query = r.data.query || '';
        $meta.textContent = State.candidates.length
          ? (VM.T('txr.from_cache') || 'from cache') + ` — ${State.candidates.length}`
          : '—';
        renderCards();
      }
    }

    function renderCards() {
      $summary.textContent = `${State.candidates.length} candidates`;
      if (!State.candidates.length) {
        $empty.style.display = '';
        $cards.innerHTML = '';
        return;
      }
      $empty.style.display = 'none';
      $cards.innerHTML = State.candidates.map(card).join('');
      $cards.querySelectorAll('[data-act="reply"]').forEach(btn => {
        btn.addEventListener('click', () => onReply(btn.dataset.tid));
      });
      $cards.querySelectorAll('[data-act="open"]').forEach(btn => {
        btn.addEventListener('click', () => window.open(btn.dataset.url, '_blank', 'noopener'));
      });
    }

    function card(c) {
      const a = c.author || {};
      const e = c.engagement || {};
      const avatar = a.profile_image_url
        ? `<img class="txr-avatar" src="${VM.escapeHTML(a.profile_image_url)}" alt="">`
        : `<span class="txr-avatar txr-avatar-fallback">${VM.escapeHTML((a.username || '?').slice(0, 1).toUpperCase())}</span>`;
      const created = c.created_at ? new Date(c.created_at).toLocaleString() : '';
      return `
        <article class="txr-card" data-tid="${VM.escapeHTML(c.id)}">
          <header class="txr-card-hd">
            ${avatar}
            <div class="txr-who">
              <strong>${VM.escapeHTML(a.name || a.username || 'unknown')}</strong>
              <span class="txr-handle">@${VM.escapeHTML(a.username || 'unknown')}</span>
              <span class="txr-time">${VM.escapeHTML(created)}</span>
            </div>
          </header>
          <p class="txr-text">${VM.escapeHTML(c.text || '')}</p>
          <footer class="txr-card-ft">
            <span class="txr-eng">♡ ${e.likes || 0} · ↻ ${e.retweets || 0} · 💬 ${e.replies || 0} · ❝ ${e.quotes || 0}</span>
            <button class="btn small ghost" data-act="open" data-url="${VM.escapeHTML(c.url)}">open on X</button>
            <button class="btn small primary" data-act="reply" data-tid="${VM.escapeHTML(c.id)}">reply…</button>
          </footer>
        </article>`;
    }

    async function onReply(tweetId) {
      const body = prompt(VM.T('txr.reply_prompt') || 'reply text (≤280 chars):');
      if (!body) return;
      const trimmed = body.trim();
      if (!trimmed) return;
      if (trimmed.length > 280) {
        VM.toast(`${trimmed.length} chars > 280`, 'error');
        return;
      }
      if (!confirm(VM.T('txr.reply_confirm') || `Send reply to tweet ${tweetId}?`)) return;
      const r = await VM.fetchJSON('/api/twitter-reply/reply', {
        method: 'POST',
        body: { tweet_id: tweetId, body: trimmed },
      });
      if (!r.ok || !r.data || !r.data.ok) {
        VM.toast((r.data && r.data.error) || 'reply failed', 'error');
        return;
      }
      VM.toast((VM.T('txr.reply_done') || 'reply posted') + ` — ${r.data.url || ''}`, 'ok');
    }
  });
})();
