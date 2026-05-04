(function () {
  'use strict';

  const State = { subs: [], threads: [] };

  document.addEventListener('DOMContentLoaded', () => {
    const $title = document.getElementById('rd-title');
    const $body = document.getElementById('rd-body');
    const $meta = document.getElementById('rd-meta');
    const $flags = document.getElementById('rd-flags');
    const $subInput = document.getElementById('rd-sub-input');
    const $threads = document.getElementById('rd-threads');
    const $preview = document.getElementById('rd-preview');

    function refreshMeta() {
      $meta.textContent = `title ${$title.value.length}/300 · body ${$body.value.length} chars`;
      $meta.classList.toggle('over', $title.value.length > 300);
    }

    function renderFlags(flags) {
      if (!flags || !flags.length) {
        $flags.innerHTML = `<li class="empty">${VM.T('send.no_flags')}</li>`;
      } else {
        $flags.innerHTML = flags.map(f => `<li>[${f.id}] ${VM.escapeHTML(f.msg)}</li>`).join('');
      }
    }

    function refreshSubs() {
      VM.renderChips('rd-subs', State.subs, (i) => {
        State.subs.splice(i, 1);
        refreshSubs();
      });
      const sub = State.subs[0] || 'programming';
      const url = `https://www.reddit.com/r/${encodeURIComponent(sub)}/submit?` +
        `title=${encodeURIComponent($title.value)}&text=${encodeURIComponent($body.value)}`;
      $preview.href = url;
    }

    let prevTimer = null;
    function previewSoon() {
      clearTimeout(prevTimer);
      prevTimer = setTimeout(async () => {
        const sub = State.subs[0] || 'programming';
        const r = await VM.fetchJSON('/api/preview/reddit', {
          method: 'POST',
          body: { subreddit: sub, title: $title.value, body: $body.value },
        });
        if (r.ok && r.data && r.data.ok) renderFlags(r.data.flags);
      }, 400);
    }

    [$title, $body].forEach(el => el.addEventListener('input', () => {
      refreshMeta(); refreshSubs(); previewSoon();
    }));

    document.getElementById('generate').addEventListener('click', () => {
      VM.generate('reddit', (data) => {
        const draft = (data.drafts || {}).reddit;
        if (!draft) return VM.toast(VM.T('gen.failed'), 'error');
        $title.value = draft.title || '';
        $body.value = draft.body || '';
        State.subs = (data.suggested_subreddits || []).slice(0, 5);
        renderFlags(draft.flags || []);
        refreshMeta();
        refreshSubs();
        VM.toast(VM.T('gen.done'), 'ok');
      });
    });

    document.getElementById('rd-sub-add').addEventListener('click', () => {
      const v = $subInput.value.trim().replace(/^r\//, '').replace(/^\//, '');
      if (!v) return;
      State.subs.push(v);
      $subInput.value = '';
      refreshSubs();
    });
    $subInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); document.getElementById('rd-sub-add').click(); }
    });

    document.getElementById('rd-scan').addEventListener('click', async () => {
      if (!State.subs.length) return VM.toast(VM.T('tg.add_sub_first'), 'error');
      const btn = document.getElementById('rd-scan');
      btn.disabled = true; btn.textContent = VM.T('tg.scanning');
      const project = VM.readProject();
      const r = await VM.fetchJSON('/api/scrape/reddit-threads', {
        method: 'POST',
        body: { subreddits: State.subs, keywords: (project.desc || '').split(/\s+/).slice(0, 5) },
      });
      btn.disabled = false; btn.textContent = VM.T('tg.scan');
      if (!r.ok || !r.data || !r.data.threads || !r.data.threads.length) {
        $threads.innerHTML = `<li class="empty">${VM.T('tg.no_threads')}</li>`;
        return;
      }
      State.threads = r.data.threads;
      $threads.innerHTML = r.data.threads.map((t, i) => `
        <li>
          <input type="checkbox" data-i="${i}">
          <div>
            <div class="th-title"><a href="${t.url}" target="_blank">${VM.escapeHTML(t.title)}</a></div>
            <div class="th-meta">r/${t.subreddit} · ${t.score}↑ · ${t.comments} comments</div>
          </div>
        </li>
      `).join('');
    });

    document.getElementById('rd-post').addEventListener('click', async () => {
      if (!State.subs.length) return VM.toast(VM.T('tg.add_sub_first'), 'error');
      if (!$title.value.trim()) return VM.toast(VM.T('reddit.title_required'), 'error');
      if (!confirm(VM.T('send.real_check'))) return;
      const r = await VM.fetchJSON('/api/post/reddit', {
        method: 'POST',
        body: {
          subreddit: State.subs[0],
          title: $title.value,
          body: $body.value,
        },
      });
      if (r.ok && r.data && r.data.ok) {
        VM.toast(VM.T('send.posted'), 'ok');
        if (r.data.url) window.open(r.data.url, '_blank');
      } else {
        VM.toast((r.data && (r.data.stderr || r.data.error)) || VM.T('send.failed'), 'error');
      }
    });

    refreshMeta(); refreshSubs();
  });
})();
