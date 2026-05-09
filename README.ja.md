<h1 align="center">viralman</h1>

<p align="center">
  <b>コードはあなたが、バズはこちらが。</b><br>
  作るだけで大丈夫です。拡散は viralman にお任せください。
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

プロジェクトの説明をお渡しいただければ、Twitter/X 投稿、Reddit スレッド、そして GitHub で似たリポにスターした開発者へのコールドメールの下書きをまとめて出力いたします。OSS でも副業プロジェクトでも、どちらでもお使いいただけます。送信するかどうかはご自身で決めていただけます。

```bash
viralman                 # http://localhost:8765 が自動で開きます
```

## 機能

- **マルチプラットフォーム下書き** — `/viral` 一発で Reddit / X / LinkedIn 用の下書きを生成します。AI 臭はありません。
- **ローカルダッシュボード** — ダーク基調の 4 ステップです (プロジェクト → 生成 → ターゲット → 送信)。ログインは上部に統一されています。
- **gitmail アウトリーチ** — GitHub で似たリポを探し、スターしたユーザーに短い個別メールをお送りします。1 回最大 1,500 通(GraphQL のプロフィール一括取得 + REST PushEvent フォールバックで、GitHub の 2 つの独立した 5,000/hr バケットを併用)、ワンクリック解除リンクが自動付与されます。
- **Twitter リプライ候補** — `/twitter-reply` が最近の X ツイートから「これ作ったんで、ちょっと見てもらえます?」と返すのが自然な投稿を検索し、ダッシュボードの `/twitter-reply` ページにカード(本文 / 作者 / リンク / エンゲージ)として並べてご提示します。返信送信はツイートごとに明示的なご確認が必要です。
- **AI 痕跡スニファ** — 約 30 のヒューリスティクスでクリシェ、em-dash 過剰、整いすぎた三項列挙、アンカー欠落を検出します。最大 3 回リライト、それでも基準に達しない場合は自動配信を拒否します。
- **OAuth または手動** — ダッシュボードで X / Reddit / LinkedIn にログインしていただくか、トークンを直貼りいただけます。秘密値は LLM コンテキストには絶対に入りません。
- **マルチ LLM** — Claude / OpenAI / Gemini からお選びいただけます (保存済みキーで自動判別されます)。

## こんな時にお使いいただけます

- **v1.0 ローンチ** — 何をリリースしたかを書いていただければ、r/programming 向け Reddit 投稿、X スレッド、LinkedIn 告知、類似ツールにスターした開発者のアウトリーチリストまで一気にご用意いたします。
- **副業プロジェクトの告知** — 3 プラットフォーム用に書き分けていただく必要はありません。一度のご入力で全チャネルに対応いたします。
- **どこに投稿すべきか分からないとき** — viralman がキーワードからサブレディット、ハッシュタグ、コメントできる最近のスレッドをスクレイプしてご提案いたします。
- **類似ツールの古いスター持ちを再エンゲージ** — gitmail が公開プロフィールとコミットメールから受信者リストを作成し、相手がスターしたリポに触れる導入で個別化いたします。
- **AI スロップ回避** — 大半の「AI 投稿ツール」は一発で見抜かれます。スニファこそ viralman の差別化点です。

## インストール

3 つのパスをご用意しております。通常はパス 1、Claude Code をお使いでない場合はパス 2、CI / 自動化はパス 3 をお選びください。

> 以下の手動セットアップに従っていただいても構いませんが、Claude Code プラグイン(パス 1)をインストールしてエージェントにセットアップを手伝ってもらう方法をお勧めいたします。

### パス 1 — Claude Code プラグイン(推奨)

ほとんどの Claude Code ユーザーにお勧めする marketplace/plugin インストールです。下の 2 行は Claude Code のスラッシュコマンドですので、**1 行ずつ** ご入力ください(2 行を一度に貼り付けると失敗いたします):

```
/plugin marketplace add https://github.com/art8engine/viralman
```

続けて:

```
/plugin install viralman
```

リポジトリをローカルに clone 済みでしたら、URL の代わりに `./` もご使用いただけます:

```
/plugin marketplace add ./
```

インストール後はコマンドを覚えていただく必要はなく、`"ダッシュボードを開いて"`、`"viralman をセットアップして"`、`"async-profiler のスターガザーにメール"` のように自然言語で話しかけていただければ、エージェントが `/dashboard`、`/viralman-setup`、`/gitmail`、`/viral` のうち適切なものを発動いたします。送信直前には (1) 言語 (2) 件名スタイル (3) 最終確認 の順にご確認いただきます。

### パス 2 — pipx インストール(Claude Code 不要)

Claude Code なしでローカルダッシュボード + 素の CLI だけお使いになりたい場合:

