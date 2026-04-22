---
name: github-trending
description: 当需要采集 GitHub 热门开源项目时使用此技能
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# GitHub Trending 采集技能

从 GitHub Trending 采集 AI/LLM/Agent 领域的优质开源项目，经智能过滤、去重和分析后，输出结构化 JSON 数据供后续处理使用。

## 使用场景

- 每日采集 GitHub Trending 上与 AI/LLM/Agent 相关的高质量开源项目
- 跟踪 AI 领域的最新开源动态和技术趋势
- 为知识库系统提供原始数据输入
- 生成面向开发者的技术资讯内容

## 执行步骤

### 步骤 1：搜索热门仓库

访问 GitHub Trending 页面，采集当日热门仓库列表。

```
https://github.com/trending
```

使用 `WebFetch` 工具抓取页面内容，或通过 `https://api.github.com/search/repositories` 按 stars 增长量排序搜索热门项目。

**搜索条件建议**：

- 语言：Python、TypeScript、Rust 等 AI 领域常见语言
- 时间范围：本周或本月
- 排序：按 stars 增长量降序

### 步骤 2：提取项目信息

对每个热门仓库提取以下信息：

| 字段          | 说明                     | 来源          |
| ------------- | ------------------------ | ------------- |
| `name`        | 仓库全名（owner/repo）   | 页面/API      |
| `url`         | 仓库 URL                 | 页面/API      |
| `description` | 项目描述                 | 页面/API      |
| `stars`       | 当前 stars 数量          | 页面/API      |
| `language`    | 主要编程语言             | 页面/API      |
| `topics`      | 项目标签列表             | 页面/API      |
| `daily_stars` | 今日新增 stars（如可用） | Trending 页面 |

### 步骤 3：过滤项目

应用以下过滤规则，保留符合条件的项目：

**纳入条件**（至少满足一项）：

- 项目描述或 topics 包含 `AI`、`LLM`、`Agent`、`RAG`、`Fine-tuning`、`Machine Learning`、`Deep Learning`、`NLP`、`Computer Vision`、`LangChain`、`GPT`、`Transformer` 等关键词
- 项目类型为框架、库、工具、论文实现、教程
- 与 AI 开发工作流相关（训练、部署、监控、数据处理等）

**排除条件**（满足任意一项即排除）：

- 项目名包含 `awesome-`、`awesome_` 前缀（Awesome 汇总列表）
- 纯教程/学习笔记类项目（无实质代码贡献）
- 非技术类项目
- 低质量或重复性项目（stars < 50 且无明显技术亮点）

### 步骤 4：去重

基于以下规则对项目去重：

- **主键**：`name`（仓库全名）
- 同一会话中多次采集到同一仓库时，只保留最新数据
- 与 `knowledge/raw/` 下已有数据重复时，更新 `stars` 等动态字段，保留历史分析记录
- 使用 URL 和内容哈希值辅助判断

### 步骤 5：撰写中文摘要

对每个过滤后的项目，撰写结构化的中文摘要。

**摘要公式**：

```
项目名 + 做什么 + 为什么值得关注
```

**模板**：

```markdown
- **{项目名}**：{一句话说明项目用途}。{为什么值得关注/核心亮点}。
```

**示例**：

```markdown
- **langchain-ai/langchain**：构建 LLM 应用的开发框架，提供链式调用、Agent 编排和 RAG 支持。近期新增了多模态模型集成能力，值得关注。
```

### 步骤 6：排序取 Top 15

按以下优先级综合排序，取前 15 个项目：

1. **相关性优先**：与 AI/LLM/Agent 核心主题最相关
2. **热度优先**：同等相关度下，stars 增长量更高者优先
3. **新颖性优先**：同等热度下，更新/发布时间更近者优先
4. **多样性优先**：尽量覆盖不同类别（框架、工具、论文、教程等）

### 步骤 7：输出 JSON 到知识库

将结果写入 `knowledge/raw/` 目录，文件名格式为：

```
knowledge/raw/github-trending-YYYY-MM-DD.json
```

**JSON 结构**：

```json
{
  "source": "github_trending",
  "skill": "github-trending",
  "collected_at": "2026-04-22T10:00:00+08:00",
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "构建 LLM 应用的开发框架，提供链式调用、Agent 编排和 RAG 支持。近期新增了多模态模型集成能力。",
      "stars": 95000,
      "language": "Python",
      "topics": ["llm", "agent", "langchain", "rag"]
    }
  ]
}
```

**字段说明**：

| 字段               | 类型     | 说明                               |
| ------------------ | -------- | ---------------------------------- |
| `source`           | string   | 固定值 `github_trending`           |
| `skill`            | string   | 固定值 `github-trending`           |
| `collected_at`     | string   | ISO 8601 格式采集时间戳            |
| `items[].name`     | string   | 仓库全名 `owner/repo`              |
| `items[].url`      | string   | 仓库完整 URL                       |
| `items[].summary`  | string   | 中文摘要（包含项目用途和核心亮点） |
| `items[].stars`    | number   | 当前 stars 数量                    |
| `items[].language` | string   | 主要编程语言                       |
| `items[].topics`   | string[] | 项目标签列表                       |

## 注意事项

### 速率限制

- GitHub API 未认证状态下限制 60 次请求/小时
- 建议配置 `GITHUB_TOKEN` 环境变量提升至 5000 次请求/小时
- 实现指数退避重试机制（首次等待 1s，后续翻倍，上限 60s）

### 数据质量

- 确保 summary 为中文且遵循摘要公式
- stars 数据为采集时刻快照，后续步骤不应修改
- topics 为空数组时保留空数组，不要省略字段
- 采集时间戳使用北京时间（UTC+8）

### 错误处理

- GitHub Trending 页面加载失败时，回退到 GitHub Search API
- 单仓库信息提取失败时，跳过该仓库并记录错误日志
- 输出文件写入失败时，保留内存中数据并重试

### 输出规范

- JSON 文件使用 UTF-8 编码
- 缩进使用 2 个空格
- 字段顺序保持与模板一致
- items 数组为空时输出 `[]`，不要省略字段

## 输出格式

### 标准输出

```json
{
  "source": "github_trending",
  "skill": "github-trending",
  "collected_at": "2026-04-22T10:00:00+08:00",
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "项目中文摘要。",
      "stars": 12345,
      "language": "Python",
      "topics": ["llm", "ai"]
    }
  ]
}
```

### 无结果输出

```json
{
  "source": "github_trending",
  "skill": "github-trending",
  "collected_at": "2026-04-22T10:00:00+08:00",
  "items": []
}
```
