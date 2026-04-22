---
name: tech-summary
description: 当需要对采集的技术内容进行深度分析总结时使用此技能
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# 技术内容深度分析总结技能

对采集的原始技术内容（GitHub Trending 项目、Hacker News 文章等）进行逐条深度分析、评分和趋势发现，输出结构化分析结果供分发和存档使用。

## 使用场景

- 对当日采集的 GitHub Trending 项目进行技术分析评分
- 对 Hacker News 热门技术文章进行深度解读
- 发现多个项目/文章之间的共同主题和趋势
- 为分发 Agent 提供经过评分和排序的高质量内容

## 执行步骤

### 步骤 1：读取最新采集数据

读取 `knowledge/raw/` 目录下最新的采集文件。

**查找规则**：

- 优先读取当天文件（文件名匹配当前日期 YYYY-MM-DD）
- 无当天文件时，读取最近修改的采集文件
- 支持的数据源目录：
  - `knowledge/raw/` — Trending 采集数据
- 文件格式为 JSON，结构为 `{ source, skill, collected_at, items[] }`

**读取后验证**：

- 确认 `items` 数组非空
- 确认每个 item 包含 `name`、`url`、`summary`、`stars` 等必要字段
- 数据不完整时记录警告，跳过异常 item 继续处理其余

### 步骤 2：逐条深度分析

对每个 item 执行以下 4 项分析：

#### 2a. 撰写精炼摘要（≤50 字）

用一句话概括项目的核心价值，控制在 50 字以内。

**公式**：`{项目名}：{做什么}`

**示例**：

```
langchain-ai/langchain：LLM 应用开发框架，支持链式调用与 Agent 编排。
```

#### 2b. 提取技术亮点（2-3 个，用事实说话）

基于项目 README、文档和代码特征提取客观事实，禁止模糊描述。

**要求**：

- 每个亮点必须包含**具体数字**或**可验证的事实**
- 格式：`{具体事实}，{为什么重要}`
- 数量严格 2-3 个

**示例**：

```
- 支持 50+ 种 LLM 模型接入，覆盖 OpenAI、Anthropic、开源模型等主流服务商
- 内置 10+ 种 RAG 检索策略，包括向量搜索、混合搜索和重排序
- 社区贡献者超 3000 人，周下载量突破 500 万次
```

#### 2c. 评分（1-10，附理由）

**评分标准**：

| 分数 | 评级          | 说明                                  |
| ---- | ------------- | ------------------------------------- |
| 9-10 | ⭐ 改变格局   | 开创性工作，可能重塑技术栈或行业方向  |
| 7-8  | 👍 直接有帮助 | 解决实际问题，立即可用的好工具/好思路 |
| 5-6  | 👀 值得了解   | 有一定价值，但需要持续观察            |
| 1-4  | ⏭ 可略过      | 同质化严重、尚不成熟或与主题关联度低  |

**评分要求**：

- 必须附评分理由（1-2 句话）
- 理由要具体，不能泛泛而谈
- 15 个项目中 9-10 分**不超过 2 个**
- 分数分布应呈金字塔形：低分多、高分少

**示例**：

```
评分: 8/10
理由: 相比竞品在推理速度上有 3 倍提升，且提供了完善的 Python 和 JS SDK，生产环境部署门槛低。
```

#### 2d. 建议标签（2-4 个）

从以下分类中选择标签：

**类别标签**：

- `framework` / `library` / `tool` / `paper` / `tutorial` / `platform`

**技术领域标签**：

- `llm` / `agent` / `rag` / `fine-tuning` / `inference` / `training`
- `multimodal` / `vision` / `nlp` / `code-generation` / `data-processing`
- `deployment` / `monitoring` / `evaluation` / `prompt-engineering`

### 步骤 3：趋势发现

对所有 item 分析完成后，从以下维度识别当日趋势：

#### 3a. 共同主题

分析多个项目/文章之间存在的共同技术主题。

**方法**：

- 统计标签出现频率
- 识别关键词聚类（如多个项目同时关注 Agent 框架）
- 对比历史数据判断是持续趋势还是新热点

