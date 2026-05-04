(function () {
  'use strict';
  const { fetchJSON, toast, debounce, refreshStatus,
          bindCredsForm, bindOAuthButtons, setRedirectHint } = window.VM;

  const $sub = document.getElementById('rd-sub');
  const $title = document.getElementById('rd-title');
  const $flair = document.getElementById('rd-flair');
  const $body = document.getElementById('rd-body');
  const $meta = document.getElementById('rd-meta');
  const $flags = document.getElementById('rd-flags');
  const $compose = document.getElementById('rd-compose-link');
  const $credStatus = document.getElementById('rd-cred-status');

  function updateMeta() {
    $meta.textContent = `title ${$title.value.length} / 300 · body ${$body.value.length} chars`;
    $meta.style.color = $title.value.length > 300 ? 'var(--err)' : '';
  }

  async function preview() {
    const r = await fetchJSON('/api/preview/reddit', {
      method: 'POST',
      body: { subreddit: $sub.value, title: $title.value, body: $body.value },
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
      $flags.textContent = 'clean';
    } else {
      $flags.className = 'vm-flags';
      $flags.innerHTML = d.flags.map(f => `<li>[${f.id}] ${f.msg}</li>`).join('');
    }
  }

  async function post() {
    if (!$sub.value.trim() || !$title.value.trim()) {
      return toast('subreddit and title required', 'error');
    }
    if (!confirm(`post to r/${$sub.value} under your account?`)) return;
    const r = await fetchJSON('/api/post/reddit', {
      method: 'POST',
      body: {
        subreddit: $sub.value,
        title: $title.value,
        body: $body.value,
        flair: $flair.value,
      },
    });
    if (r.ok && r.data && r.data.ok) {
      toast('posted ✓', 'ok');
      if (r.data.url) window.open(r.data.url, '_blank');
    } else {
      toast((r.data && (r.data.stderr || r.data.error)) || 'post failed', 'error');
    }
  }

  async function loadCredStatus() {
    const data = await refreshStatus('reddit');
    if (!data) return;
    $credStatus.textContent = JSON.stringify(data.reddit, null, 2);
  }

  document.addEventListener('DOMContentLoaded', () => {
    [$sub, $title, $body].forEach(el => {
      el.addEventListener('input', updateMeta);
      el.addEventListener('input', debounce(preview, 350));
    });
    document.getElementById('rd-preview').addEventListener('click', preview);
    document.getElementById('rd-post').addEventListener('click', post);
    bindCredsForm('.vm-creds-form[data-platform="reddit"]', loadCredStatus);
    bindOAuthButtons('reddit');
    setRedirectHint();
    loadCredStatus();
    updateMeta();
  });
})();
