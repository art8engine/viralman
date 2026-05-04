<p align="center">
  <img src="assets/viralman.png" alt="viralman" width="520">
</p>

<h1 align="center">viralman</h1>

<p align="center">
  <b>你写代码，我让它出圈。</b><br>
  你只管造 — 推广交给 viralman。
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.zh.md"><b>中文</b></a> ·
  <a href="README.ja.md">日本語</a>
</p>

---

为开源维护者打造的本地仪表盘 + 多平台发布器 + 精准外联工具。一句话告诉 viralman 你想推什么，它会生成不像 AI 写的、贴合每个平台口吻的草稿，然后用你自己的账号发出去 —— 当然，是在你点确认之后。

```bash
viralman                 # 自动在浏览器打开 http://localhost:8765
```

> 帮我把这件事做火：我们团队的开源 K8s 自动伸缩器把成本砍了 47%

三个平台同时出三份草稿，每份都不像 AI slop，发布前还会再确认一次。

## viralman 做什么

| | 内容 |
|---|---|
| **`/viral`** | 一句话意图 → **Reddit / X / LinkedIn** 各自的版本。AI 痕迹嗅探器用约 30 条规则反复打磨，直到读起来不像聊天机器人。 |
| **`viralman`** | 本地仪表盘 (`http://localhost:8765`)。三个页面 —— twitter / reddit / gitmail，顶部一键切换。每个平台都支持 OAuth 登录。 |
| **`/gitmail`** | 描述你的项目。viralman 在 GitHub 上找到最相似的仓库，遍历点过星的用户，提取公开邮箱，然后用 Claude / GPT / Gemini（你选）写一封简短个性化的邮件发出去。一键退订自动嵌入。 |
| 安全 | 默认始终确认。嗅探器可拒绝发布。每次发送都有限流。密码经 `read -s` 直送磁盘，永远不进 LLM 上下文。 |

## 仪表盘

三个页面，黑色主题，顶部切换。

- **Twitter** — 输入草稿，字数和嗅探器告警实时更新。API 发布或退回到 compose URL。
- **Reddit** — 子版块 + 标题 + flair + 正文。专门检查 Reddit 上特别招黑的问题（禁用 hashtag、必须有具体锚点等）。
- **gitmail** — 拖动滑块（1 到 10,000 个目标用户），选 LLM 提供商，点开始。实时进度：分析 → 搜索仓库 → 收集邮箱 → 写信 → 发送。每封信都可单独预览。

## "看起来不像 AI 写的" 是怎么做到的

`ai-tell-sniffer` 代理对每份草稿运行：

- 禁用词 —— "delve", "tapestry", "leverage", "navigate the landscape", "let's dive in", "supercharge", 共约 20 多条。
- 每 60 字超过 1 个 em-dash。
- 三段平衡式罗列。结尾说教。Hashtag 堆砌。
- 没有具体锚点的泛泛而谈 —— 每份草稿必须含数字、名词、时间锚或自我承认。

最多三轮重写。还过不了就把最干净的那版连同警告一起给你 —— 不会自动发送有未消除标记的草稿。

## 安装

### 作为 Claude Code 插件

```bash
claude plugin marketplace add https://github.com/art8engine/viralman
claude plugin install viralman
```

### 作为 CLI（让你在终端里直接敲 `viralman`）

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

> **注意 —— Python 3.14**：setuptools 的 editable install 依赖可执行 `.pth` 文件，3.14 已禁用。3.14+ 推荐用上面的 shim 方案。

### 凭证（一次性，按平台）

按需运行：

```
/viralman-login-reddit       # 约 3 分钟，免费
/viralman-login-twitter      # 约 5 分钟，免费档位（约 1,500 帖/月）
/viralman-login-linkedin     # 约 10 分钟，OAuth + 60 天令牌刷新
/viralman-login-gitmail      # 约 5 分钟，GitHub 令牌 + SMTP + 一个 LLM API key
```

**密码永远不进 LLM 上下文** —— 脚本通过 `read -s` 直接管道写入存储工具。最终凭证落在 `~/.viralman/.env`，权限 `chmod 600`。

## 用法

### 写草稿 + 发布

```bash
# 默认：三个平台，growth-story 模式，发布前确认
/viral 我们的开源 K8s 自动伸缩器三周内把生产账单砍了 47%

# 指定模式
/viral --mode casual-hype "刚解掉这辈子最难的 race condition"

# 指定目标
/viral --only reddit,x "想要 r/programming 对这个 go regex 库的反馈"

# 中文输出（暂未支持，本工具默认输出英语 / 韩语）
```

### 仪表盘

```bash
viralman                              # → http://localhost:8765
viralman --port 9000 --no-browser
```

### gitmail 外联

```bash
./scripts/gitmail.py run \
  --description "用 Go 写的 K8s 自动伸缩器，可降本 47%" \
  --project-name k8s-autoscaler \
  --project-url https://github.com/you/k8s-autoscaler \
  --max-users 100 \
  --provider claude \
  --dry-run
```

每封邮件都自带一键退订链接和 `List-Unsubscribe` 头。SMTP 默认 30 封/分钟（可通过 `SMTP_RATE_PER_MIN` 调整）。

## 仓库结构

```
viralman/
├── bin/viralman                    # `viralman` CLI 入口 → 启动仪表盘
├── pyproject.toml                  # `pip install -e .` 注册命令
├── viralman_cli/                   # console-script 包
├── dashboard/                      # Flask 应用（server, api, oauth, 模板, 静态）
├── commands/                       # /viral, /dashboard, /gitmail
├── skills/                         # viral, dashboard, gitmail, viralman-login-*
├── agents/                         # viral-writer, ai-tell-sniffer, publisher
├── voice/                          # ai-tells, 平台规范, 模式模板, 参考语料
├── scripts/                        # post_*.py, gitmail.py, dashboard.py, save_creds.py
│   └── lib/                        # creds, sniffer_check, github_search, llm_compose, smtp_send
├── tests/                          # 嗅探器 + gitmail 测试
├── examples/                       # 端到端实录
└── assets/                         # README 配图
```

## 状态

v0.2.0 —— 本地仪表盘 + gitmail 外联 + OAuth 登录加入。v0.1.0 的 `/viral` 流程未变。

## 协议

MIT —— 随便 fork、内化、发布。
