<h1 align="center">viralman</h1>

<p align="center">
  <b>你写代码，我让它出圈。</b><br>
  你只管造，推广交给 viralman。
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.zh.md"><b>中文</b></a> ·
  <a href="README.ja.md">日本語</a>
</p>

<p align="center">
  <img src="assets/viralman.png" alt="viralman" width="520">
</p>

---

把你的项目描述丢进来，viralman 帮你起草 Twitter/X 推文、Reddit 帖子，以及发给在 GitHub 上 star 过同类项目的开发者的冷邮件。不管是开源项目还是个人副业都行。确认之后才发出去。

```bash
viralman                 # 自动打开 http://localhost:8765
```

## 主要功能

- **多平台草稿** —— `/viral` 一句意图同时生成 Reddit / X / LinkedIn 草稿，读起来不像 AI。
- **本地 dashboard** —— 黑色风格 4 步向导：项目 → 生成 → 目标 → 发送。登录入口顶部统一。
- **gitmail 外联** —— 在 GitHub 找到和你最像的仓库，遍历其 stargazer，给每人发一封简短个性化邮件。最多 1 万收件人，自带一键退订。
- **AI 痕迹 sniffer** —— 约 30 条规则扫描每份草稿：陈词滥调、em-dash 滥用、平衡三段式、缺锚点。最多 3 轮重写，仍标红就拒绝自动发布。
- **OAuth 或手动** —— dashboard 登录 X / Reddit / LinkedIn，或粘贴 token。密码永远不进 LLM 上下文。
- **多 LLM** —— Claude / OpenAI / Gemini 任选，按已存的 API key 自动识别。

## 适用场景

- **v1.0 发布** —— 写明上线了什么，立刻拿到 r/programming 的 Reddit 帖子、X 串文、LinkedIn 公告，加一份星过同类工具的开发者名单。
- **副业项目宣告** —— 不必给三个平台各写一遍。一次输入 → 多渠道。
- **不知道该在哪儿发** —— viralman 用项目关键词抓取并推荐合适的子版块、hashtag 和最近可以评论的帖子。
- **重新激活同类工具的老 stargazer** —— gitmail 用公开 profile 和 commit 邮箱建名单，开场白会提到对方点过星的仓库。
- **躲开 AI 味** —— 大多数 "AI 社交发帖工具" 一眼就被识破。Sniffer 是 viralman 的核心差异点。

## 安装

### 作为 Claude Code 插件

```bash
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

### 作为 CLI

```bash
git clone https://github.com/art8engine/viralman
cd viralman
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/pip install -e .

# 写一行 shim，让 viralman 在任何路径都能跑
mkdir -p ~/.local/bin
cat > ~/.local/bin/viralman <<'SH'
#!/usr/bin/env bash
exec "$HOME/path/to/viralman/.venv/bin/python" "$HOME/path/to/viralman/bin/viralman" "$@"
SH
chmod +x ~/.local/bin/viralman
```

> **Python 3.14**：setuptools 的 editable install 依赖可执行 `.pth` 文件，3.14 已禁用。3.14+ 推荐用上面的 shim。

### 凭证（一次性）

按需运行：

```
/viralman-login-reddit       # 约 3 分钟，免费
/viralman-login-twitter      # 约 5 分钟，免费档（约 1,500 帖/月）
/viralman-login-linkedin     # 约 10 分钟，OAuth + 60 天令牌刷新
/viralman-login-gitmail      # 约 5 分钟，GitHub 令牌 + SMTP + 一个 LLM API key
```

不想配 API key 也行：装了 **Claude Code**，viralman 会自动检测本地的 `claude` 二进制，把 LLM 调用走它（用你 Claude Max plan 的额度）。dashboard 里把 provider 选成 `claude (Max via CLI)` 即可。

密码不进 LLM 上下文。脚本通过 `read -s` 直接管道写入 `~/.viralman/.env`（`chmod 600`）。

## 用法

### Dashboard（推荐）

```bash
viralman                              # → http://localhost:8765
```

4 步：

1. **项目** —— 名称、URL、一句话定位、详细描述。
2. **生成** —— 选频道（X / Reddit / Gitmail），拿草稿。
3. **目标** —— 选子版块、hashtag、可评论的帖子、收件人名单。全部自动建议。
4. **发送** —— 确认，看实时进度。

### 斜杠命令

```bash
/viral 我们开源的 K8s 自动伸缩器三周内把生产账单砍了 47%
/viral --mode casual-hype "刚搞定这辈子最难的 race condition"
/viral --only reddit,x "想要 r/programming 对这个 go regex 库的反馈"

/dashboard                                       # 网页 UI
/gitmail "Go 写的 K8s autoscaler" --max-users 100 --dry-run
```

### gitmail CLI

```bash
./scripts/gitmail.py run \
  --description "用 Go 写的 K8s 自动伸缩器，可降本 47%" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

每封邮件自带一键退订链接和 `List-Unsubscribe` 头。SMTP 默认 30 封/分钟（`SMTP_RATE_PER_MIN` 可调）。

## "看起来不像 AI" 是怎么做到的

`ai-tell-sniffer` 对每份草稿运行：禁用词（"delve", "leverage", "let's dive in", "supercharge" 等 20+），每 60 字超过 1 个 em-dash，平衡式三段列举，结尾说教，hashtag 堆砌，没有具体锚点（数字/名称/时间/自我承认）的泛泛而谈。最多 3 轮重写，仍标红就拒绝自动发布。

## 状态

v0.2.0 —— 本地 dashboard + gitmail 外联 + OAuth 登录。v0.1.0 的 `/viral` 流程未变。

## 贡献

见 [`CONTRIBUTING.md`](CONTRIBUTING.md) 和 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。安全问题：[`SECURITY.md`](SECURITY.md)。

## 协议

MIT。
