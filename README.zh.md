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
- **gitmail 外联** —— 在 GitHub 找到和你最像的仓库，遍历其 stargazer，给每人发一封简短个性化邮件。每次最多 1,500 收件人（GraphQL 批量获取 profile + REST PushEvent 兜底，同时利用 GitHub 两个独立的 5,000/hr 配额），自带一键退订。
- **Twitter 回复候选** —— `/twitter-reply` 搜索最近的 X 推文，找出适合用 "我做了这个，要不要看一下？" 来回复的对象，并把候选推到 dashboard `/twitter-reply` 页面，以卡片（正文 / 作者 / 链接 / 互动数）展示。回复需逐条显式确认。
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

三条路径。一般推荐路径 1；不使用 Claude Code 选路径 2；CI / 自动化选路径 3。

> 您可以按照下面的手动设置步骤完成配置，但更推荐安装 Claude Code 插件（路径 1），让智能体直接帮您完成所有设置。

### 路径 1 —— Claude Code 插件（推荐）

适合大多数 Claude Code 用户的 marketplace/plugin 安装方式。下面两行是 Claude Code 斜杠命令，请**逐行输入**（一次粘贴两行会失败）：

```
/plugin marketplace add https://github.com/art8engine/viralman
```

然后：

```
/plugin install viralman
```

如果已经把仓库克隆到本地，URL 可换成 `./`：

```
/plugin marketplace add ./
```

安装完成后，无需记任何命令——直接用自然语言说，例如 `"打开面板"`、`"配置 viralman"`、`"给 async-profiler 的 starrer 发邮件"`，代理会自动调用 `/dashboard`、`/viralman-setup`、`/gitmail`、`/viral`。发送前依次确认 (1) 语言 (2) 主题风格 (3) 最终确认。

### 路径 2 —— pipx 安装（无需 Claude Code）

如果只想用本地 Dashboard + 纯 CLI：

```bash
pipx install git+https://github.com/art8engine/viralman
viralman   # → http://localhost:8765
```

`pipx` 会创建独立 venv 并把 `viralman` 命令注入到 `$PATH`。已有 venv 则 `pip install git+...` 同样可用。Dashboard 4 个标签页（Twitter / Reddit / Gitmail / Setup）涵盖全部操作；斜杠命令需要 Claude Code。

### 路径 3 —— 克隆后直接运行（CI / headless / 自动化）

需要在脚本或 CI 流水线里用显式参数运行：

```bash
git clone https://github.com/art8engine/viralman && cd viralman
pip install .
./scripts/gitmail.py run --description "..." --max-users 100 --dry-run
```

完整的 gitmail / viral 参数请见下文 [使用](#使用示例) 章节。

## 使用示例

### Block A —— 在 Claude Code 里用自然语言（路径 1 用户）

直接说就行 —— 代理会自动选择正确的斜杠命令：

```
"帮我给 star 过类似项目的人发邮件"
"把我们的 JVM 监控工具介绍给 star 了 async-profiler 的人"
"帮我写一篇 r/programming 帖子，不要 AI 味"
"打开面板"
"配置 viralman"
```

代理自动触发 `/gitmail`、`/viral`、`/dashboard` 或 `/viralman-setup`。
发送前依次确认 (1) 语言 (2) 主题风格 (3) 最终确认。

### Block B —— 直接输入斜杠命令（路径 1 高级用户）

```
/viralman-setup gitmail
/gitmail https://github.com/myuser/myproj
/gitmail --seed-repos jvm-profiling/async-profiler --tone "友好的开发者" --emphasis "47% 降本"
/dashboard
/viral 我们的 K8s 自动伸缩器三周内把生产成本降了 47% --mode growth-story
```

### Block C —— 直接调用脚本（路径 3 / CI / headless）

```bash
# 1) 保存凭证
read -rs -p 'GITHUB_TOKEN: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin GITHUB_TOKEN; unset s
./scripts/save_creds.py --set SMTP_HOST=smtp.gmail.com --set SMTP_PORT=587 --set SMTP_USER=you@gmail.com --set SMTP_FROM=you@gmail.com
read -rs -p 'SMTP_PASSWORD: ' s && printf '%s' "$s" | ./scripts/save_creds.py --stdin SMTP_PASSWORD; unset s

# 2) 收集收件人（直接指定种子仓库）
./scripts/gitmail.py recipients \
  --seed-repos jvm-profiling/async-profiler,oracle/graal \
  --max-users 100 > recipients.json

# 3) 带语气·重点·主题风格的 dry-run —— 发送前审核
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "友好的开发者，简短" \
  --emphasis "47% 降本" \
  --subject-style headline \
  --dry-run

# 4) 审核通过后去掉 --dry-run 再次运行即实发
./scripts/gitmail.py send-from-recipients \
  --recipients-file recipients.json \
  --project-name myproj \
  --description "JVM monitoring SaaS" \
  --tone "友好的开发者，简短" \
  --emphasis "47% 降本" \
  --subject-style headline
```

## 邮件样例

### 韩语自动生成（默认）

不加任何选项调用时，默认生成韩语邮件（系统默认值）：

```
SUBJECT: 안녕하세요, 이제 당신도 쉽게 사이드 프로젝트를 알릴 수 있습니다.

안녕하세요, 저희 오픈소스 viralman 도구를 알려드리고자 메일을 보냈습니다.

이제 당신은 본인의 사이드 프로젝트를 자연스럽게 알릴 수 있습니다.

AI가 프로젝트를 분석해 어울리는 홍보 멘트를 만들어주고, 관심을 가질 만한 개발자에게 메일 발송까지 도와드립니다.

당신의 사이드 프로젝트를 쉽게 바이럴 해보세요.

관심이 있다면 이 링크를 확인하세요: https://github.com/art8engine/viralman
```

### 英语（通过自然语言 `--tone "in English"`）

Add `--tone "in English"` (or natural-language equivalents like `영어로 써줘` / `中文で`) to switch:

```
SUBJECT: Hi, now you can easily share your side project too.

Hi, we're reaching out to share our open-source project viralman.

Now you can easily get your own side project in front of the developers most likely to care about it.

The AI reads your repository, drafts a natural outreach note in your voice, and helps you deliver it to a relevant audience.

Try giving your side project the reach it deserves, without the awkward self-promotion.

If you're curious, here is the link: https://github.com/art8engine/viralman
```

## 凭证

```bash
/viralman-setup            # 选渠道 (gitmail / twitter / reddit / linkedin) 并配置
/viralman-setup gitmail    # 直接进入 gitmail 分支
/viralman-setup --check    # 查看已保存的 key
```

各渠道独立命令：`/viralman-login-reddit`（约 3 分钟）、`/viralman-login-twitter`（约 5 分钟）、`/viralman-login-linkedin`（约 10 分钟）、`/viralman-login-gitmail`（约 5 分钟）。

不配 API key 也行：装了 **Claude Code** 就自动走本地 `claude` 二进制（Claude Max plan 额度）。Dashboard 里选 `claude (Max via CLI)`。

密码不进 LLM 上下文 —— `read -s` 直接写入 `~/.viralman/.env`（`chmod 600`）。

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
