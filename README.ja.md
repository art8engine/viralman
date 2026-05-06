<h1 align="center">viralman</h1>

<p align="center">
  <b>コードは君が、バズはこっちが。</b><br>
  作るだけでいい。拡散は viralman がやる。
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.zh.md">中文</a> ·
  <a href="README.ja.md"><b>日本語</b></a>
</p>

<p align="center">
  <img src="assets/viralman.png" alt="viralman" width="520">
</p>

---

プロジェクトの説明を渡すと、Twitter/X 投稿、Reddit スレッド、そして GitHub で似たリポにスターした開発者へのコールドメールの下書きをまとめて出す。OSS でも副業プロジェクトでも何でも使える。送信するかどうかは自分が決める。

```bash
viralman                 # http://localhost:8765 が自動で開く
```

## 機能

- **マルチプラットフォーム下書き** — `/viral` 一発で Reddit / X / LinkedIn 用の下書き。AI 臭なし。
- **ローカルダッシュボード** — ダーク基調の 4 ステップ: プロジェクト → 生成 → ターゲット → 送信。ログインは上部に統一。
- **gitmail アウトリーチ** — GitHub で似たリポを探し、スターした人に短い個別メール。最大 1 万通、ワンクリック解除リンク自動付与。
- **AI 痕跡スニファ** — 約 30 のヒューリスティクスでクリシェ、em-dash 過剰、整いすぎた三項列挙、アンカー欠落を検出。最大 3 回リライト、それでもダメなら自動配信を拒否。
- **OAuth または手動** — ダッシュボードで X / Reddit / LinkedIn にログインするか、トークン直貼り。秘密値は LLM コンテキストに絶対入らない。
- **マルチ LLM** — Claude / OpenAI / Gemini から選択（保存済みキーで自動判別）。

## こんな時に使う

- **v1.0 ローンチ** — 何をリリースしたか書けば、r/programming 向け Reddit 投稿、X スレッド、LinkedIn 告知、類似ツールにスターした開発者のアウトリーチリストまで一気に。
- **副業プロジェクトの告知** — 3 プラットフォーム用に書き分け不要。一度入力 → 全チャネル。
- **どこに投稿すべきか分からない** — viralman がキーワードからサブレディット、ハッシュタグ、コメントできる最近のスレッドをスクレイプして提案。
- **類似ツールの古いスター持ちを再エンゲージ** — gitmail が公開プロフィールとコミットメールから受信者リストを作り、相手がスターしたリポに触れる導入で個別化。
- **AI スロップ回避** — 大半の「AI 投稿ツール」は一発でバレる。スニファこそ viralman の差別化点。

## インストール

使い方に合わせて 3 つのパスから 1 つ選んでください。

### パス 1 — Claude Code プラグイン（推奨）

Claude Code の中で自然言語だけで全部やりたい人向け。

```bash
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

コマンドは覚えなくて OK — そのまま言葉で:

```
"viralman をセットアップして"  → /viralman-setup が発動。Step 0 が venv/flask/shim を自動ブートストラップ、
                               その後好きなチャンネルの認証情報を 1 つ保存。
"ダッシュボードを開いて"       → /dashboard → http://localhost:8765
"似たリポのスターガザーにメール" → /gitmail が 5 ステップ対話フローを開始
"AI っぽくない投稿を書いて"    → /viral
```

送信直前にエージェントが (1) 言語 (2) 件名スタイル (3) 最終確認 の順に確認します。

### パス 2 — ローカル CLI / ダッシュボード（Python 直接実行）

Claude Code なしで viralman だけ使いたい人、またはダッシュボード UI を使いたい人向け。

```bash
git clone https://github.com/art8engine/viralman
cd viralman
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/pip install -e .   # Python ≤ 3.13 のみ。3.14+ はこの行をスキップ（shim が代替）

