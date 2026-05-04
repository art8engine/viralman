(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    // Tab switching
    const tabs = document.querySelectorAll('.setup-tab');
    const panes = document.querySelectorAll('.setup-pane');
    function activate(name) {
      tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
      panes.forEach(p => p.classList.toggle('hidden', p.dataset.pane !== name));
    }
    tabs.forEach(t => t.addEventListener('click', () => activate(t.dataset.tab)));

    // Auto-open the right tab if URL has ?platform=...
    const params = new URLSearchParams(location.search);
    const platform = params.get('platform');
    const missing = params.get('missing');
    if (platform) {
      activate(platform === 'twitter' ? 'twitter'
        : platform === 'reddit' ? 'reddit'
        : platform === 'linkedin' ? 'linkedin'
        : platform === 'gitmail' ? 'gitmail'
        : 'twitter');
      if (missing === 'client_id') {
        VM.toast(`save ${platform} OAuth client_id + secret first`, 'warn');
      }
    }

    // Save buttons — bind every .creds-form
    document.querySelectorAll('.creds-form').forEach(form => {
      const btn = form.querySelector('button.save');
      if (!btn) return;
      btn.addEventListener('click', async () => {
        btn.disabled = true; btn.textContent = 'saving…';
        const inputs = form.querySelectorAll('input[data-key]');
        let saved = 0, failed = 0;
        for (const el of inputs) {
          const v = (el.value || '').trim();
          if (!v) continue;
          const r = await VM.fetchJSON('/api/creds/manual', {
            method: 'POST',
            body: { key: el.dataset.key, value: v, secret: el.hasAttribute('data-secret') },
          });
          if (r.ok && r.data && r.data.ok) { saved++; el.value = ''; } else failed++;
        }
        btn.disabled = false; btn.textContent = 'save';
        if (saved && !failed) VM.toast(`saved ${saved}`, 'ok');
        else if (failed) VM.toast(`saved ${saved}, failed ${failed}`, 'error');
        else VM.toast('nothing to save (all empty)', 'warn');
        VM.refreshConnectStatus();
      });
    });

    // Claude Max status check
    (async () => {
      const r = await VM.fetchJSON('/api/creds/status');
      const el = document.getElementById('claudemax-status');
      if (!el) return;
      const cli = (r.data || {}).claude_cli || {};
      if (cli.available) {
        el.className = 'claudemax-status ok';
        el.textContent = `✓ claude CLI detected at ${cli.path}` + (cli.version ? ` (${cli.version})` : '');
      } else {
        el.className = 'claudemax-status bad';
        el.textContent = '✗ claude CLI not found on PATH';
      }
    })();

    // Update redirect URI hints with the current origin (so users see actual URL).
    const origin = window.location.origin;
    ['twitter', 'reddit', 'linkedin'].forEach(p => {
      const el = document.getElementById(`setup-redir-${p}`);
      if (el) el.textContent = `${origin}/oauth/${p}/callback`;
    });
  });
})();
