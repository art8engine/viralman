(function () {
  'use strict';

  const PLATFORMS = ['twitter', 'reddit', 'linkedin', 'gitmail'];
  let LANG = window.VM_DETECT_LANG();
  const T = (k) => window.VM_T(k, LANG);
  const State = {
    project: { name: '', url: '', pitch: '', desc: '' },
    keywords: [],
    drafts: {},        // {twitter:{body,flags}, reddit:{title,body,flags}}
    targets: {
      twitter: { hashtags: [] },
      reddit:  { subs: [], threads: [] },
      gitmail: { max: 100, minStars: 200, templateOnly: false },
    },
    channels: { twitter: true, reddit: true, gitmail: false },
    creds: null,
    gitmailJobId: null,
    gitmailSince: 0,
    gitmailTimer: null,
  };

  // ───── HTTP ─────
  async function api(path, opts = {}) {
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
    el.textContent = msg;
    el.className = 'toast show ' + kind;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 3500);
  }

  // ───── Steps lock/unlock ─────
  function unlockStep(n) {
    document.querySelectorAll('.step').forEach(s => {
      if (parseInt(s.dataset.step, 10) <= n) s.removeAttribute('data-locked');
    });
  }
  function lockFromStep(n) {
    document.querySelectorAll('.step').forEach(s => {
      if (parseInt(s.dataset.step, 10) >= n) s.setAttribute('data-locked', '');
    });
  }

  // ───── Step 1: Project ─────
  function readProject() {
    State.project = {
      name: document.getElementById('p-name').value.trim() || 'my-project',
      url:  document.getElementById('p-url').value.trim(),
      pitch: document.getElementById('p-pitch').value.trim(),
      desc: document.getElementById('p-desc').value.trim(),
    };
  }
  document.getElementById('p-next').addEventListener('click', () => {
    readProject();
    if (!State.project.desc) {
      toast(T('project.desc.required'), 'error');
      return;
    }
    unlockStep(2);
    document.querySelector('[data-step="2"]').scrollIntoView({ behavior: 'smooth' });
  });

  // ───── Step 2: Generate ─────
  function readChannels() {
    State.channels.twitter = document.getElementById('ch-tw').checked;
    State.channels.reddit  = document.getElementById('ch-rd').checked;
    State.channels.gitmail = document.getElementById('ch-gm').checked;
  }

  document.getElementById('g-run').addEventListener('click', async () => {
    readProject();
    readChannels();
    if (!State.project.desc) return toast(T('gen.finish_step1'), 'error');

    const channels = Object.entries(State.channels).filter(([, v]) => v).map(([k]) => k);
    if (!channels.length) return toast(T('gen.no_channels'), 'error');

    const btn = document.getElementById('g-run');
    btn.disabled = true; btn.textContent = T('gen.running');

    const r = await api('/api/generate', {
      method: 'POST',
      body: {
        project: State.project,
        channels,
        provider: document.getElementById('g-provider').value || null,
        mode: document.getElementById('g-mode').value,
      },
    });

    btn.disabled = false; btn.textContent = T('generate');

    if (!r.ok || !r.data || !r.data.ok) {
      toast((r.data && r.data.error) || T('gen.failed'), 'error');
      return;
    }

    State.drafts = r.data.drafts || {};
    State.keywords = r.data.keywords || [];
    State.targets.twitter.hashtags = (r.data.suggested_hashtags || []).slice(0, 6);
    renderDrafts();
    populateTargetSuggestions(r.data);
    unlockStep(3);
    document.querySelector('[data-step="3"]').scrollIntoView({ behavior: 'smooth' });
  });

  function renderDrafts() {
    const root = document.getElementById('drafts');
    root.innerHTML = '';
    for (const [ch, d] of Object.entries(State.drafts)) {
      if (!d) continue;
      const div = document.createElement('div');
      div.className = 'draft';
      const title = ch === 'twitter' ? 'X' : ch === 'reddit' ? 'Reddit' : 'Gitmail';
      const flags = (d.flags || []);
      const meta = ch === 'twitter'
        ? `${(d.body || '').split('---')[0].length}/280`
        : ch === 'reddit' ? `title ${(d.title || '').length}/300` : '';
      div.innerHTML = `
        <div class="draft-hd"><b>${title}</b><span class="meta">${meta}</span></div>
        ${ch === 'reddit' ? `<input class="rd-title" placeholder="title">` : ''}
        <textarea rows="${ch === 'gitmail' ? 6 : 8}"></textarea>
        <div class="flags ${flags.length ? '' : 'clean'}">
          ${flags.length ? flags.map(f => `[${f.id}] ${f.msg}`).join('\n') : T('send.no_flags')}
        </div>
      `;
      const ta = div.querySelector('textarea');
      ta.value = ch === 'reddit' ? (d.body || '') : (d.body || '');
      ta.addEventListener('input', () => {
        State.drafts[ch].body = ta.value;
        if (ch === 'twitter') {
          div.querySelector('.meta').textContent = `${ta.value.split('---')[0].length}/280`;
        }
      });
      if (ch === 'reddit') {
        const ti = div.querySelector('.rd-title');
        ti.value = d.title || '';
        ti.addEventListener('input', () => {
          State.drafts.reddit.title = ti.value;
          div.querySelector('.meta').textContent = `title ${ti.value.length}/300`;
        });
      }
      root.appendChild(div);
    }
  }

  // ───── Step 3: Targets ─────

  function renderChips(rootId, list, onRemove) {
    const root = document.getElementById(rootId);
    root.innerHTML = list.map((t, i) =>
      `<span class="chip">${t}<span class="x" data-i="${i}">×</span></span>`
    ).join('');
    root.querySelectorAll('.x').forEach(x => {
      x.addEventListener('click', () => onRemove(parseInt(x.dataset.i, 10)));
    });
  }

  function refreshHashtags() {
    renderChips('tw-tags', State.targets.twitter.hashtags, (i) => {
      State.targets.twitter.hashtags.splice(i, 1);
      refreshHashtags();
    });
  }
  function refreshSubs() {
    renderChips('rd-subs', State.targets.reddit.subs, (i) => {
      State.targets.reddit.subs.splice(i, 1);
      refreshSubs();
    });
  }

  document.getElementById('tw-tag-add').addEventListener('click', () => {
    const v = document.getElementById('tw-tag-input').value.trim().replace(/^#/, '');
    if (!v) return;
    State.targets.twitter.hashtags.push('#' + v);
    document.getElementById('tw-tag-input').value = '';
    refreshHashtags();
  });
  document.getElementById('rd-sub-add').addEventListener('click', () => {
    const v = document.getElementById('rd-sub-input').value.trim().replace(/^r\//, '').replace(/^\//, '');
    if (!v) return;
    State.targets.reddit.subs.push(v);
    document.getElementById('rd-sub-input').value = '';
    refreshSubs();
  });

  function populateTargetSuggestions(data) {
    refreshHashtags();
    State.targets.reddit.subs = (data.suggested_subreddits || []).slice(0, 5);
    refreshSubs();
  }

  document.getElementById('rd-scan').addEventListener('click', async () => {
    const subs = State.targets.reddit.subs;
    if (!subs.length) return toast(T('tg.add_sub_first'), 'error');
    const btn = document.getElementById('rd-scan');
    btn.disabled = true; btn.textContent = T('tg.scanning');
    const r = await api('/api/scrape/reddit-threads', {
      method: 'POST',
      body: { subreddits: subs, keywords: State.keywords },
    });
    btn.disabled = false; btn.textContent = T('tg.scan');
    const ul = document.getElementById('rd-threads');
    if (!r.ok || !r.data || !r.data.threads) {
      ul.innerHTML = `<li class="empty">${T('tg.scan_failed')}</li>`;
      return;
    }
    if (!r.data.threads.length) {
      ul.innerHTML = `<li class="empty">${T('tg.no_threads')}</li>`;
      return;
    }
    ul.innerHTML = r.data.threads.map((t, i) => `
      <li>
        <input type="checkbox" data-i="${i}">
        <div>
          <div class="th-title"><a href="${t.url}" target="_blank">${escapeHTML(t.title)}</a></div>
          <div class="th-meta">r/${t.subreddit} · ${t.score}↑ · ${t.comments} comments</div>
        </div>
      </li>
    `).join('');
    State.targets.reddit.threads = r.data.threads;
    ul.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      cb.addEventListener('change', () => {
        const i = parseInt(cb.dataset.i, 10);
        State.targets.reddit.threads[i]._selected = cb.checked;
      });
    });
  });

  document.getElementById('t-next').addEventListener('click', () => {
    State.targets.gitmail.max = parseInt(document.getElementById('gm-max').value, 10) || 100;
    State.targets.gitmail.minStars = parseInt(document.getElementById('gm-min-stars').value, 10) || 200;
    State.targets.gitmail.templateOnly = document.getElementById('gm-template').checked;
    unlockStep(4);
    document.querySelector('[data-step="4"]').scrollIntoView({ behavior: 'smooth' });
  });

  // ───── Step 4: Send ─────

  function setProgStep(key, state) {
    document.querySelectorAll('.prog-step').forEach(el => {
      if (el.dataset.key === key) el.className = `prog-step ${state}`;
    });
  }

  function logLine(text, cls) {
    const log = document.getElementById('log');
    if (log.textContent === 'no run yet') log.textContent = '';
    const span = document.createElement('span');
    if (cls) span.className = cls;
    span.textContent = text + '\n';
    log.appendChild(span);
    log.scrollTop = log.scrollHeight;
  }

  document.getElementById('s-confirm').addEventListener('change', (e) => {
    document.getElementById('s-go').disabled = !e.target.checked;
  });

  document.getElementById('s-cancel').addEventListener('click', async () => {
    if (State.gitmailJobId) {
      await api(`/api/gitmail/cancel/${State.gitmailJobId}`, { method: 'POST' });
    }
    if (State.gitmailTimer) {
      clearInterval(State.gitmailTimer);
      State.gitmailTimer = null;
    }
    document.getElementById('s-cancel').disabled = true;
    toast(T('send.cancelled'), 'warn');
  });

  document.getElementById('s-go').addEventListener('click', async () => {
    const dry = document.getElementById('s-dryrun').checked;
    if (!dry && !confirm(T('send.real_check'))) return;

    document.getElementById('s-go').disabled = true;
    document.getElementById('s-cancel').disabled = false;

    if (State.channels.twitter && State.drafts.twitter) {
      setProgStep('twitter', 'active');
      logLine('▸ X');
      if (dry) {
        const r = await api('/api/preview/twitter', { method: 'POST', body: { body: State.drafts.twitter.body } });
        if (r.ok && r.data && r.data.ok) {
          logLine(`  preview: ${r.data.compose_url}`);
          setProgStep('twitter', 'done');
        } else { setProgStep('twitter', 'error'); logLine('  preview failed', 'ev-error'); }
      } else {
        const r = await api('/api/post/twitter', { method: 'POST', body: { body: State.drafts.twitter.body } });
        if (r.ok && r.data && r.data.ok) {
          logLine(`  posted: ${r.data.url}`, 'ev-ok');
          setProgStep('twitter', 'done');
        } else {
          logLine(`  failed: ${(r.data && (r.data.stderr || r.data.error)) || 'unknown'}`, 'ev-error');
          setProgStep('twitter', 'error');
        }
      }
    }

    if (State.channels.reddit && State.drafts.reddit && State.targets.reddit.subs.length) {
      setProgStep('reddit', 'active');
      logLine('▸ Reddit');
      const sub = State.targets.reddit.subs[0];
      if (dry) {
        const r = await api('/api/preview/reddit', {
          method: 'POST',
          body: {
            subreddit: sub,
            title: State.drafts.reddit.title || State.project.pitch || State.project.name,
            body: State.drafts.reddit.body,
          },
        });
        if (r.ok && r.data && r.data.ok) {
          logLine(`  preview: ${r.data.compose_url}`);
          setProgStep('reddit', 'done');
        } else { setProgStep('reddit', 'error'); logLine('  preview failed', 'ev-error'); }
      } else {
        const r = await api('/api/post/reddit', {
          method: 'POST',
          body: {
            subreddit: sub,
            title: State.drafts.reddit.title || State.project.pitch || State.project.name,
            body: State.drafts.reddit.body,
          },
        });
        if (r.ok && r.data && r.data.ok) {
          logLine(`  posted: ${r.data.url}`, 'ev-ok');
          setProgStep('reddit', 'done');
        } else {
          logLine(`  failed: ${(r.data && (r.data.stderr || r.data.error)) || 'unknown'}`, 'ev-error');
          setProgStep('reddit', 'error');
        }
      }
    }

    if (State.channels.gitmail) {
      setProgStep('gitmail', 'active');
      logLine('▸ Gitmail');
      const r = await api('/api/gitmail/start', {
        method: 'POST',
        body: {
          project_name: State.project.name,
          project_url: State.project.url,
          description: State.project.desc,
          pitch: State.project.pitch,
          max_users: State.targets.gitmail.max,
          min_stars: State.targets.gitmail.minStars,
          template_only: State.targets.gitmail.templateOnly,
          provider: document.getElementById('g-provider').value || null,
          dry_run: dry,
        },
      });
      if (r.ok && r.data && r.data.ok) {
        State.gitmailJobId = r.data.job_id;
        State.gitmailSince = 0;
        State.gitmailTimer = setInterval(pollGitmail, 1500);
        pollGitmail();
      } else {
        logLine(`  failed to start: ${(r.data && r.data.error) || 'unknown'}`, 'ev-error');
        setProgStep('gitmail', 'error');
      }
    } else {
      // no gitmail → enable s-go again so user can retry
      setTimeout(() => {
        document.getElementById('s-go').disabled = false;
        document.getElementById('s-cancel').disabled = true;
      }, 500);
    }
  });

  async function pollGitmail() {
    if (!State.gitmailJobId) return;
    const r = await api(`/api/gitmail/status/${State.gitmailJobId}?since=${State.gitmailSince}`);
    if (!r.ok || !r.data) return;
    State.gitmailSince = r.data.next_since;
    for (const ev of r.data.events) {
      const t = ev.event;
      if (t === 'done') {
        const send = ev.send || {};
        logLine(`  done — sent ${send.sent || 0}, failed ${send.failed || 0}`,
                send.failed === 0 ? 'ev-ok' : 'ev-warn');
        setProgStep('gitmail', send.failed ? 'error' : 'done');
      } else if (t === 'fatal') {
        logLine(`  fatal: ${ev.reason}`, 'ev-error');
        setProgStep('gitmail', 'error');
      } else if (t === 'send_ok') {
        logLine(`  ✓ ${ev.to} (${ev.sent}/${ev.target})`, 'ev-ok');
      } else if (t === 'send_fail') {
        logLine(`  ✗ ${ev.to}: ${ev.error}`, 'ev-error');
      } else if (t === 'analyse_done') {
        logLine(`  analyse: ${ev.summary || '(none)'}`);
      } else if (t === 'search_done') {
        logLine(`  search: ${ev.count} repo(s)`);
      } else if (t === 'recipients_done') {
        logLine(`  recipients: ${ev.count}`);
      }
    }
    if (['done', 'error', 'cancelled'].includes(r.data.status)) {
      clearInterval(State.gitmailTimer);
      State.gitmailTimer = null;
      State.gitmailJobId = null;
      document.getElementById('s-go').disabled = false;
      document.getElementById('s-cancel').disabled = true;
    }
  }

  // ───── Connect dropdown ─────

  const connect = document.getElementById('connect');
  document.getElementById('connect-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    connect.classList.toggle('open');
  });
  document.addEventListener('click', () => connect.classList.remove('open'));

  document.querySelectorAll('.hd-row [data-act]').forEach(b => {
    b.addEventListener('click', (e) => {
      e.stopPropagation();
      const platform = b.dataset.platform;
      if (b.dataset.act === 'oauth') {
        window.location.href = `/oauth/${platform}/start`;
      } else {
        openManualModal(platform);
      }
    });
  });

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
        const r = await api('/api/creds/manual', {
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
  document.getElementById('modal-close').addEventListener('click', () => {
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
        ['SMTP_PORT', 'SMTP port', false],
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
    const r = await api('/api/creds/status');
    if (!r.ok || !r.data) return;
    State.creds = r.data;
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
    document.getElementById('connect-count').textContent = `${configured}/4`;
    const dot = document.getElementById('connect-dot');
    dot.className = 'hd-dot ' + (configured === 4 ? 'ok' : configured ? 'partial' : '');
  }

  function escapeHTML(s) {
    return (s || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[c]);
  }

  // ───── Language switcher ─────
  const langPick = document.getElementById('lang-pick');
  langPick.value = LANG;
  langPick.addEventListener('change', () => {
    LANG = langPick.value;
    localStorage.setItem('vm.lang', LANG);
    window.VM_APPLY_I18N(LANG);
    refreshConnectStatus();
  });

  // ───── Init ─────
  window.VM_APPLY_I18N(LANG);
  unlockStep(1);
  refreshConnectStatus();
})();
