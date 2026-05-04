<p align="center">
  <img src="assets/viralman.png" alt="viralman" width="520">
</p>

<h1 align="center">viralman</h1>

<p align="center">
  <b>コードは君が、バズはこっちが。</b><br>
  作るだけでいい — 拡散は viralman の仕事だ。
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.zh.md">中文</a> ·
  <a href="README.ja.md"><b>日本語</b></a>
</p>

---

OSS メンテナーのためのローカルダッシュボード + マルチプラットフォーム投稿 + ターゲット型アウトリーチ。一行の意図を投げると、AI 臭くないプラットフォームごとの下書きを生成し、あなたのアカウントから配信する — 確認ボタンを押した後だけ。

```bash
viralman                 # ブラウザで http://localhost:8765 が自動的に開く
```

> このネタをバズらせて：チームで作った OSS の K8s autoscaler が本番コストを 47% 削減した

3 プラットフォーム分の下書きが同時に出る。AI スロップ感のない文体で、配信前にもう一度確認を求められる。

## viralman ができること

| | 内容 |
|---|---|
| **`/viral`** | 一行の意図 → **Reddit / X / LinkedIn** 別の下書き。AI 臭判定スニファが約 30 のヒューリスティクスでチャットボット臭を抜いていきます。 |
| **`viralman`** | ローカルダッシュボード (`http://localhost:8765`)。3 ページ — twitter / reddit / gitmail — ヘッダーから瞬時に切替。プラットフォームごとに OAuth ログイン。 |
| **`/gitmail`** | プロジェクトの説明を渡すと、GitHub で最も似たリポを見つけ、スター押した人を辿り、公開メールを抽出して、Claude / GPT / Gemini（お好みで）で短い個別メールを送ります。ワンクリック解除リンク自動付与。 |
| 安全 | デフォルトは常に確認。スニファが配信を拒否することも。送信ごとにレート制限。秘密値は `read -s` だけ、LLM コンテキストには絶対入りません。 |

## ダッシュボード

3 ページ、ダークテーマ、ヘッダーで切替。

- **Twitter** — 下書きを入力すると、文字数とスニファのフラグがリアルタイム更新。API 配信または compose URL フォールバック。
- **Reddit** — サブレディット + タイトル + フレア + 本文。Reddit 特有の地雷（ハッシュタグ禁止、アンカー必須など）を専用ルールでチェック。
- **gitmail** — スライダー（1〜10,000 名）、LLM プロバイダ選択、開始。リアルタイム進捗: analyse → リポ検索 → メール収集 → 文面作成 → 送信。受信者ごとのプレビュー。

## 「AI っぽくない」を実現する仕組み

`ai-tell-sniffer` エージェントが全下書きをチェック:

- 禁止表現 — "delve", "tapestry", "leverage", "navigate the landscape", "let's dive in", "supercharge", ほか約 20。
- 60 語あたり em-dash が 1 個を超える。
- バランスの取れた三項列挙。締めの説教。ハッシュタグ詰め込み。
- アンカーのない一般論 — 全下書きに数字 / 固有名 / 時刻アンカー / 不確実性の表明のいずれかが必須。

リライトは最大 3 回。それでもフラグが残るなら、最も綺麗なバージョンを警告つきで提示し — 自動配信は拒否します。

## インストール

### Claude Code プラグインとして

```bash
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

### CLI として（`viralman` 一語をシェルで使うため）

```bash
git clone https://github.com/art8engine/viralman
cd viralman
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/pip install -e .

# どこからでも viralman が動くように PATH に shim を 1 つ作る
mkdir -p ~/.local/bin
cat > ~/.local/bin/viralman <<'SH'
#!/usr/bin/env bash
exec "$HOME/path/to/viralman/.venv/bin/python" "$HOME/path/to/viralman/bin/viralman" "$@"
SH
chmod +x ~/.local/bin/viralman
```

> **注意 — Python 3.14**: setuptools の editable install が使う実行可能 `.pth` ファイルが Python 3.14 で無効化されました。3.14+ では上の shim 方式を推奨します。

### 認証情報（プラットフォームごとに 1 回）

必要なものだけ:

```
/viralman-login-reddit       # 約 3 分、無料
/viralman-login-twitter      # 約 5 分、無料枠（月 ~1,500 投稿）
/viralman-login-linkedin     # 約 10 分、OAuth + 60 日トークンリフレッシュ
/viralman-login-gitmail      # 約 5 分、GitHub トークン + SMTP + LLM API キー 1 つ
```

**秘密値は LLM コンテキストに絶対に入りません** — スキルが `read -s` で直接保存スクリプトにパイプするように案内します。認証情報は `~/.viralman/.env` に `chmod 600` で保存されます。

## 使い方

### 下書き作成 + 配信

```bash
# デフォルト: 3 プラットフォーム、growth-story モード、配信前に確認
/viral OSS で作った K8s autoscaler が本番コストを 3 週間で 47% 削減した

# モード指定
/viral --mode casual-hype "人生で最高にエグい race condition を倒した"

# 対象指定
/viral --only reddit,x "この go regex ライブラリに r/programming のフィードバックが欲しい"

# 言語指定（en / ko）
/viral --lang ko "..."
```

### ダッシュボード

```bash
viralman                              # → http://localhost:8765
viralman --port 9000 --no-browser
```

### gitmail アウトリーチ

```bash
./scripts/gitmail.py run \
  --description "Go 製の K8s autoscaler、コスト 47% 削減" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

すべてのメールにワンクリック解除リンクと `List-Unsubscribe` ヘッダーが付きます。SMTP はデフォルトで毎分 30 通制限（`SMTP_RATE_PER_MIN` で変更可）。

## リポジトリ構成

```
viralman/
├── bin/viralman                    # `viralman` CLI エントリ → ダッシュボード起動
├── pyproject.toml                  # `pip install -e .` でコマンド登録
├── viralman_cli/                   # console-script パッケージ
├── dashboard/                      # Flask アプリ（server, api, oauth, テンプレ, 静的）
├── commands/                       # /viral, /dashboard, /gitmail
├── skills/                         # viral, dashboard, gitmail, viralman-login-*
├── agents/                         # viral-writer, ai-tell-sniffer, publisher
├── voice/                          # ai-tells, プラットフォーム規範, モードテンプレ, 参考コーパス
├── scripts/                        # post_*.py, gitmail.py, dashboard.py, save_creds.py
│   └── lib/                        # creds, sniffer_check, github_search, llm_compose, smtp_send
├── tests/                          # スニファ + gitmail 作成テスト
├── examples/                       # エンドツーエンドの実例
└── assets/                         # README 用画像
```

## ステータス

v0.2.0 — ローカルダッシュボード + gitmail アウトリーチ + OAuth ログインを追加。v0.1.0 の `/viral` フローは変更なし。

## ライセンス

MIT — fork、ベンダリング、出荷、すべて自由。