```bash
pipx install git+https://github.com/art8engine/viralman
viralman   # → http://localhost:8765
```

`pipx` が独立した venv を作って `viralman` コマンドを `$PATH` に登録いたします。既存の venv をお使いの場合は `pip install git+...` でも同様にお使いいただけます。ダッシュボードの 4 タブ(Twitter / Reddit / Gitmail / Setup)で全作業が完結いたしますが、スラッシュコマンドは Claude Code が必要となります。

### パス 3 — clone して直接実行(CI / headless / 自動化)

スクリプトや CI パイプラインから明示的な引数で叩きたい場合:

```bash
git clone https://github.com/art8engine/viralman && cd viralman
pip install .
./scripts/gitmail.py run --description "..." --max-users 100 --dry-run
```

gitmail / viral の全フラグ一覧は下の [使用例](#使用例) をご参照ください。

## 使用例

### Block A — Claude Code の中で自然言語(パス 1 ユーザー)

そのまま言葉でお伝えください — エージェントが適切なスラッシュコマンドを自動で発動いたします:

```
"似たリポをスターした人にメールを送って"
"async-profiler をスターした人に JVM 監視ツールを紹介して"
"r/programming 向けの投稿を書いて、AI っぽくなく"
"ダッシュボードを開いて"
"viralman をセットアップして"
```

エージェントが `/gitmail`、`/viral`、`/dashboard`、`/viralman-setup` を自動で発動いたします。
送信直前に (1) 言語 (2) 件名スタイル (3) 最終確認 の順にご確認いただきます。

### Block B — スラッシュコマンドを直接入力(パス 1 パワーユーザー)

```
/viralman-setup gitmail
/gitmail https://github.com/myuser/myproj
/gitmail --seed-repos jvm-profiling/async-profiler --tone "フレンドリーな開発者" --emphasis "47% コスト削減"
/dashboard
/viral K8s autoscaler が 3 週間で本番コストを 47% 削減 --mode growth-story
```

### Block C — スクリプト直接呼び出し(パス 3 / CI / headless)

```bash
# 1) 認証情報を保存
read -rs -p 'GITHUB_TOKEN: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin GITHUB_TOKEN; unset s
./scripts/save_creds.py --set SMTP_HOST=smtp.gmail.com --set SMTP_PORT=587 --set SMTP_USER=you@gmail.com --set SMTP_FROM=you@gmail.com
read -rs -p 'SMTP_PASSWORD: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin SMTP_PASSWORD; unset s

# 2) 受信者を収集(シードリポを直接指定)
./scripts/gitmail.py recipients \
  --seed-repos jvm-profiling/async-profiler,oracle/graal \
  --max-users 100 > recipients.json

# 3) トーン・強調・件名スタイルを反映した dry-run — 送信前にご確認ください
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "フレンドリーな開発者、短く" \
  --emphasis "47% コスト削減" \
  --subject-style headline \
  --dry-run

# 4) ご確認後に --dry-run を外して再実行いただくと本送信となります
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "フレンドリーな開発者、短く" \
  --emphasis "47% コスト削減" \
  --subject-style headline
```

## メール送信例

### 韓国語自動生成(デフォルト)

オプションなしで呼び出していただくと、韓国語で生成されます(システムデフォルト):

```
SUBJECT: 안녕하세요, 이제 당신도 쉽게 사이드 프로젝트를 알릴 수 있습니다.

안녕하세요, 저희 오픈소스 viralman 도구를 알려드리고자 메일을 보냈습니다.

이제 당신은 본인의 사이드 프로젝트를 자연스럽게 알릴 수 있습니다.

AI가 프로젝트를 분석해 어울리는 홍보 멘트를 만들어주고, 관심을 가질 만한 개발자에게 메일 발송까지 도와드립니다.

당신의 사이드 프로젝트를 쉽게 바이럴 해보세요.

관심이 있다면 이 링크를 확인하세요: https://github.com/art8engine/viralman
```

### 英語(自然言語 `--tone "in English"` 経由)

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
/viralman-setup            # チャンネルをお選びいただき (gitmail / twitter / reddit / linkedin) 設定します
/viralman-setup gitmail    # gitmail ブランチへ直行いたします
/viralman-setup --check    # 保存済みキーの一覧をご確認いただけます
```

チャンネル別レガシーコマンド: `/viralman-login-reddit`(約 3 分)、`/viralman-login-twitter`(約 5 分)、`/viralman-login-linkedin`(約 10 分)、`/viralman-login-gitmail`(約 5 分)をお使いいただけます。

API キーがなくても動作いたします: **Claude Code** がインストールされていれば viralman がローカルの `claude` バイナリを自動検出し LLM 呼び出しを経由いたします(Claude Max plan クォータ)。ダッシュボードで `claude (Max via CLI)` をお選びください。

秘密値は LLM コンテキストには入りません — `read -s` で `~/.viralman/.env`(`chmod 600`)へ直接書き込まれます。

## 使い方

### ダッシュボード(推奨)

```bash
viralman                              # → http://localhost:8765
```

4 ステップでお進みいただけます:

1. **プロジェクト** — 名前、URL、一言ピッチ、詳細をご入力ください。
2. **生成** — チャンネル(X / Reddit / Gitmail)をお選びいただき、下書きを取得していただきます。
3. **ターゲット** — サブレディット、ハッシュタグ、コメント先、受信者リストを自動でご提案いたします。
4. **送信** — ご確認のうえ、リアルタイム進捗を表示いたします。

### スラッシュコマンド

```bash
/viral OSS で作った K8s autoscaler が本番コストを 3 週間で 47% 削減
/viral --mode casual-hype "人生で最高にエグい race condition を倒した"
/viral --only reddit,x "この go regex ライブラリに r/programming のフィードバックが欲しい"

/dashboard                                       # Web UI
/gitmail https://github.com/you/jvm-monitor
```

### gitmail — 5 ステップ対話フロー(CLI またはスラッシュ)

スラッシュ 1 つで完結いたします:

```bash
/gitmail https://github.com/you/jvm-monitor
```

5 ステップでガイドいたします:
1. **ターゲット入力** — GitHub URL または自由記述をお寄せください。
2. **トーン・強調入力** — 「フレンドリーな開発者トーン」、「47% コスト削減を強調」のような自由入力を承ります。
3. **受信者設定** — max_users + シードリポを直接ご指定いただくか、キーワード検索をお使いください。
4. **収集・確認** — 受信者プレビューでご確認のうえ、送信を承認していただきます。
5. **下書き・送信** — dry-run プレビュー → ご確定 → 実送信の順序で進行いたします。

CLI で直接 2 フェーズ実行なさる場合:

```bash
# Phase 1: 収集(シードリポを直接指定)
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

# ご確認後に実送信(--dry-run を外してください)
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name jvm-monitor \
  --description "JVM monitoring SaaS" \
  --tone "フレンドリーな開発者、短く" \
  --emphasis "free, OSS, JVM monitoring"
```

### gitmail CLI(ワンショット)

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

- `--tone "..."` — メールトーンの自由入力です(「フレンドリーな開発者」、「技術的詳細」、「簡潔に」)。
- `--emphasis "..."` — 強調点の自由入力です(「47% コスト削減」、「free, OSS」)。
- `--seed-repos owner/repo,...` — 検索ステップをスキップし、これらのリポの stargazer を直接収集いたします。
- `--keywords k1,k2` — 自動分析の代わりにご指定のキーワードで検索いたします。
- `--topics t1,t2` — topics をオーバーライドいたします。

すべてのメールにワンクリック解除リンクと `List-Unsubscribe` ヘッダーが付与されます。SMTP は毎分 30 通がデフォルトです(`SMTP_RATE_PER_MIN` で変更いただけます)。

## 「AI っぽくない」仕組み

`ai-tell-sniffer` が全下書きをチェックいたします。禁止表現(「delve」、「leverage」、「let's dive in」、「supercharge」など 20 余り)、60 語あたり em-dash が 1 個超、整いすぎた三項列挙、締めの説教、ハッシュタグ詰め込み、アンカーなしの一般論(数字 / 固有名 / 時刻 / 不確実性のいずれか必須)を検査いたします。最大 3 回リライト、それでも残れば自動配信を拒否いたします。

韓国語出力にも 12 種のパターン(활용하여 / 결론적으로 / 「X 아니라 Y」 形式など)の検出、モラライザー検知、em-dash 密度チェックが適用されます。

すべての送信経路(ダッシュボード、CLI スラッシュコマンド、直接スクリプト)は同じ退会ログを共有しております。一度退会されたアドレスは次のキャンペーンで自動的にスキップされます — どの経路でもポリシーは一貫しています。

## ステータス

181 件のリグレッションテストで動作とポリシーを保護しております(Flask ルート、AI-tell 英/韓、OAuth、MIME RFC、i18n パリティ、退会一貫性、5 ステップユーザーストーリー)。

v0.3.0 — 5 ステップ対話式 gitmail フロー + `/viralman-setup` 統合認証情報入力 + `--tone` / `--emphasis` / `--seed-repos` フラグが追加されました。ローカルダッシュボードと v0.1.0 の `/viral` は変更ございません。

## コントリビュート

[`CONTRIBUTING.md`](CONTRIBUTING.md) と [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) をご参照ください。セキュリティ報告は [`SECURITY.md`](SECURITY.md) よりお願いいたします。

## ライセンス

MIT。
