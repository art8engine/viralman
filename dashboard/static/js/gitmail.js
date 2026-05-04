(function () {
  'use strict';
  const { fetchJSON, toast, refreshStatus, bindCredsForm } = window.VM;

  let jobId = null;
  let pollTimer = null;
  let nextSince = 0;
  let composedRecipients = [];

  const $log = document.getElementById('gm-log');
  const $start = document.getElementById('gm-start');
  const $cancel = document.getElementById('gm-cancel');
  const $pick = document.getElementById('gm-preview-pick');
  const $copy = document.getElementById('gm-copy');
  const $previewMeta = document.getElementById('gm-preview-meta');
  const $previewSubject = document.getElementById('gm-preview-subject');
  const $previewBody = document.getElementById('gm-preview-body');
  const $costHint = document.getElementById('gm-cost-hint');
  const $credStatus = document.getElementById('gm-cred-status');

  const STEPS = ['analyse', 'search', 'recipients', 'compose', 'send'];

  function setStep(name, state) {
    document.querySelectorAll('.vm-step').forEach(el => {
      if (el.dataset.step === name) el.className = `vm-step ${state}`;
    });
  }
  function resetSteps() {
    document.querySelectorAll('.vm-step').forEach(el => { el.className = 'vm-step'; });
  }

  function buildArgs() {
    const max = parseInt(document.getElementById('gm-max').value, 10);
    return {
      project_name: document.getElementById('gm-name').value.trim() || 'my-project',
      project_url:  document.getElementById('gm-url').value.trim(),
      description:  document.getElementById('gm-desc').value.trim(),
      pitch:        document.getElementById('gm-pitch').value.trim(),
      max_users:    isFinite(max) ? max : 100,
      min_stars:    parseInt(document.getElementById('gm-min-stars').value, 10) || 200,
      repo_limit:   parseInt(document.getElementById('gm-repo-limit').value, 10) || 15,
      provider:     document.getElementById('gm-provider').value || null,
      dry_run:      document.getElementById('gm-dryrun').checked,
      template_only: document.getElementById('gm-template').checked,
    };
  }

  function refreshCostHint() {
    const args = buildArgs();
    const calls = args.template_only ? 2 : 1 + args.max_users;
    $costHint.textContent = `~${calls} LLM call${calls === 1 ? '' : 's'}, ~${args.max_users} emails`;
  }

  async function start() {
    const args = buildArgs();
    if (!args.description) return toast('description required', 'error');
    if (args.max_users > 10000) return toast('max 10000', 'error');

    resetSteps();
    setStep('analyse', 'active');
    $log.textContent = 'starting…\n';
    composedRecipients = [];
    $pick.innerHTML = '<option>collecting…</option>';
    $pick.disabled = true;
    $copy.disabled = true;

    const r = await fetchJSON('/api/gitmail/start', { method: 'POST', body: args });
    if (!r.ok || !r.data || !r.data.ok) {
      toast((r.data && r.data.error) || 'failed to start', 'error');
      return;
    }
    jobId = r.data.job_id;
    nextSince = 0;
    $start.disabled = true;
    $cancel.disabled = false;
    pollTimer = setInterval(poll, 1500);
    poll();
  }

  async function poll() {
    if (!jobId) return;
    const r = await fetchJSON(`/api/gitmail/status/${jobId}?since=${nextSince}`);
    if (!r.ok || !r.data) return;
    nextSince = r.data.next_since;
    for (const ev of r.data.events) {
      handleEvent(ev);
    }
    if (['done', 'error', 'cancelled'].includes(r.data.status)) {
      clearInterval(pollTimer);
      pollTimer = null;
      $start.disabled = false;
      $cancel.disabled = true;
      if (r.data.status === 'done') toast('gitmail finished ✓', 'ok');
      if (r.data.status === 'error') toast('gitmail errored', 'error');
    }
  }

  function logLine(text, cls) {
    const line = document.createElement('span');
    if (cls) line.className = cls;
    line.textContent = text + '\n';
    if ($log.textContent === 'no job started yet' || $log.textContent === 'starting…\n') {
      $log.textContent = '';
    }
    $log.appendChild(line);
    $log.scrollTop = $log.scrollHeight;
  }

  function handleEvent(ev) {
    const t = ev.event;
    switch (t) {
      case 'analyse_start':       setStep('analyse', 'active'); logLine('▸ analyse'); break;
      case 'analyse_done':
        setStep('analyse', 'done');
        logLine(`  summary: ${ev.summary || '(none)'}`, 'ev-ok');
        logLine(`  topics: ${(ev.topics || []).join(', ')}`);
        logLine(`  keywords: ${(ev.keywords || []).join(', ')}`);
        break;
      case 'search_start':
        setStep('search', 'active');
        logLine(`▸ search (min_stars ${ev.min_stars})`);
        break;
      case 'search_done':
        setStep('search', ev.count ? 'done' : 'error');
        logLine(`  found ${ev.count} repo(s)`, ev.count ? 'ev-ok' : 'ev-error');
        for (const r of (ev.repos || []).slice(0, 8)) {
          logLine(`    · ${r.full_name} (${r.stars}⭐)`);
        }
        break;
      case 'recipients_start':
        setStep('recipients', 'active');
        logLine(`▸ recipients (target ${ev.target}, walking ${ev.repo_count} repos)`);
        break;
      case 'recipients_progress':
        logLine(`  ${ev.count}/${ev.target}`);
        break;
      case 'recipients_done':
        setStep('recipients', ev.count ? 'done' : 'error');
        logLine(`  collected ${ev.count}`, ev.count ? 'ev-ok' : 'ev-error');
        break;
      case 'compose_start':
        setStep('compose', 'active');
        logLine(`▸ compose (${ev.template_only ? 'template-only' : 'per-recipient'})`);
        break;
      case 'compose_progress':
        logLine(`  ${ev.count}/${ev.target}`);
        break;
      case 'compose_done':
        setStep('compose', ev.count ? 'done' : 'error');
        break;
      case 'send_start':
        setStep('send', 'active');
        logLine(`▸ send (${ev.count})`);
        break;
      case 'send_dry_run_start':
        setStep('send', 'active');
        logLine(`▸ dry-run preview (${ev.count})`, 'ev-warn');
        break;
      case 'send_preview':
        composedRecipients.push({ to: ev.to, subject: ev.subject });
        renderPick();
        break;
      case 'send_dry_run_done':
        setStep('send', 'done');
        logLine(`  ${ev.count} preview(s) ready`, 'ev-ok');
        break;
      case 'send_ok':
        composedRecipients.push({ to: ev.to, subject: '(sent)' });
        renderPick();
        logLine(`  ✓ ${ev.to} (${ev.sent}/${ev.target})`, 'ev-ok');
        break;
      case 'send_fail':
        logLine(`  ✗ ${ev.to}: ${ev.error}`, 'ev-error');
        break;
      case 'send_done':
        setStep('send', ev.failed === 0 ? 'done' : 'error');
        logLine(`▸ done — sent ${ev.sent}, failed ${ev.failed}`,
                 ev.failed === 0 ? 'ev-ok' : 'ev-error');
        break;
      case 'fatal':
        logLine(`✗ FATAL: ${ev.reason}`, 'ev-error');
        STEPS.forEach(s => {
          const el = document.querySelector(`.vm-step[data-step="${s}"]`);
          if (el && el.classList.contains('active')) el.className = 'vm-step error';
        });
        break;
      case 'compose_error':
        logLine(`  compose error for ${ev.login}: ${ev.error}`, 'ev-error');
        break;
      case 'analyse_fallback':
        logLine(`  (LLM analyse failed, falling back to heuristic: ${ev.reason})`, 'ev-warn');
        break;
      case 'stderr':
        logLine(`  [stderr] ${ev.msg}`, 'ev-warn');
        break;
      case 'log':
        logLine(`  ${ev.msg}`);
        break;
      case 'exit':
        logLine(`  process exited (code ${ev.code})`);
        break;
      default:
        logLine(`  ${t} ${JSON.stringify(ev).slice(0, 200)}`);
    }
  }

  function renderPick() {
    if (composedRecipients.length === 0) return;
    if ($pick.disabled) {
      $pick.disabled = false;
      $copy.disabled = false;
      $pick.innerHTML = '';
    }
    $pick.innerHTML = composedRecipients.map(
      (r, i) => `<option value="${i}">${r.to} — ${r.subject || ''}</option>`
    ).join('');
    if (!$pick.dataset.bound) {
      $pick.addEventListener('change', () => showPreview($pick.value));
      $pick.dataset.bound = '1';
    }
    if ($pick.value === '' || $pick.value == null) {
      $pick.value = '0';
      showPreview(0);
    }
  }

  async function showPreview(i) {
    const status = await fetchJSON(`/api/gitmail/status/${jobId}?since=0`);
    if (!status.ok || !status.data) return;
    const sendPreviews = (status.data.summary && status.data.summary.send && status.data.summary.send.previews)
      || extractPreviews(status.data.events);
    if (!sendPreviews || !sendPreviews[i]) {
      $previewMeta.textContent = '(not ready yet)';
      return;
    }
    const item = sendPreviews[i];
    $previewMeta.textContent = `to: ${item.email}\nlogin: @${item.login}\nstarred: ${item.starred_repo || '(unknown)'}`;
    $previewSubject.textContent = item.subject || '';
    $previewBody.textContent = (item.preview_headers ? item.preview_headers + '\n\n' : '') + (item.body || '');
  }

  function extractPreviews(events) {
    // Walk in reverse to find the most recent done summary if present.
    for (let i = events.length - 1; i >= 0; i--) {
      const e = events[i];
      if (e.event === 'done' && e.send && e.send.previews) return e.send.previews;
    }
    return null;
  }

  $copy.addEventListener('click', () => {
    const txt = $previewBody.textContent;
    if (!txt) return;
    navigator.clipboard.writeText(txt).then(() => toast('copied', 'ok'));
  });

  $cancel.addEventListener('click', async () => {
    if (!jobId) return;
    const r = await fetchJSON(`/api/gitmail/cancel/${jobId}`, { method: 'POST' });
    if (r.ok && r.data && r.data.ok) toast('cancelled', 'ok');
    else toast('cancel failed', 'error');
  });

  async function loadCredStatus() {
    const data = await refreshStatus('smtp');
    if (!data) return;
    const subset = {
      github: data.github,
      smtp: data.smtp,
      llm: {
        claude: data.claude.configured,
        openai: data.openai.configured,
        gemini: data.gemini.configured,
      },
    };
    $credStatus.textContent = JSON.stringify(subset, null, 2);
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('gm-start').addEventListener('click', start);
    ['gm-max', 'gm-template', 'gm-dryrun'].forEach(id => {
      document.getElementById(id).addEventListener('input', refreshCostHint);
      document.getElementById(id).addEventListener('change', refreshCostHint);
    });
    refreshCostHint();
    bindCredsForm('.vm-creds-form[data-platform="gitmail"]', loadCredStatus);
    loadCredStatus();
  });
})();
