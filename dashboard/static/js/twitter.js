(function () {
  'use strict';
  const { fetchJSON, toast, debounce, refreshStatus,
          bindCredsForm, bindOAuthButtons, setRedirectHint } = window.VM;

  const $body = document.getElementById('tw-body');
  const $meta = document.getElementById('tw-meta');
  const $flags = document.getElementById('tw-flags');
  const $thread = document.getElementById('tw-thread');
  const $compose = document.getElementById('tw-compose-link');
  const $credStatus = document.getElementById('tw-cred-status');

  function updateMeta() {
    const text = $body.value;
    const first = text.split('---')[0].trim();
    $meta.textContent = `${first.length} / 280`;
    $meta.style.color = first.length > 280 ? 'var(--err)' : '';
  }

  async function preview() {
    const r = await fetchJSON('/api/preview/twitter', {
      method: 'POST', body: { body: $body.value },
    });
    if (!r.ok || !r.data || !r.data.ok) {
      toast((r.data && r.data.error) || 'preview failed', 'error');
      return;
    }
    const d = r.data;
    $compose.href = d.compose_url;
    $compose.textContent = d.compose_url;
    if (!d.flags || !d.flags.length) {
      $flags.className = 'vm-flags vm-empty';
      $flags.textContent = d.over_limit ? `over 280 (${d.char_count})` : 'clean';
    } else {
      $flags.className = 'vm-flags';
      $flags.innerHTML = d.flags.map(f => `<li>[${f.id}] ${f.msg}</li>`).join('');
    }
    $thread.innerHTML = (d.thread_parts || []).map(
      p => `<li>${escapeHTML(p)}  <span class="vm-meta">(${p.length})</span></li>`
    ).join('');
  }

  async function post() {
    const body = $body.value.trim();
    if (!body) return toast('write something first', 'error');
    if (!confirm('post to X under your account?')) return;
    const r = await fetchJSON('/api/post/twitter', {
      method: 'POST', body: { body },
    });
    if (r.ok && r.data && r.data.ok) {
      toast('posted ✓', 'ok');
      const url = r.data.url;
      if (url && /^https?:/.test(url)) window.open(url, '_blank');
    } else {
      toast((r.data && (r.data.stderr || r.data.error)) || 'post failed', 'error');
    }
  }

  function escapeHTML(s) {
    return s.replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[c]);
  }

  async function loadCredStatus() {
    const data = await refreshStatus('twitter');
    if (!data) return;
    $credStatus.textContent = JSON.stringify(data.twitter, null, 2);
  }

  document.addEventListener('DOMContentLoaded', () => {
    $body.addEventListener('input', updateMeta);
    $body.addEventListener('input', debounce(preview, 350));
    document.getElementById('tw-preview').addEventListener('click', preview);
    document.getElementById('tw-post').addEventListener('click', post);
    bindCredsForm('.vm-creds-form[data-platform="twitter"]', loadCredStatus);
    bindOAuthButtons('twitter');
    setRedirectHint();
    loadCredStatus();
    updateMeta();
  });
})();
