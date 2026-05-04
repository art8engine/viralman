(function () {
  'use strict';

  const PAGE_SIZE = 15;
  const State = {
    collectJobId: null, collectSince: 0, collectTimer: null,
    sendJobId: null, sendSince: 0, sendTimer: null,
    recipients: [],          // [{login,email,starred_repo,profile}]
    selected: new Set(),     // login set
    page: 0,
    previews: [],
  };

  document.addEventListener('DOMContentLoaded', () => {
    const $body = document.getElementById('gm-body');
    const $log = document.getElementById('gm-log');

    const $collect = document.getElementById('gm-collect');
    const $collectCancel = document.getElementById('gm-collect-cancel');
    const $collectMeta = document.getElementById('gm-collect-meta');

    const $recWrap = document.getElementById('gm-rec-wrap');
    const $recAll = document.getElementById('gm-rec-all');
    const $recSummary = document.getElementById('gm-rec-summary');
    const $recBody = document.getElementById('gm-rec-tbody');
    const $recPrev = document.getElementById('gm-rec-prev');
    const $recNext = document.getElementById('gm-rec-next');
    const $recPage = document.getElementById('gm-rec-page');

    const $send = document.getElementById('gm-send');
    const $sendCancel = document.getElementById('gm-send-cancel');
    const $sendCount = document.getElementById('gm-send-count');
    const $confirm = document.getElementById('gm-confirm');
    const $dryrun = document.getElementById('gm-dryrun');

    const $pick = document.getElementById('gm-pick');
    const $copy = document.getElementById('gm-copy');
    const $preview = document.getElementById('gm-preview');

    function setStep(name, state) {
      document.querySelectorAll(`.prog-step[data-step="${name}"]`).forEach(el => {
        el.className = `prog-step ${state}`;
      });
    }
    function resetCollectSteps() {
      ['analyse','search','recipients'].forEach(s => setStep(s, ''));
    }
    function logLine(text, cls) {
      if ($log.textContent === VM.T('send.no_run')) $log.textContent = '';
      const span = document.createElement('span');
      if (cls) span.className = cls;
      span.textContent = text + '\n';
      $log.appendChild(span);
      $log.scrollTop = $log.scrollHeight;
    }

    // ───── Generate (template) ─────
    document.getElementById('generate').addEventListener('click', () => {
      VM.generate('gitmail', (data) => {
        const draft = (data.drafts || {}).gitmail;
        if (!draft) return VM.toast(VM.T('gen.failed'), 'error');
        $body.value = draft.body || '';
        VM.toast(VM.T('gen.done'), 'ok');
      });
    });

    // ───── Collect ─────
    $collect.addEventListener('click', async () => {
      const project = VM.readProject();
      if (!project.desc) return VM.toast(VM.T('project.desc.required'), 'error');
      const max = parseInt(document.getElementById('gm-max').value, 10) || 100;
      if (max < 1 || max > 10000) return VM.toast('max 1..10000', 'error');

      resetCollectSteps();
      State.recipients = [];
      State.selected.clear();
      State.page = 0;
      $recWrap.hidden = true;
      $collectMeta.textContent = '';
      updateSelectedSummary();

      const r = await VM.fetchJSON('/api/gitmail/collect', {
        method: 'POST',
        body: {
          description: project.desc,
          project_name: project.name,
          project_url: project.url,
          pitch: project.pitch,
          max_users: max,
          min_stars: parseInt(document.getElementById('gm-min-stars').value, 10) || 200,
        },
      });
      if (!r.ok || !r.data || !r.data.ok) {
        VM.toast((r.data && r.data.error) || 'failed to start', 'error');
        return;
      }
      State.collectJobId = r.data.job_id;
      State.collectSince = 0;
      $collect.disabled = true;
      $collectCancel.disabled = false;
      State.collectTimer = setInterval(pollCollect, 1500);
      pollCollect();
    });

    $collectCancel.addEventListener('click', async () => {
      if (State.collectJobId) {
        await VM.fetchJSON(`/api/gitmail/cancel/${State.collectJobId}`, { method: 'POST' });
      }
      stopCollect();
      VM.toast(VM.T('send.cancelled'), 'warn');
    });

    function stopCollect() {
      if (State.collectTimer) { clearInterval(State.collectTimer); State.collectTimer = null; }
      State.collectJobId = null;
      $collect.disabled = false;
      $collectCancel.disabled = true;
    }

    async function pollCollect() {
      if (!State.collectJobId) return;
      const r = await VM.fetchJSON(`/api/gitmail/status/${State.collectJobId}?since=${State.collectSince}`);
      if (!r.ok || !r.data) return;
      State.collectSince = r.data.next_since;
      for (const ev of r.data.events) handleCollectEvent(ev);
      if (['done','error','cancelled'].includes(r.data.status)) stopCollect();
    }

    function handleCollectEvent(ev) {
      switch (ev.event) {
        case 'analyse_start': setStep('analyse','active'); break;
        case 'analyse_done':
          setStep('analyse','done');
          $collectMeta.textContent = `keywords: ${(ev.keywords||[]).join(', ').slice(0,80)}`;
          break;
        case 'search_start': setStep('search','active'); break;
        case 'search_done': setStep('search', ev.count ? 'done' : 'error'); break;
        case 'recipients_start':
          setStep('recipients','active');
          if ($recWrap.hidden) $recWrap.hidden = false;
          break;
        case 'recipient':
          State.recipients.push({
            login: ev.login, email: ev.email,
            starred_repo: ev.starred_repo, profile: ev.profile,
          });
          State.selected.add(ev.login);  // default ON; user can uncheck
          renderRecipients();
          break;
        case 'recipients_done':
          setStep('recipients','done');
          $collectMeta.textContent = `${ev.count} recipient(s) collected`;
          break;
        case 'fatal':
          setStep('recipients','error');
          $collectMeta.textContent = `error: ${ev.reason}`;
          VM.toast(ev.reason, 'error');
          break;
      }
    }

    // ───── Recipients table ─────
    function totalPages() {
      return Math.max(1, Math.ceil(State.recipients.length / PAGE_SIZE));
    }
    function renderRecipients() {
      if (!State.recipients.length) {
        $recBody.innerHTML = '';
        $recPage.textContent = '0 / 0';
        updateSelectedSummary();
        return;
      }
      if (State.page >= totalPages()) State.page = totalPages() - 1;
      const start = State.page * PAGE_SIZE;
      const slice = State.recipients.slice(start, start + PAGE_SIZE);
      $recBody.innerHTML = slice.map(r => {
        const checked = State.selected.has(r.login) ? 'checked' : '';
        return `<tr>
          <td><input type="checkbox" data-login="${VM.escapeHTML(r.login)}" ${checked}></td>
          <td><a href="${VM.escapeHTML(r.profile)}" target="_blank" rel="noopener">@${VM.escapeHTML(r.login)}</a></td>
          <td class="rec-email">${VM.escapeHTML(r.email)}</td>
          <td><a href="https://github.com/${VM.escapeHTML(r.starred_repo)}" target="_blank" rel="noopener">${VM.escapeHTML(r.starred_repo)}</a></td>
        </tr>`;
      }).join('');
      $recBody.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', () => {
          if (cb.checked) State.selected.add(cb.dataset.login);
          else State.selected.delete(cb.dataset.login);
          updateSelectedSummary();
          syncAllCheckbox();
        });
      });
      $recPage.textContent = `${State.page + 1} / ${totalPages()} · ${State.recipients.length} total`;
      syncAllCheckbox();
      updateSelectedSummary();
    }

    function updateSelectedSummary() {
      const n = State.selected.size;
      $recSummary.textContent = `${n} selected`;
      $sendCount.textContent = String(n);
      const canSend = n > 0 && $confirm.checked;
      $send.disabled = !canSend;
    }

    function syncAllCheckbox() {
      const start = State.page * PAGE_SIZE;
      const slice = State.recipients.slice(start, start + PAGE_SIZE);
      const allOn = slice.length > 0 && slice.every(r => State.selected.has(r.login));
      $recAll.checked = allOn;
    }

    $recAll.addEventListener('change', () => {
      const start = State.page * PAGE_SIZE;
      const slice = State.recipients.slice(start, start + PAGE_SIZE);
      slice.forEach(r => {
        if ($recAll.checked) State.selected.add(r.login);
        else State.selected.delete(r.login);
      });
      renderRecipients();
    });

    $recPrev.addEventListener('click', () => {
      if (State.page > 0) { State.page--; renderRecipients(); }
    });
    $recNext.addEventListener('click', () => {
      if (State.page < totalPages() - 1) { State.page++; renderRecipients(); }
    });

    // ───── Send selected ─────
    $confirm.addEventListener('change', updateSelectedSummary);

    $send.addEventListener('click', async () => {
      if (!State.selected.size) return VM.toast('no recipients selected', 'error');
      if (!$body.value.trim()) return VM.toast('email body is empty', 'error');
      const dry = $dryrun.checked;
      if (!dry && !confirm(VM.T('send.real_check'))) return;

      const project = VM.readProject();
      const recipients = State.recipients.filter(r => State.selected.has(r.login));

      setStep('send','active');
      $log.textContent = '';
      State.previews = [];
      $pick.innerHTML = `<option>${VM.T('gitmail.collecting')}</option>`;
      $pick.disabled = true;
      $copy.disabled = true;

      const r = await VM.fetchJSON('/api/gitmail/send', {
        method: 'POST',
        body: {
          recipients,
          body: $body.value,
          subject: `about ${project.name || 'your project'}`,
          project_name: project.name,
          dry_run: dry,
        },
      });
      if (!r.ok || !r.data || !r.data.ok) {
        VM.toast((r.data && r.data.error) || 'failed to start', 'error');
        setStep('send','error');
        return;
      }
      State.sendJobId = r.data.job_id;
      State.sendSince = 0;
      $send.disabled = true;
      $sendCancel.disabled = false;
      State.sendTimer = setInterval(pollSend, 1500);
      pollSend();
    });

    $sendCancel.addEventListener('click', async () => {
      if (State.sendJobId) {
        await VM.fetchJSON(`/api/gitmail/cancel/${State.sendJobId}`, { method: 'POST' });
      }
      stopSend();
      VM.toast(VM.T('send.cancelled'), 'warn');
    });

    function stopSend() {
      if (State.sendTimer) { clearInterval(State.sendTimer); State.sendTimer = null; }
      State.sendJobId = null;
      $sendCancel.disabled = true;
      updateSelectedSummary();
    }

    async function pollSend() {
      if (!State.sendJobId) return;
      const r = await VM.fetchJSON(`/api/gitmail/status/${State.sendJobId}?since=${State.sendSince}`);
      if (!r.ok || !r.data) return;
      State.sendSince = r.data.next_since;
      for (const ev of r.data.events) handleSendEvent(ev);
      if (['done','error','cancelled'].includes(r.data.status)) {
        stopSend();
        if (r.data.summary && r.data.summary.send && r.data.summary.send.previews) {
          State.previews = r.data.summary.send.previews;
          renderPreviewsPick();
        }
      }
    }

    function handleSendEvent(ev) {
      switch (ev.event) {
        case 'send_dry_run_start':
          logLine(`▸ dry-run (${ev.count})`, 'ev-warn'); break;
        case 'send_preview':
          logLine(`  preview: ${ev.to}`); break;
        case 'send_dry_run_done':
          setStep('send','done');
          logLine(`  ${ev.count} preview(s) ready`, 'ev-ok'); break;
        case 'send_start':
          logLine(`▸ send (${ev.count})`); break;
        case 'send_ok':
          logLine(`  ✓ ${ev.to} (${ev.sent}/${ev.target})`, 'ev-ok'); break;
        case 'send_fail':
          logLine(`  ✗ ${ev.to}: ${ev.error}`, 'ev-error'); break;
        case 'send_done':
          setStep('send', ev.failed === 0 ? 'done' : 'error');
          logLine(`▸ done — sent ${ev.sent}, failed ${ev.failed}`,
                  ev.failed === 0 ? 'ev-ok' : 'ev-error');
          break;
        case 'fatal':
          setStep('send','error');
          logLine(`✗ ${ev.reason}`, 'ev-error');
          VM.toast(ev.reason, 'error');
          break;
      }
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