**输出示例**：

```
- **Agent 框架持续爆发**：今日 6 个项目与 Agent 编排相关，较上周增长 50%
- **多模态推理升温**：3 个新项目聚焦视觉语言模型的应用落地
```

#### 3b. 新概念

识别首次出现或近期显著增长的技术概念。

**方法**：

- 对比过往分析结果中的标签和关键词
- 关注近期 stars 增长异常的新项目
- 识别可能代表下一波技术方向的新范式

**输出示例**：

```
- **MCP (Model Context Protocol)** 首次出现在 2 个项目中，作为一种标准化 LLM 工具调用协议值得关注
```

#### 3c. 整体评估

一句话总结当日采集内容的整体质量。

**输出示例**：

```
今日采集内容整体质量较高，Agent 和推理优化方向尤为突出。
```

### 步骤 4：输出分析结果 JSON

将分析结果写入 `knowledge/articles/pending/` 目录，文件名格式为：

```
knowledge/articles/pending/tech-summary-YYYY-MM-DD.json
```

**JSON 结构**：

```json
{
  "source": "tech_summary",
  "skill": "tech-summary",
  "analyzed_at": "2026-04-22T10:00:00+08:00",
  "raw_file": "knowledge/raw/github-trending-2026-04-22.json",
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "LLM 应用开发框架，支持链式调用与 Agent 编排。",
      "highlights": [
        "支持 50+ 种 LLM 模型接入，覆盖 OpenAI、Anthropic 等主流服务商",
        "内置 10+ 种 RAG 检索策略，包括向量搜索和重排序"
      ],
      "score": 8,
      "score_label": "directly_helpful",
      "score_reason": "相比竞品在推理速度上有 3 倍提升，生产部署门槛低。",
      "tags": ["framework", "llm", "agent", "rag"],
      "original_stars": 95000,
      "original_language": "Python"
    }
  ],
  "trends": {
    "common_themes": ["Agent 框架持续爆发：今日 6 个项目与 Agent 编排相关"],
    "new_concepts": ["MCP (Model Context Protocol) 首次出现在 2 个项目中"],
    "overall_assessment": "今日采集内容整体质量较高，Agent 和推理优化方向尤为突出。"
  },
  "summary": {
    "total_items": 15,
    "high_score_count": 1,
    "medium_score_count": 8,
    "low_score_count": 6,
    "top_tags": ["agent", "llm", "rag", "inference"]
  }
}
```

**字段说明**：

| 字段                         | 类型     | 说明                                                                      |
| ---------------------------- | -------- | ------------------------------------------------------------------------- |
| `source`                     | string   | 固定值 `tech_summary`                                                     |
| `skill`                      | string   | 固定值 `tech-summary`                                                     |
| `analyzed_at`                | string   | ISO 8601 格式分析完成时间戳                                               |
| `raw_file`                   | string   | 对应的原始采集文件路径                                                    |
| `items[].name`               | string   | 项目/文章名称                                                             |
| `items[].url`                | string   | 原始链接                                                                  |
| `items[].summary`            | string   | 精炼摘要，≤50 字                                                          |
| `items[].highlights`         | string[] | 技术亮点列表，2-3 个，每个包含具体事实                                    |
| `items[].score`              | number   | 评分 1-10                                                                 |
| `items[].score_label`        | string   | 评分等级：`game_changing` / `directly_helpful` / `worth_knowing` / `skip` |
| `items[].score_reason`       | string   | 评分理由，1-2 句话                                                        |
| `items[].tags`               | string[] | 标签列表，2-4 个                                                          |
| `items[].original_stars`     | number   | 原始 stars 数据（如适用）                                                 |
| `items[].original_language`  | string   | 原始编程语言（如适用）                                                    |
| `trends.common_themes`       | string[] | 共同主题列表                                                              |
| `trends.new_concepts`        | string[] | 新概念列表                                                                |
| `trends.overall_assessment`  | string   | 整体评估一句话                                                            |
| `summary.total_items`        | number   | 分析项目总数                                                              |
| `summary.high_score_count`   | number   | 高分（9-10）项目数                                                        |
| `summary.medium_score_count` | number   | 中分（5-8）项目数                                                         |
| `summary.low_score_count`    | number   | 低分（1-4）项目数                                                         |
| `summary.top_tags`           | string[] | 出现频率最高的标签                                                        |