# 任意：どこからでも viralman を呼べるよう shim を 1 つ置く
mkdir -p ~/.local/bin
cat > ~/.local/bin/viralman <<'SH'
#!/usr/bin/env bash
exec "$HOME/path/to/viralman/.venv/bin/python" "$HOME/path/to/viralman/bin/viralman" "$@"
SH
chmod +x ~/.local/bin/viralman
```

> **Python 3.14**: setuptools の editable install が使う実行可能 `.pth` ファイルが 3.14 で無効化された。3.14+ は上の shim 推奨。

**初回利用:**

```bash
viralman                                       # ダッシュボード → http://localhost:8765
./scripts/save_creds.py --set GITHUB_TOKEN=... # 認証情報を保存
```

ダッシュボードの 4 タブ（Twitter / Reddit / Gitmail / Setup）で全作業が完結。スラッシュコマンドは Claude Code が必要。

### パス 3 — スクリプト直接呼び出し（自動化 / CI / headless）

ダッシュボードも Claude Code も使わず、明示的な引数でスクリプトだけ動かしたい人向け。CI パイプラインで使用可。

**インストール**: パス 2 と同じ（git clone + venv + flask + パッケージ）。shim は任意。

**認証情報の保存:**

```bash
read -rs -p 'GITHUB_TOKEN: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin GITHUB_TOKEN; unset s
# SMTP 等も同じパターン
./scripts/save_creds.py --set SMTP_HOST=smtp.gmail.com --set SMTP_PORT=587
```

**gitmail 2 フェーズフロー:**

```bash
# フェーズ 1: 受信者収集（シードリポを直接指定またはキーワード）
./scripts/gitmail.py recipients \
  --seed-repos owner1/repo1,owner2/repo2 \
  --max-users 100 > recipients.json

# フェーズ 2: トーン・強調を反映した dry-run → 確認 → 本送信
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "..." \
  --tone "..." \
  --emphasis "..." \
  --subject-style headline \
  --dry-run

# 確認後に --dry-run を外して再実行すると本送信
```

**ワンショット実行:**

```bash
./scripts/gitmail.py run --description "..." --max-users 100 --dry-run
```

## 使用例

### Block A — Claude Code の中で自然言語（パス 1 ユーザー）

そのまま言葉で — エージェントが適切なスラッシュコマンドを自動で発動します:

```
"似たリポをスターした人にメールを送って"
"async-profiler をスターした人に JVM 監視ツールを紹介して"
"r/programming 向けの投稿を書いて、AI っぽくなく"
"ダッシュボードを開いて"
"viralman をセットアップして"
```

エージェントが `/gitmail`、`/viral`、`/dashboard`、`/viralman-setup` を自動で発動します。
送信直前に (1) 言語 (2) 件名スタイル (3) 最終確認 の順に確認します。

### Block B — スラッシュコマンドを直接入力（パス 1 パワーユーザー）

```
/viralman-setup gitmail
/gitmail https://github.com/myuser/myproj
/gitmail --seed-repos jvm-profiling/async-profiler --tone "フレンドリーな開発者" --emphasis "47% コスト削減"
/dashboard
/viral K8s autoscaler が 3 週間で本番コストを 47% 削減 --mode growth-story
```

### Block C — スクリプト直接呼び出し（パス 3 / CI / headless）

```bash
# 1) 認証情報を保存
read -rs -p 'GITHUB_TOKEN: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin GITHUB_TOKEN; unset s
./scripts/save_creds.py --set SMTP_HOST=smtp.gmail.com --set SMTP_PORT=587 --set SMTP_USER=you@gmail.com --set SMTP_FROM=you@gmail.com
read -rs -p 'SMTP_PASSWORD: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin SMTP_PASSWORD; unset s

# 2) 受信者を収集（シードリポを直接指定）
./scripts/gitmail.py recipients \
  --seed-repos jvm-profiling/async-profiler,oracle/graal \
  --max-users 100 > recipients.json

