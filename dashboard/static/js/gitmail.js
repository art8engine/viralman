(function () {
  'use strict';

  const State = { jobId: null, since: 0, timer: null, recipients: [], previews: [] };

  document.addEventListener('DOMContentLoaded', () => {
    const $body = document.getElementById('gm-body');
    const $log = document.getElementById('gm-log');
    const $start = document.getElementById('gm-start');
    const $cancel = document.getElementById('gm-cancel');
    const $confirm = document.getElementById('gm-confirm');
    const $dryrun = document.getElementById('gm-dryrun');
    const $pick = document.getElementById('gm-pick');
    const $copy = document.getElementById('gm-copy');
    const $preview = document.getElementById('gm-preview');

    function setStep(name, state) {
      document.querySelectorAll('.prog-step').forEach(el => {
        if (el.dataset.step === name) el.className = `prog-step ${state}`;
      });
    }
    function resetSteps() {
      document.querySelectorAll('.prog-step').forEach(el => { el.className = 'prog-step'; });
    }

    function logLine(text, cls) {
      if ($log.textContent === VM.T('send.no_run')) $log.textContent = '';
      const span = document.createElement('span');
      if (cls) span.className = cls;
      span.textContent = text + '\n';
      $log.appendChild(span);
      $log.scrollTop = $log.scrollHeight;
    }

    document.getElementById('generate').addEventListener('click', () => {
      VM.generate('gitmail', (data) => {
        const draft = (data.drafts || {}).gitmail;
        if (!draft) return VM.toast(VM.T('gen.failed'), 'error');
        $body.value = draft.body || '';
        VM.toast(VM.T('gen.done'), 'ok');
      });
    });

    $confirm.addEventListener('change', () => {
      $start.disabled = !$confirm.checked;
    });

    $start.addEventListener('click', async () => {
      const project = VM.readProject();
      if (!project.desc) return VM.toast(VM.T('project.desc.required'), 'error');
      const max = parseInt(document.getElementById('gm-max').value, 10) || 100;
      const dry = $dryrun.checked;
      if (!dry && !confirm(VM.T('send.real_check'))) return;

      resetSteps();
      $log.textContent = '';
      State.recipients = [];
      State.previews = [];
      $pick.innerHTML = `<option>${VM.T('gitmail.collecting')}</option>`;
      $pick.disabled = true;
      $copy.disabled = true;

      const r = await VM.fetchJSON('/api/gitmail/start', {
        method: 'POST',
        body: {
          project_name: project.name,
          project_url: project.url,
          description: project.desc,
          pitch: project.pitch,
          max_users: max,
          min_stars: parseInt(document.getElementById('gm-min-stars').value, 10) || 200,
          template_only: document.getElementById('gm-template').checked,
          provider: project.provider || null,
          dry_run: dry,
          custom_template: $body.value || null,
          intent: project.intent || '',
        },
      });
      if (!r.ok || !r.data || !r.data.ok) {
        VM.toast((r.data && r.data.error) || VM.T('gen.failed'), 'error');
        return;
      }
      State.jobId = r.data.job_id;
      State.since = 0;
      $start.disabled = true;
      $cancel.disabled = false;
      State.timer = setInterval(poll, 1500);
      poll();
    });

    $cancel.addEventListener('click', async () => {
      if (State.jobId) {
        await VM.fetchJSON(`/api/gitmail/cancel/${State.jobId}`, { method: 'POST' });
      }
      if (State.timer) { clearInterval(State.timer); State.timer = null; }
      $cancel.disabled = true;
      $start.disabled = false;
      VM.toast(VM.T('send.cancelled'), 'warn');
    });

    async function poll() {
      if (!State.jobId) return;
      const r = await VM.fetchJSON(`/api/gitmail/status/${State.jobId}?since=${State.since}`);
      if (!r.ok || !r.data) return;
      State.since = r.data.next_since;
      for (const ev of r.data.events) handleEvent(ev);
      if (['done', 'error', 'cancelled'].includes(r.data.status)) {
        clearInterval(State.timer);
        State.timer = null;
        State.jobId = null;
        $cancel.disabled = true;
        $start.disabled = !$confirm.checked;
        if (r.data.summary && r.data.summary.send && r.data.summary.send.previews) {
          State.previews = r.data.summary.send.previews;
          renderPreviewsPick();
        }
      }
    }

    function handleEvent(ev) {
      const t = ev.event;
      switch (t) {
        case 'analyse_start':       setStep('analyse', 'active'); logLine('▸ analyse'); break;
        case 'analyse_done':
          setStep('analyse', 'done');
          logLine(`  summary: ${ev.summary || ''}`, 'ev-ok');
          break;
        case 'search_start': setStep('search', 'active'); logLine(`▸ search`); break;
        case 'search_done':
          setStep('search', ev.count ? 'done' : 'error');
          logLine(`  ${ev.count} repo(s)`, ev.count ? 'ev-ok' : 'ev-error');
          break;
        case 'recipients_start': setStep('recipients', 'active'); logLine(`▸ recipients`); break;
        case 'recipients_progress': logLine(`  ${ev.count}/${ev.target}`); break;
        case 'recipients_done':
          setStep('recipients', ev.count ? 'done' : 'error');
          logLine(`  collected ${ev.count}`, ev.count ? 'ev-ok' : 'ev-error');
          break;
        case 'compose_start': setStep('compose', 'active'); logLine(`▸ compose`); break;
        case 'compose_done': setStep('compose', 'done'); break;
        case 'send_start': setStep('send', 'active'); logLine(`▸ send (${ev.count})`); break;
        case 'send_dry_run_start':
          setStep('send', 'active');
          logLine(`▸ dry-run preview (${ev.count})`, 'ev-warn');
          break;
        case 'send_preview':
          State.recipients.push({ to: ev.to, subject: ev.subject });
          renderPick();
          break;
        case 'send_dry_run_done':
          setStep('send', 'done');
          logLine(`  ${ev.count} preview(s) ready`, 'ev-ok');
          break;
        case 'send_ok':
          State.recipients.push({ to: ev.to, subject: '(sent)' });
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
          logLine(`✗ ${ev.reason}`, 'ev-error');
          document.querySelectorAll('.prog-step.active').forEach(el => el.className = 'prog-step error');
          break;
        case 'stderr': logLine(`  ${ev.msg}`, 'ev-warn'); break;
      }
    }

    function renderPick() {
      if (!State.recipients.length) return;
      if ($pick.disabled) {
        $pick.disabled = false;
        $copy.disabled = false;
      }
      $pick.innerHTML = State.recipients.map(
        (r, i) => `<option value="${i}">${VM.escapeHTML(r.to)}</option>`
      ).join('');
    }

    function renderPreviewsPick() {
      if (!State.previews.length) return;
      $pick.disabled = false;
      $copy.disabled = false;
      $pick.innerHTML = State.previews.map(
        (p, i) => `<option value="${i}">${VM.escapeHTML(p.email)}</option>`
      ).join('');
      showPreview(0);
    }

    function showPreview(i) {
      const p = State.previews[i];
      if (!p) { $preview.textContent = '—'; return; }
      $preview.textContent =
        `to: ${p.email}\nlogin: @${p.login}\nstarred: ${p.starred_repo || '-'}\nsubject: ${p.subject}\n\n${p.body || ''}`;
    }

    $pick.addEventListener('change', () => showPreview(parseInt($pick.value, 10) || 0));
    $copy.addEventListener('click', () => {
      navigator.clipboard.writeText($preview.textContent).then(() => VM.toast(VM.T('gitmail.copied'), 'ok'));
    });
  });
})();