## 评分标准

| 分数 | 评级          | 标签值             | 说明                                  |
| ---- | ------------- | ------------------ | ------------------------------------- |
| 9-10 | ⭐ 改变格局   | `game_changing`    | 开创性工作，可能重塑技术栈或行业方向  |
| 7-8  | 👍 直接有帮助 | `directly_helpful` | 解决实际问题，立即可用的好工具/好思路 |
| 5-6  | 👀 值得了解   | `worth_knowing`    | 有一定价值，但需要持续观察            |
| 1-4  | ⏭ 可略过      | `skip`             | 同质化严重、尚不成熟或与主题关联度低  |

## 注意事项

### 评分纪律

- 15 个项目中 9-10 分**不超过 2 个**
- 评分分布呈金字塔形：1-4 分占比最多，5-6 分次之，7-8 分再次，9-10 分最少
- 每个评分必须附具体理由，禁止无理由评分
- 禁止为了凑分布而人为调分，基于事实客观评分

### 摘要规范

- 摘要严格 ≤50 字
- 使用中文
- 禁止评价性语言（"很好"、"不错"、"值得关注"等），只陈述事实

### 技术亮点要求

- 每个亮点必须包含**具体数字**或**可验证的客观事实**
- 禁止模糊描述（如"性能很好"、"社区活跃" → 改为"推理速度提升 3 倍"、"GitHub stars 破万"）
- 亮点来源应为项目 README、官方文档或可公开获取的数据
- 不确定的数据不要编造，标注"数据待核实"

### 趋势发现

- 共同主题至少识别 1 条，最多 3 条
- 无新概念时，`new_concepts` 数组保留空数组 `[]`
- 整体评估必须有实质内容，不要写"无特别发现"

### 输出规范

- JSON 使用 UTF-8 编码，2 空格缩进
- 字段顺序保持与模板一致
- `items` 数组中的项目顺序按评分降序排列（高分在前）
- 同分项目按 `original_stars` 降序排列

## 输出格式

### 标准输出

```json
{
  "source": "tech_summary",
  "skill": "tech-summary",
  "analyzed_at": "2026-04-22T10:00:00+08:00",
  "raw_file": "knowledge/raw/github-trending-2026-04-22.json",
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "LLM 应用开发框架，支持链式调用与 Agent 编排。",
      "highlights": [
        "支持 50+ 种 LLM 模型接入，覆盖 OpenAI、Anthropic 等主流服务商",
        "内置 10+ 种 RAG 检索策略，包括向量搜索和重排序"
      ],
      "score": 8,
      "score_label": "directly_helpful",
      "score_reason": "相比竞品在推理速度上有 3 倍提升，生产部署门槛低。",
      "tags": ["framework", "llm", "agent", "rag"],
      "original_stars": 95000,
      "original_language": "Python"
    }
  ],
  "trends": {
    "common_themes": ["Agent 框架持续爆发：今日 6 个项目与 Agent 编排相关"],
    "new_concepts": [],
    "overall_assessment": "今日采集内容整体质量较高，Agent 和推理优化方向尤为突出。"
  },
  "summary": {
    "total_items": 15,
    "high_score_count": 1,
    "medium_score_count": 8,
    "low_score_count": 6,
    "top_tags": ["agent", "llm", "rag", "inference"]
  }
}
```

### 无分析结果输出

```json
{
  "source": "tech_summary",
  "skill": "tech-summary",
  "analyzed_at": "2026-04-22T10:00:00+08:00",
  "raw_file": "",
  "items": [],
  "trends": {
    "common_themes": [],
    "new_concepts": [],
    "overall_assessment": "当日无可用采集数据。"
  },
  "summary": {
    "total_items": 0,
    "high_score_count": 0,
    "medium_score_count": 0,
    "low_score_count": 0,
    "top_tags": []
  }
}
```