# 3) トーン・強調・件名スタイルを反映した dry-run —— 送信前に確認
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "フレンドリーな開発者、短く" \
  --emphasis "47% コスト削減" \
  --subject-style headline \
  --dry-run

# 4) 確認後に --dry-run を外して再実行すると本送信
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "フレンドリーな開発者、短く" \
  --emphasis "47% コスト削減" \
  --subject-style headline
```

## メール送信例

### 韓国語自動生成（デフォルト）

オプションなしで呼び出すと韓国語で生成されます（システムデフォルト）：

```
SUBJECT: 안녕하세요, 이제 당신도 쉽게 사이드 프로젝트를 알릴 수 있습니다.

안녕하세요, 저희 오픈소스 viralman 도구를 알려드리고자 메일을 보냈습니다.

이제 당신은 본인의 사이드 프로젝트를 자연스럽게 알릴 수 있습니다.

AI가 프로젝트를 분석해 어울리는 홍보 멘트를 만들어주고, 관심을 가질 만한 개발자에게 메일 발송까지 도와드립니다.

당신의 사이드 프로젝트를 쉽게 바이럴 해보세요.

관심이 있다면 이 링크를 확인하세요: https://github.com/art8engine/viralman
```

### 英語（自然言語 `--tone "in English"` 経由）

Add `--tone "in English"` (or natural-language equivalents like `영어로 써줘` / `中文で`) to switch:

```
SUBJECT: Hi, now you can easily share your side project too.

Hi, we're reaching out to share our open-source project viralman.

Now you can easily get your own side project in front of the developers most likely to care about it.

The AI reads your repository, drafts a natural outreach note in your voice, and helps you deliver it to a relevant audience.

Try giving your side project the reach it deserves, without the awkward self-promotion.

If you're curious, here is the link: https://github.com/art8engine/viralman
```

## 認証情報

```bash
/viralman-setup            # チャンネル選択 (gitmail / twitter / reddit / linkedin) して設定
/viralman-setup gitmail    # gitmail ブランチへ直行
/viralman-setup --check    # 保存済みキー一覧を確認
```

チャンネル別レガシーコマンド: `/viralman-login-reddit`（約 3 分）、`/viralman-login-twitter`（約 5 分）、`/viralman-login-linkedin`（約 10 分）、`/viralman-login-gitmail`（約 5 分）。

API キー不要でも動く: **Claude Code** があれば viralman がローカルの `claude` バイナリを自動検出し LLM 呼び出しを経由する（Claude Max plan クォータ）。ダッシュボードで `claude (Max via CLI)` を選択。

秘密値は LLM コンテキストに入らない —— `read -s` で `~/.viralman/.env`（`chmod 600`）へ直接書き込み。

## 使い方

### ダッシュボード（推奨）

```bash
viralman                              # → http://localhost:8765
```

4 ステップ:

1. **プロジェクト** — 名前、URL、一言ピッチ、詳細。
2. **生成** — チャンネル（X / Reddit / Gitmail）を選んで下書きを取得。
3. **ターゲット** — サブレディット、ハッシュタグ、コメント先、受信者リスト。全部自動提案。
4. **送信** — 確認してリアルタイム進捗。

### スラッシュコマンド

```bash
/viral OSS で作った K8s autoscaler が本番コストを 3 週間で 47% 削減
/viral --mode casual-hype "人生で最高にエグい race condition を倒した"
/viral --only reddit,x "この go regex ライブラリに r/programming のフィードバックが欲しい"

