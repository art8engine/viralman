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

### Claude Code プラグインとして

```bash
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

### CLI として

```bash
git clone https://github.com/art8engine/viralman
cd viralman
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/pip install -e .

# どこからでも viralman が動くように PATH に shim を 1 つ
mkdir -p ~/.local/bin
cat > ~/.local/bin/viralman <<'SH'
#!/usr/bin/env bash
exec "$HOME/path/to/viralman/.venv/bin/python" "$HOME/path/to/viralman/bin/viralman" "$@"
SH
chmod +x ~/.local/bin/viralman
```

> **Python 3.14**: setuptools の editable install が使う実行可能 `.pth` ファイルが 3.14 で無効化された。3.14+ は上の shim 推奨。

### 認証情報（一度だけ）

推奨 — 1 コマンドでチャンネルを選ぶ:

```bash
/viralman-setup                    # カテゴリ選択 (gitmail / twitter / reddit / linkedin) → そのチャンネルだけ設定
/viralman-setup gitmail            # gitmail ブランチへ直行
/viralman-setup --check            # 現在保存済みのキー一覧だけ確認
```

レガシー — 1 チャンネルだけ個別に設定したい場合:

```bash
/viralman-login-reddit       # 約 3 分、無料
/viralman-login-twitter      # 約 5 分、無料枠（月 ~1,500 投稿）
/viralman-login-linkedin     # 約 10 分、OAuth + 60 日トークンリフレッシュ
/viralman-login-gitmail      # 約 5 分、GitHub トークン + SMTP + LLM API キー 1 つ
```

API キーなしでも動く: **Claude Code** が入っていれば viralman がローカルの `claude` バイナリを自動検出し、LLM 呼び出しをそちら経由にする (Claude Max plan のクォータがそのまま使える)。ダッシュボードで provider を `claude (Max via CLI)` に。

秘密値は LLM コンテキストに入らない。`read -s` で直接 `~/.viralman/.env`（`chmod 600`）へ。

## 自然な言葉で頼む（Claude Code エージェントモード）

コマンドを覚える必要はありません。Claude Code 内で viralman はプラグインとして動き、スキルが自然言語の意図に自動反応します。次のどれかを言えば、エージェントが正しく処理します:

- *"viralman をセットアップ"* / *"set up viralman"* / *"viralman をインストール"* / *"viralman の認証情報を保存"* → `/viralman-setup` が単一エントリポイント。Step 0 で viralman 本体が入っているか確認し、なければ自動でブートストラップ（クローン、.venv 作成、flask インストール、shim 配置、検証）。その後どのチャンネルを設定するか聞いて（gitmail / twitter / reddit / linkedin）、そのチャンネルだけ保存。平文トークン貼り付けも可能（警告あり）、推奨は `read -s` でシークレットを LLM コンテキストに残さない。
- *"ダッシュボード を 開いて"* / *"open the dashboard"* → `http://localhost:8765` を起動。インストールされていなければ自動で install を先に実行。
- *"似たリポジトリのスターガザーにメール"* → 5 ステップ対話型 gitmail フロー: 対象 → トーン・強調 → シードリポまたはキーワード → 受信者レビュー → dry-run プレビュー → 本送信。
- *"AI っぽくない 投稿 を 書いて"* → `viral-writer` が下書き、`ai-tell-sniffer` がレビュー＆リライト。

不足する入力は一度だけ聞きます。取り返しのつかない操作（本送信、OAuth 保存）は明示的な同意なしには進みません。

スラッシュコマンドを直接打ちたい場合は、各自然言語意図に対応するスラッシュ形式があります — 下の使い方を参照。

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
