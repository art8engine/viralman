// Translation table for the dashboard. 4 languages, flat keys.
window.VM_I18N = {
  en: {
    'connect': 'connect', 'login': 'login', 'tokens': 'tokens', 'setup': 'setup',
    'close': 'close', 'cancel': 'cancel', 'auto': 'auto', 'provider': 'provider',
    'generate': 'generate', 'connected': 'connected', 'not_set': 'not set',

    'block.project': 'project',
    'block.intent': 'what to write',
    'project.name': 'name',
    'project.url': 'github URL',
    'project.pitch': 'one-line pitch',
    'project.pitch.ph': 'cuts cost by 47% in 3 weeks',
    'project.desc': 'description',
    'project.desc.ph': "3–5 lines on what your project is and who it's for",
    'project.desc.required': 'description is required',
    'intent.ph': "tell viralman what angle, mood, what to emphasize. e.g. 'launch announcement, casually excited, lead with the 47% cost cut'",

    'gen.running': 'generating…',
    'gen.failed': 'generate failed',
    'gen.done': 'draft ready',

    'twitter.draft': 'tweet',
    'twitter.body.ph': 'generate a draft, or write your own. split a thread with --- on its own line.',
    'twitter.targets': 'hashtags',
    'twitter.preview': 'preview compose URL',
    'twitter.post': 'post',

    'reddit.draft': 'post',
    'reddit.title': 'title',
    'reddit.body': 'body (markdown)',
    'reddit.targets': 'subreddits',
    'reddit.post_to': 'posting to first subreddit',
    'reddit.preview': 'preview submit URL',
    'reddit.post': 'post',
    'reddit.title_required': 'title required',

    'gitmail.template': 'email template',
    'gitmail.template_hint': '{{login}} and {{starred_repo}} get filled per recipient.',
    'gitmail.body.ph': 'generated email body — uses {{login}} and {{starred_repo}}',
    'gitmail.recipients': 'recipients',
    'gitmail.start': 'start',
    'gitmail.progress': 'progress',
    'gitmail.no_recipients': 'no recipients yet',
    'gitmail.collecting': 'collecting…',
    'gitmail.copy_mime': 'copy raw MIME',
    'gitmail.copied': 'copied',

    'tg.add_hashtag': 'add hashtag',
    'tg.add_subreddit': 'add subreddit (without r/)',
    'tg.click_scan': 'click "scan" to fetch',
    'tg.scan': 'scan threads',
    'tg.scanning': 'scanning…',
    'tg.no_threads': 'no recent threads matched',
    'tg.add_sub_first': 'add a subreddit first',
    'tg.max_users': 'max users',
    'tg.min_stars': 'min stars',
    'tg.template_only': 'template-only (cheaper)',

    'send.dryrun': "dry-run (don't actually send)",
    'send.confirm': 'I confirm I want to send under my account',
    'send.real_check': 'Send for real, under your account?',
    'send.no_run': 'no run yet',
    'send.cancelled': 'cancelled',
    'send.empty': 'write something first',
    'send.posted': 'posted ✓',
    'send.failed': 'failed',
    'send.no_flags': 'no flags',
    'send.saved': 'saved',

    'step.analyse': 'analyse',
    'step.search': 'search',
    'step.recipients': 'recipients',
    'step.compose': 'compose',
    'step.send': 'send',
  },

  ko: {
    'connect': '연결', 'login': '로그인', 'tokens': '토큰', 'setup': '설정',
    'close': '닫기', 'cancel': '취소', 'auto': '자동', 'provider': '프로바이더',
    'generate': '생성', 'connected': '연결됨', 'not_set': '미설정',

    'block.project': '프로젝트',
    'block.intent': '무엇을 쓸까',
    'project.name': '이름',
    'project.url': 'GitHub URL',
    'project.pitch': '한 줄 요약',
    'project.pitch.ph': '3주만에 운영 비용을 47% 줄였다',
    'project.desc': '설명',
    'project.desc.ph': '3~5줄로 프로젝트가 무엇이고 누구를 위한 것인지',
    'project.desc.required': '설명을 입력해주세요',
    'intent.ph': "어떤 톤·각도·강조점으로 쓸지 적기. 예: '런칭 공지, 가볍게 텐션 있게, 47% 비용 절감을 앞에 둘 것'",

    'gen.running': '생성 중…',
    'gen.failed': '생성 실패',
    'gen.done': '초안 완성',

    'twitter.draft': '트윗',
    'twitter.body.ph': '생성 버튼으로 초안을 받거나 직접 작성. 스레드는 한 줄에 ---',
    'twitter.targets': '해시태그',
    'twitter.preview': 'compose URL 미리보기',
    'twitter.post': '게시',

    'reddit.draft': '포스트',
    'reddit.title': '제목',
    'reddit.body': '본문 (markdown)',
    'reddit.targets': '서브레딧',
    'reddit.post_to': '첫 번째 서브레딧으로 게시',
    'reddit.preview': 'submit URL 미리보기',
    'reddit.post': '게시',
    'reddit.title_required': '제목을 입력해주세요',

    'gitmail.template': '이메일 템플릿',
    'gitmail.template_hint': '{{login}}과 {{starred_repo}}가 수신자마다 자동 치환된다.',
    'gitmail.body.ph': '이메일 본문 — {{login}}과 {{starred_repo}} 사용 가능',
    'gitmail.recipients': '수신자',
    'gitmail.start': '시작',
    'gitmail.progress': '진행',
    'gitmail.no_recipients': '아직 수신자 없음',
    'gitmail.collecting': '수집 중…',
    'gitmail.copy_mime': '원본 MIME 복사',
    'gitmail.copied': '복사됨',

    'tg.add_hashtag': '해시태그 추가',
    'tg.add_subreddit': '서브레딧 추가 (r/ 없이)',
    'tg.click_scan': '"스캔"을 눌러 가져오기',
    'tg.scan': '스레드 스캔',
    'tg.scanning': '스캔 중…',
    'tg.no_threads': '관련 스레드를 찾지 못함',
    'tg.add_sub_first': '서브레딧을 먼저 추가',
    'tg.max_users': '최대 인원',
    'tg.min_stars': '최소 ★ 수',
    'tg.template_only': '템플릿 전용 (저렴)',

    'send.dryrun': '드라이런 (실제 발송 안 함)',
    'send.confirm': '내 계정으로 발송하는 것에 동의함',
    'send.real_check': '실제로 보낼까?',
    'send.no_run': '아직 실행 안 됨',
    'send.cancelled': '취소됨',
    'send.empty': '뭐라도 써',
    'send.posted': '게시됨 ✓',
    'send.failed': '실패',
    'send.no_flags': '플래그 없음',
    'send.saved': '저장됨',

    'step.analyse': '분석',
    'step.search': '검색',
    'step.recipients': '수신자',
    'step.compose': '작성',
    'step.send': '발송',
  },

  zh: {
    'connect': '连接', 'login': '登录', 'tokens': '令牌', 'setup': '设置',
    'close': '关闭', 'cancel': '取消', 'auto': '自动', 'provider': '提供商',
    'generate': '生成', 'connected': '已连接', 'not_set': '未设置',

    'block.project': '项目',
    'block.intent': '写什么',
    'project.name': '名称',
    'project.url': 'GitHub URL',
    'project.pitch': '一句话定位',
    'project.pitch.ph': '三周内把生产账单砍了 47%',
    'project.desc': '描述',
    'project.desc.ph': '3-5 行说明项目是什么、给谁用',
    'project.desc.required': '需要填写描述',
    'intent.ph': "告诉 viralman 用什么角度、语气、强调什么。例：'发布公告，轻松带感，先讲 47% 降本'",

    'gen.running': '生成中…',
    'gen.failed': '生成失败',
    'gen.done': '草稿完成',

    'twitter.draft': '推文',
    'twitter.body.ph': '点生成获取草稿，或自己写。串文用单独一行的 --- 分隔',
    'twitter.targets': 'hashtag',
    'twitter.preview': 'compose URL 预览',
    'twitter.post': '发送',

    'reddit.draft': '帖子',
    'reddit.title': '标题',
    'reddit.body': '正文 (markdown)',
    'reddit.targets': '子版块',
    'reddit.post_to': '发到第一个子版块',
    'reddit.preview': 'submit URL 预览',
    'reddit.post': '发送',
    'reddit.title_required': '标题不能为空',

    'gitmail.template': '邮件模板',
    'gitmail.template_hint': '{{login}} 和 {{starred_repo}} 会按收件人填充。',
    'gitmail.body.ph': '邮件正文 — 可用 {{login}} 和 {{starred_repo}}',
    'gitmail.recipients': '收件人',
    'gitmail.start': '开始',
    'gitmail.progress': '进度',
    'gitmail.no_recipients': '尚无收件人',
    'gitmail.collecting': '收集中…',
    'gitmail.copy_mime': '复制 MIME',
    'gitmail.copied': '已复制',

    'tg.add_hashtag': '添加 hashtag',
    'tg.add_subreddit': '添加子版块（不带 r/）',
    'tg.click_scan': '点 "扫描" 获取',
    'tg.scan': '扫描帖子',
    'tg.scanning': '扫描中…',
    'tg.no_threads': '没有找到相关帖子',
    'tg.add_sub_first': '请先添加一个子版块',
    'tg.max_users': '最大人数',
    'tg.min_stars': '最低 ★ 数',
    'tg.template_only': '仅模板（更便宜）',

    'send.dryrun': '演练（不实际发送）',
    'send.confirm': '我确认要用我的账号发送',
    'send.real_check': '确定要真实发送吗？',
    'send.no_run': '尚未运行',
    'send.cancelled': '已取消',
    'send.empty': '先写点东西',
    'send.posted': '已发送 ✓',
    'send.failed': '失败',
    'send.no_flags': '无标记',
    'send.saved': '已保存',

    'step.analyse': '分析',
    'step.search': '搜索',
    'step.recipients': '收件人',
    'step.compose': '撰写',
    'step.send': '发送',
  },

  ja: {
    'connect': '接続', 'login': 'ログイン', 'tokens': 'トークン', 'setup': '設定',
    'close': '閉じる', 'cancel': 'キャンセル', 'auto': '自動', 'provider': 'プロバイダ',
    'generate': '生成', 'connected': '接続済み', 'not_set': '未設定',

    'block.project': 'プロジェクト',
    'block.intent': '何を書く',
    'project.name': '名前',
    'project.url': 'GitHub URL',
    'project.pitch': '一言ピッチ',
    'project.pitch.ph': '3 週間で本番コストを 47% 削減',
    'project.desc': '説明',
    'project.desc.ph': '3〜5 行でプロジェクトの内容と対象ユーザー',
    'project.desc.required': '説明を入力してください',
    'intent.ph': "viralman に角度・トーン・強調したい点を伝える。例: 'ローンチ告知、軽くテンション高め、47% 削減を先に出す'",

    'gen.running': '生成中…',
    'gen.failed': '生成失敗',
    'gen.done': '下書き完成',

    'twitter.draft': 'ツイート',
    'twitter.body.ph': '生成ボタンで下書きを取得、もしくは自分で書く。スレッドは --- だけの行で区切る',
    'twitter.targets': 'ハッシュタグ',
    'twitter.preview': 'compose URL プレビュー',
    'twitter.post': '投稿',

    'reddit.draft': '投稿',
    'reddit.title': 'タイトル',
    'reddit.body': '本文 (markdown)',
    'reddit.targets': 'サブレディット',
    'reddit.post_to': '最初のサブレディットへ投稿',
    'reddit.preview': 'submit URL プレビュー',
    'reddit.post': '投稿',
    'reddit.title_required': 'タイトルを入力してください',

    'gitmail.template': 'メールテンプレート',
    'gitmail.template_hint': '{{login}} と {{starred_repo}} は受信者ごとに置換される。',
    'gitmail.body.ph': 'メール本文 — {{login}} と {{starred_repo}} が使える',
    'gitmail.recipients': '受信者',
    'gitmail.start': '開始',
    'gitmail.progress': '進捗',
    'gitmail.no_recipients': '受信者なし',
    'gitmail.collecting': '収集中…',
    'gitmail.copy_mime': '生 MIME をコピー',
    'gitmail.copied': 'コピーした',

    'tg.add_hashtag': 'ハッシュタグ追加',
    'tg.add_subreddit': 'サブレディット追加（r/ なし）',
    'tg.click_scan': '「スキャン」を押して取得',
    'tg.scan': 'スレッド検索',
    'tg.scanning': 'スキャン中…',
    'tg.no_threads': '該当スレッドなし',
    'tg.add_sub_first': '先にサブレディットを追加',
    'tg.max_users': '最大人数',
    'tg.min_stars': '最低 ★ 数',
    'tg.template_only': 'テンプレのみ（安価）',

    'send.dryrun': 'ドライラン（実送信しない）',
    'send.confirm': '自分のアカウントで送信することに同意',
    'send.real_check': '本当に送信する？',
    'send.no_run': '未実行',
    'send.cancelled': 'キャンセル',
    'send.empty': '何か書いてから',
    'send.posted': '投稿した ✓',
    'send.failed': '失敗',
    'send.no_flags': 'フラグなし',
    'send.saved': '保存した',

    'step.analyse': '分析',
    'step.search': '検索',
    'step.recipients': '受信者',
    'step.compose': '作成',
    'step.send': '送信',
  },
};

window.VM_T = function (key, lang) {
  const L = window.VM_I18N[lang] || window.VM_I18N.en;
  return L[key] !== undefined ? L[key] : (window.VM_I18N.en[key] !== undefined ? window.VM_I18N.en[key] : key);
};

window.VM_APPLY_I18N = function (lang) {
  const T = (k) => window.VM_T(k, lang);
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = T(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = T(el.dataset.i18nPlaceholder); });
  document.documentElement.setAttribute('lang', lang);
};

window.VM_DETECT_LANG = function () {
  const stored = localStorage.getItem('vm.lang');
  if (stored && ['en', 'ko', 'zh', 'ja'].includes(stored)) return stored;
  const nav = (navigator.language || 'en').toLowerCase();
  if (nav.startsWith('ko')) return 'ko';
  if (nav.startsWith('zh')) return 'zh';
  if (nav.startsWith('ja')) return 'ja';
  return 'en';
};
