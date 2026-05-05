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

推荐 —— 一条命令选定渠道：

```bash
/viralman-setup                    # 选择类别 (gitmail / twitter / reddit / linkedin) → 只配置该渠道
/viralman-setup gitmail            # 直接进入 gitmail 分支
/viralman-setup --check            # 仅列出当前已保存的 key
```

传统方式 —— 单独配置某个渠道：

```bash
/viralman-login-reddit       # 约 3 分钟，免费
/viralman-login-twitter      # 约 5 分钟，免费档（约 1,500 帖/月）
/viralman-login-linkedin     # 约 10 分钟，OAuth + 60 天令牌刷新
/viralman-login-gitmail      # 约 5 分钟，GitHub 令牌 + SMTP + 一个 LLM API key
```

不想配 API key 也行：装了 **Claude Code**，viralman 会自动检测本地的 `claude` 二进制，把 LLM 调用走它（用你 Claude Max plan 的额度）。dashboard 里把 provider 选成 `claude (Max via CLI)` 即可。

密码不进 LLM 上下文。脚本通过 `read -s` 直接管道写入 `~/.viralman/.env`（`chmod 600`）。

## 直接告诉它（Claude Code 代理模式）

不必记命令。在 Claude Code 内，viralman 作为插件运行，技能会自动响应自然语言意图。说下面任何一句，代理就会做对应的事：

- *"安装 viralman"* / *"install viralman"* → 自助引导：必要时克隆仓库、建 .venv、装 flask + viralman、把 `viralman` shim 放进 PATH、验证 dashboard 能响应。幂等 — 重复运行安全。
- *"打开面板"* / *"open the dashboard"* → 在 `http://localhost:8765` 启动。还没装好就先 install，再启动。
- *"保存 viralman 凭证"* → 触发 `/viralman-setup`，只配置你需要的渠道。可以直接粘贴明文 token（会先警告），推荐 `read -s` 让密钥不进 LLM 上下文。
- *"给类似仓库的 stargazer 发邮件"* → 5 步互动 gitmail 流程：项目 → 语气/重点 → 种子仓库或关键词 → 收件人审查 → dry-run 预览 → 实发。
- *"写一条不像 AI 的推文"* → `viral-writer` 起草，`ai-tell-sniffer` 复核改写。

缺失输入只问一次。不可逆操作（实发邮件、OAuth 保存）需要明确同意。

如果你更喜欢直接打命令，每个自然语言意图都有对应的斜杠形式 — 见下方用法。

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
/gitmail https://github.com/you/jvm-monitor
```

### gitmail — 5 步交互流程（CLI 或斜杠）

一条斜杠命令搞定：

```bash
/gitmail https://github.com/you/jvm-monitor
```

系统将引导你完成 5 步：
1. **输入目标** —— GitHub URL 或自由描述
2. **输入语气·重点** —— 自由填写，如"友好的开发者语气"或"强调 47% 降本"
3. **设定收件人** —— 直接指定 max_users + 种子 repo，或按关键词搜索
4. **收集·审核** —— 预览收件人后确认发送
5. **起草·发送** —— dry-run 预览 → 确认 → 实际发送

如需直接从 CLI 跑 2-phase 流程：

```bash
# Phase 1：收集（直接指定种子 repo）
./scripts/gitmail.py recipients \
  --seed-repos jvm-profiling/async-profiler,oracle/graal \
  --max-users 100 \
  --provider claude \
  > recipients.json

# Phase 2：带语气·重点的 dry-run
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name jvm-monitor \
  --description "JVM monitoring SaaS" \
  --tone "友好的开发者，简短" \
  --emphasis "free, OSS, JVM monitoring" \
  --dry-run

# 审核后实际发送（去掉 --dry-run）
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name jvm-monitor \
  --description "JVM monitoring SaaS" \
  --tone "友好的开发者，简短" \
  --emphasis "free, OSS, JVM monitoring"
```

### gitmail CLI（一次性）

```bash
./scripts/gitmail.py run \
  --description "用 Go 写的 K8s 自动伸缩器，可降本 47%" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

`run` 子命令同样接受新参数：

```bash
./scripts/gitmail.py run \
  --description "JVM monitoring SaaS" \
  --tone "casual" \
  --emphasis "free, OSS" \
  --seed-repos jvm-profiling/async-profiler \
  --max-users 100 \
  --dry-run
```

### 新参数

- `--tone "..."` —— 邮件语气自由输入（"友好的开发者"、"技术细节"、"简洁"）
- `--emphasis "..."` —— 强调点自由输入（"47% 降本"、"free, OSS"）
- `--seed-repos owner/repo,...` —— 跳过搜索步骤，直接从这些 repo 的 stargazer 收集
- `--keywords k1,k2` —— 用指定关键词替代自动分析结果
- `--topics t1,t2` —— topics 覆盖

每封邮件自带一键退订链接和 `List-Unsubscribe` 头。SMTP 默认 30 封/分钟（`SMTP_RATE_PER_MIN` 可调）。

## "看起来不像 AI" 是怎么做到的

`ai-tell-sniffer` 对每份草稿运行：禁用词（"delve", "leverage", "let's dive in", "supercharge" 等 20+），每 60 字超过 1 个 em-dash，平衡式三段列举，结尾说教，hashtag 堆砌，没有具体锚点（数字/名称/时间/自我承认）的泛泛而谈。最多 3 轮重写，仍标红就拒绝自动发布。

韩语输出同样会检测 12 种模式（활용하여 / 결론적으로 / "X 아니라 Y" 等），以及说教检测和 em-dash 密度分析。

所有发送路径（dashboard、CLI 斜杠命令、直接脚本）共享同一份退订日志。某个地址一旦退订，后续所有活动都会自动跳过 —— 各路径策略保持一致。

## 状态

181 条回归测试守护行为与策略（Flask 路由、AI-tell 英/韩、OAuth、MIME RFC、i18n 一致性、退订一致性、5 步用户故事）。

v0.3.0 —— 5 步交互式 gitmail 流程 + `/viralman-setup` 统一凭证入口 + `--tone` / `--emphasis` / `--seed-repos` 参数。本地 dashboard 和 v0.1.0 的 `/viral` 流程未变。

## 贡献

见 [`CONTRIBUTING.md`](CONTRIBUTING.md) 和 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。安全问题：[`SECURITY.md`](SECURITY.md)。

## 协议

MIT。
