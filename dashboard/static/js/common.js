// Shared dashboard helpers: project state, connect dropdown, lang, toast, chips.

(function () {
  'use strict';

  const PLATFORMS = ['twitter', 'reddit', 'linkedin', 'gitmail'];
  const PROJECT_KEY = 'vm.project';
  let LANG = window.VM_DETECT_LANG();
  const T = (k) => window.VM_T(k, LANG);

  // ───── HTTP ─────
  async function fetchJSON(path, opts = {}) {
    const init = { method: opts.method || 'GET' };
    if (opts.body) {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, init);
    let data = null;
    try { data = await res.json(); } catch (_) {}
    return { ok: res.ok, status: res.status, data };
  }

  // ───── Toast ─────
  let toastTimer;
  function toast(msg, kind = '') {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'toast show ' + kind;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 3500);
  }

  // ───── Project state (shared via localStorage) ─────
  function loadProject() {
    try { return JSON.parse(localStorage.getItem(PROJECT_KEY) || '{}'); }
    catch (_) { return {}; }
  }
  function saveProject(p) {
    localStorage.setItem(PROJECT_KEY, JSON.stringify(p));
  }
  function bindProject() {
    const ids = ['p-name', 'p-url', 'p-pitch', 'p-desc', 'p-intent', 'p-provider'];
    const p = loadProject();
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      const key = id.replace(/^p-/, '');
      if (p[key] != null) el.value = p[key];
      el.addEventListener('input', () => {
        const cur = loadProject();
        cur[key] = el.value;
        saveProject(cur);
      });
    });
  }
  function readProject() {
    const p = loadProject();
    return {
      name:  (document.getElementById('p-name') || {}).value || p.name || 'my-project',
      url:   (document.getElementById('p-url') || {}).value || p.url || '',
      pitch: (document.getElementById('p-pitch') || {}).value || p.pitch || '',
      desc:  (document.getElementById('p-desc') || {}).value || p.desc || '',
      intent:(document.getElementById('p-intent') || {}).value || p.intent || '',
      provider: (document.getElementById('p-provider') || {}).value || p.provider || '',
    };
  }

  // ───── Generate (LLM-driven draft for one channel) ─────
  async function generate(channel, onSuccess) {
    const p = readProject();
    if (!p.desc) { toast(T('project.desc.required'), 'error'); return; }
    const btn = document.getElementById('generate');
    if (btn) { btn.disabled = true; btn.textContent = T('gen.running'); }
    const r = await fetchJSON('/api/generate', {
      method: 'POST',
      body: {
        project: p,
        channels: [channel],
        provider: p.provider || null,
        intent: p.intent || '',
      },
    });
    if (btn) { btn.disabled = false; btn.textContent = T('generate'); }
    if (!r.ok || !r.data || !r.data.ok) {
      toast((r.data && r.data.error) || T('gen.failed'), 'error');
      return;
    }
    onSuccess(r.data);
  }

  // ───── Chip helpers ─────
  function renderChips(rootId, list, onRemove) {
    const root = document.getElementById(rootId);
    if (!root) return;
    root.innerHTML = list.map((t, i) =>
      `<span class="chip">${escapeHTML(t)}<span class="x" data-i="${i}">×</span></span>`
    ).join('');
    root.querySelectorAll('.x').forEach(x => {
      x.addEventListener('click', () => onRemove(parseInt(x.dataset.i, 10)));
    });
  }

  function escapeHTML(s) {
    return (s || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[c]);
  }

  // ───── Connect dropdown ─────
  function bindConnect() {
    const connect = document.getElementById('connect');
    const btn = document.getElementById('connect-btn');
    if (!connect || !btn) return;
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      connect.classList.toggle('open');
    });
    document.addEventListener('click', () => connect.classList.remove('open'));
    document.querySelectorAll('.hd-row [data-act]').forEach(b => {
      b.addEventListener('click', (e) => {
        e.stopPropagation();
        const platform = b.dataset.platform;
        if (b.dataset.act === 'oauth') window.location.href = `/oauth/${platform}/start`;
        else openManualModal(platform);
      });
    });
  }

  function openManualModal(platform) {
    const modal = document.getElementById('modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    title.textContent = `${platform} — manual credentials`;
    body.innerHTML = manualForm(platform);
    modal.hidden = false;
    body.querySelector('button.save').addEventListener('click', async () => {
      const inputs = body.querySelectorAll('input[data-key]');
      let saved = 0, failed = 0;
      for (const el of inputs) {
        const v = el.value.trim();
        if (!v) continue;
        const r = await fetchJSON('/api/creds/manual', {
          method: 'POST',
          body: { key: el.dataset.key, value: v, secret: el.hasAttribute('data-secret') },
        });
        if (r.ok && r.data && r.data.ok) { saved++; el.value = ''; } else failed++;
      }
      if (saved && !failed) toast(`${T('send.saved')} ${saved}`, 'ok');
      else if (failed) toast(`${T('send.saved')} ${saved}, ${T('send.failed')} ${failed}`, 'error');
      modal.hidden = true;
      refreshConnectStatus();
    });
  }
  document.getElementById('modal-close')?.addEventListener('click', () => {
    document.getElementById('modal').hidden = true;
  });

  function manualForm(p) {
    const fields = {
      twitter: [
        ['TWITTER_API_KEY', 'API key'],
        ['TWITTER_API_SECRET', 'API secret', true],
        ['TWITTER_ACCESS_TOKEN', 'access token'],
        ['TWITTER_ACCESS_SECRET', 'access secret', true],
        ['TWITTER_HANDLE', 'handle (no @)'],
      ],
      reddit: [
        ['REDDIT_CLIENT_ID', 'client_id'],
        ['REDDIT_CLIENT_SECRET', 'client_secret', true],
        ['REDDIT_USERNAME', 'username'],
        ['REDDIT_PASSWORD', 'password', true],
        ['REDDIT_USER_AGENT', 'user agent (optional)'],
      ],
      linkedin: [
        ['LINKEDIN_ACCESS_TOKEN', 'access token', true],
        ['LINKEDIN_PERSON_URN', 'person urn (urn:li:person:…)'],
      ],
      gitmail: [
        ['GITHUB_TOKEN', 'GitHub token', true],
        ['SMTP_HOST', 'SMTP host (e.g. smtp.gmail.com)'],
        ['SMTP_PORT', 'SMTP port'],
        ['SMTP_USER', 'SMTP user'],
        ['SMTP_PASSWORD', 'SMTP password / app-pw', true],
        ['SMTP_FROM', 'from address'],
        ['SMTP_FROM_NAME', 'from display name (optional)'],
        ['ANTHROPIC_API_KEY', 'Claude API key', true],
        ['OPENAI_API_KEY', 'OpenAI API key', true],
        ['GEMINI_API_KEY', 'Gemini API key', true],
      ],
    };
    return (fields[p] || []).map(([key, label, secret]) => `
      <label>${label}
        <input type="${secret ? 'password' : 'text'}" data-key="${key}" ${secret ? 'data-secret' : ''} autocomplete="off">
      </label>
    `).join('') + '<button class="btn primary save">save</button>';
  }

  async function refreshConnectStatus() {
    const r = await fetchJSON('/api/creds/status');
    if (!r.ok || !r.data) return;
    window.VM_LAST_STATUS = r.data;
    refreshProviderStatus();
    let configured = 0;
    for (const p of PLATFORMS) {
      const row = document.querySelector(`.hd-row[data-platform="${p}"] .hd-st`);
      if (!row) continue;
      let s;
      if (p === 'gitmail') {
        const llmOk = (r.data.claude && r.data.claude.configured) ||
                       (r.data.openai && r.data.openai.configured) ||
                       (r.data.gemini && r.data.gemini.configured);
        s = (r.data.smtp.configured && r.data.github.configured && llmOk);
      } else {
        s = r.data[p] && r.data[p].configured;
      }
      row.textContent = s ? T('connected') : T('not_set');
      row.className = 'hd-st ' + (s ? 'ok' : 'bad');
      if (s) configured++;
    }
    const ct = document.getElementById('connect-count');
    if (ct) ct.textContent = `${configured}/4`;
    const dot = document.getElementById('connect-dot');
    if (dot) dot.className = 'hd-dot ' + (configured === 4 ? 'ok' : configured ? 'partial' : '');
  }

  // ───── Provider inline status ─────
  function refreshProviderStatus() {
    const sel = document.getElementById('p-provider');
    const out = document.getElementById('cli-status');
    if (!sel || !out || !window.VM_LAST_STATUS) return;
    const status = window.VM_LAST_STATUS;
    const v = sel.value;
    let cls = '', text = '';
    if (v === '') {
      text = T('pstatus.auto'); cls = '';
    } else if (v === 'claude-cli') {
      const cli = status.claude_cli || {};
      if (cli.available) {
        text = `${T('pstatus.cli_ok')}${cli.version ? ' (' + cli.version + ')' : ''}`;
        cls = 'ok';
      } else {
        text = T('pstatus.cli_missing'); cls = 'bad';
      }
    } else {
      const ok = (status[v] || {}).configured;
      text = ok ? T('pstatus.key_ok') : T('pstatus.key_missing');
      cls = ok ? 'ok' : 'bad';
    }
    out.textContent = text;
    out.className = 'cli-status ' + cls;
  }

  // ───── Language switcher ─────
  const langPick = document.getElementById('lang-pick');
  if (langPick) {
    langPick.value = LANG;
    langPick.addEventListener('change', () => {
      LANG = langPick.value;
      localStorage.setItem('vm.lang', LANG);
      window.VM_APPLY_I18N(LANG);
      refreshConnectStatus();
      refreshProviderStatus();
    });
  }

  // Expose
  window.VM = {
    fetchJSON, toast, escapeHTML,
    readProject, bindProject,
    generate,
    renderChips,
    refreshConnectStatus,
    T: (k) => T(k),
  };

  // ───── Boot (every page) ─────
  document.addEventListener('DOMContentLoaded', () => {
    window.VM_APPLY_I18N(LANG);
    bindProject();
    bindConnect();
    refreshConnectStatus();
    const sel = document.getElementById('p-provider');
    if (sel) sel.addEventListener('change', refreshProviderStatus);
  });
})();
