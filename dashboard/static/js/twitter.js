(function () {
  'use strict';

  const State = { hashtags: [], flags: [] };

  document.addEventListener('DOMContentLoaded', () => {
    const $body = document.getElementById('tw-body');
    const $meta = document.getElementById('tw-meta');
    const $flags = document.getElementById('tw-flags');
    const $tags = document.getElementById('tw-tags');
    const $tagInput = document.getElementById('tw-tag-input');
    const $preview = document.getElementById('tw-preview');

    function refreshMeta() {
      const first = ($body.value || '').split('---')[0].trim();
      $meta.textContent = `${first.length} / 280`;
      $meta.classList.toggle('over', first.length > 280);
    }

    function renderFlags(flags) {
      State.flags = flags || [];
      if (!flags || !flags.length) {
        $flags.innerHTML = `<li class="empty">${VM.T('send.no_flags')}</li>`;
      } else {
        $flags.innerHTML = flags.map(f => `<li>[${f.id}] ${VM.escapeHTML(f.msg)}</li>`).join('');
      }
    }

    function refreshTags() {
      VM.renderChips('tw-tags', State.hashtags, (i) => {
        State.hashtags.splice(i, 1);
        refreshTags();
      });
      const tags = State.hashtags.length ? '\n\n' + State.hashtags.join(' ') : '';
      const text = ($body.value || '').replace(/\n\n#[\w\s#]+$/, '');
      // append hashtags only at the very end (don't double-add)
      // we leave editing free — the post API just sends $body.value as-is
      const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(($body.value || '') + tags)}`;
      $preview.href = url;
    }

    $body.addEventListener('input', () => {
      refreshMeta();
      refreshTags();
      previewSoon();
    });

    let previewTimer = null;
    function previewSoon() {
      clearTimeout(previewTimer);
      previewTimer = setTimeout(async () => {
        const r = await VM.fetchJSON('/api/preview/twitter', {
          method: 'POST', body: { body: $body.value },
        });
        if (r.ok && r.data && r.data.ok) renderFlags(r.data.flags);
      }, 400);
    }

    document.getElementById('generate').addEventListener('click', () => {
      VM.generate('twitter', (data) => {
        const draft = (data.drafts || {}).twitter;
        if (!draft) return VM.toast(VM.T('gen.failed'), 'error');
        $body.value = draft.body || '';
        State.hashtags = (data.suggested_hashtags || []).slice(0, 4);
        renderFlags(draft.flags || []);
        refreshMeta();
        refreshTags();
        VM.toast(VM.T('gen.done'), 'ok');
      });
    });

    document.getElementById('tw-tag-add').addEventListener('click', () => {
      const v = $tagInput.value.trim().replace(/^#/, '');
      if (!v) return;
      State.hashtags.push('#' + v);
      $tagInput.value = '';
      refreshTags();
    });
    $tagInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); document.getElementById('tw-tag-add').click(); }
    });

    document.getElementById('tw-post').addEventListener('click', async () => {
      const body = ($body.value || '').trim();
      if (!body) return VM.toast(VM.T('send.empty'), 'error');
      if (!confirm(VM.T('send.real_check'))) return;
      const tags = State.hashtags.length ? '\n\n' + State.hashtags.join(' ') : '';
      const r = await VM.fetchJSON('/api/post/twitter', {
        method: 'POST', body: { body: body + tags },
      });
      if (r.ok && r.data && r.data.ok) {
        VM.toast(VM.T('send.posted'), 'ok');
        if (r.data.url && /^https?:/.test(r.data.url)) window.open(r.data.url, '_blank');
      } else {
        VM.toast((r.data && (r.data.stderr || r.data.error)) || VM.T('send.failed'), 'error');
      }
    });

    refreshMeta();
    refreshTags();
  });
})();