/dashboard                                       # Web UI
/gitmail https://github.com/you/jvm-monitor
```

### gitmail — 5 ステップ対話フロー（CLI またはスラッシュ）

スラッシュ 1 つで完結:

```bash
/gitmail https://github.com/you/jvm-monitor
```

5 ステップでガイドされます:
1. **ターゲット入力** — GitHub URL または自由記述
2. **トーン・強調入力** — "フレンドリーな開発者トーン"、"47% コスト削減を強調" のような自由入力
3. **受信者設定** — max_users + シードリポを直接指定、またはキーワード検索
4. **収集・確認** — 受信者プレビューで確認後、送信を承認
5. **下書き・送信** — dry-run プレビュー → 確定 → 実送信

CLI で直接 2 フェーズ実行する場合:

```bash
# Phase 1: 収集（シードリポを直接指定）
./scripts/gitmail.py recipients \
  --seed-repos jvm-profiling/async-profiler,oracle/graal \
  --max-users 100 \
  --provider claude \
  > recipients.json

# Phase 2: トーン・強調を反映した dry-run
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name jvm-monitor \
  --description "JVM monitoring SaaS" \
  --tone "フレンドリーな開発者、短く" \
  --emphasis "free, OSS, JVM monitoring" \
  --dry-run

# 確認後に実送信（--dry-run を外す）
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name jvm-monitor \
  --description "JVM monitoring SaaS" \
  --tone "フレンドリーな開発者、短く" \
  --emphasis "free, OSS, JVM monitoring"
```

### gitmail CLI（ワンショット）

```bash
./scripts/gitmail.py run \
  --description "Go 製の K8s autoscaler、コスト 47% 削減" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

`run` サブコマンドも同じ新フラグを受け付けます:

```bash
./scripts/gitmail.py run \
  --description "JVM monitoring SaaS" \
  --tone "casual" \
  --emphasis "free, OSS" \
  --seed-repos jvm-profiling/async-profiler \
  --max-users 100 \
  --dry-run
```

### 新フラグ

- `--tone "..."` — メールトーンの自由入力（"フレンドリーな開発者"、"技術的詳細"、"簡潔に"）
- `--emphasis "..."` — 強調点の自由入力（"47% コスト削減"、"free, OSS"）
- `--seed-repos owner/repo,...` — 検索ステップをスキップ、これらのリポの stargazer を直接収集
- `--keywords k1,k2` — 自動分析の代わりに指定キーワードで検索
- `--topics t1,t2` — topics オーバーライド

すべてのメールにワンクリック解除リンクと `List-Unsubscribe` ヘッダー付き。SMTP は毎分 30 通がデフォルト（`SMTP_RATE_PER_MIN` で変更可）。

## 「AI っぽくない」仕組み

`ai-tell-sniffer` が全下書きをチェック。禁止表現（"delve", "leverage", "let's dive in", "supercharge" など 20+）、60 語あたり em-dash が 1 個超、整いすぎた三項列挙、締めの説教、ハッシュタグ詰め込み、アンカーなしの一般論（数字 / 固有名 / 時刻 / 不確実性のいずれか必須）。最大 3 回リライト、それでも残れば自動配信拒否。

韓国語出力にも 12 種のパターン（활용하여 / 결론적으로 / "X 아니라 Y" 形式など）の検出、モラライザー検知、em-dash 密度チェックが適用されます。

すべての送信経路（ダッシュボード、CLI スラッシュコマンド、直接スクリプト）は同じ退会ログを共有します。一度退会したアドレスは次のキャンペーンで自動的にスキップされます — どの経路でもポリシーは一貫しています。

## ステータス

181 件のリグレッションテストで動作とポリシーを保護（Flask ルート、AI-tell 英/韓、OAuth、MIME RFC、i18n パリティ、退会一貫性、5 ステップユーザーストーリー）。

v0.3.0 — 5 ステップ対話式 gitmail フロー + `/viralman-setup` 統合認証情報入力 + `--tone` / `--emphasis` / `--seed-repos` フラグ。ローカルダッシュボードと v0.1.0 の `/viral` は変更なし。

## コントリビュート

[`CONTRIBUTING.md`](CONTRIBUTING.md) と [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) を参照。セキュリティ報告は [`SECURITY.md`](SECURITY.md)。

## ライセンス

MIT。
