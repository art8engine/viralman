// Shared dashboard helpers.

(function () {
  'use strict';

  window.VM = {
    fetchJSON,
    toast,
    debounce,
    refreshStatus,
    bindCredsForm,
    bindOAuthButtons,
    setRedirectHint,
  };

  async function fetchJSON(url, opts = {}) {
    const res = await fetch(url, {
      method: opts.method || 'GET',
      headers: opts.headers || (opts.body ? { 'Content-Type': 'application/json' } : {}),
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch (_e) { /* not JSON */ }
    return { ok: res.ok, status: res.status, data };
  }

  let toastTimer = null;
  function toast(msg, kind = '') {
    const el = document.getElementById('vm-toast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'vm-toast show ' + kind;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.classList.remove('show'); }, 3500);
  }

  function debounce(fn, ms) {
    let t = null;
    return function () {
      const args = arguments;
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  async function refreshStatus(platform) {
    const { ok, data } = await fetchJSON('/api/creds/status');
    const dot = document.querySelector('#vm-status .vm-status-dot');
    const txt = document.querySelector('#vm-status .vm-status-text');
    if (!ok || !data) {
      dot && (dot.className = 'vm-status-dot bad');
      txt && (txt.textContent = 'creds error');
      return null;
    }
    if (platform && data[platform]) {
      const s = data[platform];
      dot.className = 'vm-status-dot ' + (s.configured ? 'ok' : (s.present.length ? 'partial' : 'bad'));
      txt.textContent = s.configured ? `${platform}: connected` : `${platform}: missing ${s.missing.length}`;
    }
    return data;
  }

  function bindCredsForm(rootSelector, onSaved) {
    const root = typeof rootSelector === 'string'
      ? document.querySelector(rootSelector)
      : rootSelector;
    if (!root) return;
    const btn = root.querySelector('button');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'saving…';
      const inputs = root.querySelectorAll('input[data-key]');
      let saved = 0, failed = 0;
      for (const el of inputs) {
        const value = el.value.trim();
        if (!value) continue;
        const key = el.getAttribute('data-key');
        const isSecret = el.hasAttribute('data-secret');
        const r = await fetchJSON('/api/creds/manual', {
          method: 'POST',
          body: { key, value, secret: isSecret },
        });
        if (r.ok && r.data && r.data.ok) { saved++; el.value = ''; } else { failed++; }
      }
      btn.disabled = false;
      btn.textContent = 'save';
      if (saved && !failed) toast(`saved ${saved}`, 'ok');
      else if (failed) toast(`saved ${saved}, failed ${failed}`, 'error');
      if (onSaved) onSaved();
    });
  }

  function bindOAuthButtons(platform) {
    const startBtn = document.getElementById(`${platformPrefix(platform)}-oauth-start`);
    if (startBtn) {
      startBtn.addEventListener('click', async () => {
        const cfg = await fetchJSON('/api/oauth/config');
        if (!cfg.ok) return toast('oauth config unavailable', 'error');
        const c = cfg.data[platform] || {};
        if (!c.client_id_set || !c.client_secret_set) {
          toast(`save ${oauthClientKey(platform)} first`, 'error');
          return;
        }
        window.location.href = `/oauth/${platform}/start`;
      });
    }
    const manualBtn = document.getElementById(`${platformPrefix(platform)}-manual`);
    const manualPane = document.getElementById(`${platformPrefix(platform)}-manual-pane`);
    if (manualBtn && manualPane) {
      manualBtn.addEventListener('click', () => { manualPane.open = !manualPane.open; });
    }
  }

  function platformPrefix(p) {
    return ({ twitter: 'tw', reddit: 'rd', linkedin: 'li', gitmail: 'gm' })[p] || p;
  }

  function oauthClientKey(p) {
    if (p === 'twitter') return 'TWITTER_OAUTH2_CLIENT_ID + SECRET';
    if (p === 'reddit') return 'REDDIT_OAUTH_CLIENT_ID + SECRET';
    if (p === 'linkedin') return 'LINKEDIN_CLIENT_ID + SECRET';
    return p.toUpperCase() + '_CLIENT_ID + SECRET';
  }

  async function setRedirectHint() {
    const cfg = await fetchJSON('/api/oauth/config');
    if (!cfg.ok) return;
    for (const [p, conf] of Object.entries(cfg.data)) {
      const el = document.getElementById(`${platformPrefix(p)}-redir`);
      if (el) el.textContent = conf.redirect_uri;
    }
  }

})();
