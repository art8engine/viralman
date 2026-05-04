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

OSS メンテナー向けのローカルダッシュボード + マルチプラットフォーム投稿 + ターゲットアウトリーチ。プロジェクトの説明を一度書けば、各プラットフォーム用の下書きと送信先リストが揃う。配信は確認後だけ。

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

必要なものだけ:

```
/viralman-login-reddit       # 約 3 分、無料
/viralman-login-twitter      # 約 5 分、無料枠（月 ~1,500 投稿）
/viralman-login-linkedin     # 約 10 分、OAuth + 60 日トークンリフレッシュ
/viralman-login-gitmail      # 約 5 分、GitHub トークン + SMTP + LLM API キー 1 つ
```

秘密値は LLM コンテキストに入らない。`read -s` で直接 `~/.viralman/.env`（`chmod 600`）へ。

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
/gitmail "Go 製 K8s autoscaler" --max-users 100 --dry-run
```

### gitmail CLI

```bash
./scripts/gitmail.py run \
  --description "Go 製の K8s autoscaler、コスト 47% 削減" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

すべてのメールにワンクリック解除リンクと `List-Unsubscribe` ヘッダー付き。SMTP は毎分 30 通がデフォルト（`SMTP_RATE_PER_MIN` で変更可）。

## 「AI っぽくない」仕組み

`ai-tell-sniffer` が全下書きをチェック。禁止表現（"delve", "leverage", "let's dive in", "supercharge" など 20+）、60 語あたり em-dash が 1 個超、整いすぎた三項列挙、締めの説教、ハッシュタグ詰め込み、アンカーなしの一般論（数字 / 固有名 / 時刻 / 不確実性のいずれか必須）。最大 3 回リライト、それでも残れば自動配信拒否。

## ステータス

v0.2.0 — ローカルダッシュボード + gitmail アウトリーチ + OAuth ログイン。v0.1.0 の `/viral` は変更なし。

## コントリビュート

[`CONTRIBUTING.md`](CONTRIBUTING.md) と [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) を参照。セキュリティ報告は [`SECURITY.md`](SECURITY.md)。

## ライセンス

MIT。
