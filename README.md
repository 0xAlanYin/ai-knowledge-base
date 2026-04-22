# AI Knowledge Base

一个智能化的 AI 知识库助手系统，能够自动从 GitHub Trending 和 Hacker News 等渠道采集 AI/LLM/Agent 领域的最新技术动态，通过 AI 分析进行结构化处理，并支持多渠道内容分发。

## ✨ 功能特性

### 📊 数据采集
- **GitHub Trending**: 自动采集 AI/LLM/Agent 相关的热门开源项目
- **Hacker News**: 实时监控 HN 首页和 /show 板块的技术动态
- **智能过滤**: 基于关键词（LLM, Agent, RAG, Fine-tuning 等）自动过滤
- **去重机制**: 基于 URL 和内容哈希值防止重复采集

### 🤖 AI 分析处理
- **内容理解**: 使用大模型理解技术内容的核心价值
- **自动分类**: 分类到框架、库、工具、论文、教程等类别
- **摘要生成**: 生成简洁明了的技术摘要（200-300字）
- **标签提取**: 自动提取相关技术标签
- **质量评分**: 评估相关性、新颖性、实用性

### 📤 多渠道分发
- **Telegram Bot**: 支持 Telegram 频道推送
- **飞书集成**: 支持飞书群组/频道推送
- **Webhook**: 通用 HTTP 通知接口
- **模板系统**: 支持 Markdown 和富文本模板

### 🔍 MCP 知识搜索
- **本地搜索**: 通过 MCP (Model Context Protocol) 服务器提供知识库搜索功能
- **语义检索**: 支持关键词搜索文章标题、摘要和标签
- **统计信息**: 提供知识库统计数据和趋势分析

## 🚀 快速开始

### 环境要求
- Python 3.12+
- Node.js 18+ (可选，用于前端界面)
- Git

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/0xAlanYin/ai-knowledge-base.git
cd ai-knowledge-base
```

2. **安装 Python 依赖**
```bash
pip install -r requirements.txt
```

3. **安装 Node.js 依赖** (可选)
```bash
npm install
```

### 配置说明

1. **数据源配置**
编辑 `config/sources.yaml` 配置采集源：
```yaml
github_trending:
  enabled: true
  schedule: "0 9 * * *"  # 每天 9:00 执行
  keywords: ["llm", "agent", "rag", "fine-tuning"]

hacker_news:
  enabled: true
  schedule: "*/30 * * * *"  # 每 30 分钟执行
```

2. **分发渠道配置**
编辑 `config/channels.yaml` 配置推送渠道：
```yaml
telegram:
  enabled: false
  bot_token: "YOUR_BOT_TOKEN"
  channel_id: "@your_channel"

feishu:
  enabled: false
  app_id: "YOUR_APP_ID"
  app_secret: "YOUR_APP_SECRET"
  receive_id: "YOUR_RECEIVE_ID"
```

## 📁 项目结构

```
ai-knowledge-base/
├── .opencode/              # OpenCode 配置
│   ├── agents/            # Agent 定义文件
│   └── skills/            # 技能定义
├── knowledge/             # 知识库数据
│   ├── raw/              # 原始采集数据
│   └── articles/         # 处理后的知识条目
├── config/               # 配置文件
│   ├── agents.yaml       # Agent 配置
│   ├── sources.yaml      # 数据源配置
│   └── channels.yaml     # 分发渠道配置
├── src/                  # 源代码
│   ├── collectors/       # 采集器实现
│   ├── analyzers/        # 分析器实现
│   ├── distributors/     # 分发器实现
│   └── utils/           # 工具函数
├── mcp_knowledge_server.py    # MCP 知识搜索服务器
├── test_mcp_server.py         # MCP 服务器测试
├── MCP_SERVER_README.md       # MCP 服务器文档
├── AGENTS.md                  # Agent 架构文档
├── requirements.txt           # Python 依赖
└── package.json              # Node.js 依赖
```

## 🔧 使用方法

### 1. 手动运行采集
```bash
# 运行 GitHub Trending 采集
python -m src.collectors.github_trending

# 运行 Hacker News 采集
python -m src.collectors.hacker_news
```

### 2. 运行 AI 分析
```bash
# 分析未处理的数据
python -m src.analyzers.main
```

### 3. 启动 MCP 知识搜索服务器
```bash
# 直接运行测试
python test_mcp_server.py

# 启动 MCP 服务器
python mcp_knowledge_server.py
```

### 4. 配置 Claude Desktop 使用 MCP 服务器
在 Claude Desktop 配置文件中添加：
```json
{
  "mcpServers": {
    "ai-knowledge-base": {
      "command": "python",
      "args": ["/path/to/ai-knowledge-base/mcp_knowledge_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/ai-knowledge-base"
      }
    }
  }
}
```

## 🛠️ 开发指南

### Agent 架构
项目基于 OpenCode 平台构建，包含三个核心 Agent：

1. **采集 Agent (collector)**: 从指定数据源采集原始内容
2. **分析 Agent (analyzer)**: AI 分析、分类、摘要生成
3. **分发 Agent (distributor)**: 多渠道内容分发

### 知识条目格式
知识条目使用标准化的 JSON 格式存储：
```json
{
  "id": "unique-uuid-v4",
  "title": "文章标题或项目名称",
  "source_url": "https://原始来源链接",
  "source_type": "github_trending|hacker_news|custom",
  "content": {
    "raw": "原始内容或摘要",
    "summary": "AI 生成的摘要",
    "key_points": ["关键点1", "关键点2"]
  },
  "analysis": {
    "category": "framework|library|tool|paper|tutorial",
    "relevance_score": 0.95,
    "tags": ["llm", "agent", "rag"]
  },
  "status": "draft|review|processing|analyzed|published"
}
```

### 添加新的数据源
1. 在 `src/collectors/` 目录下创建新的采集器
2. 实现 `collect()` 方法返回标准化数据
3. 在 `config/sources.yaml` 中添加配置
4. 注册到采集 Agent

### 添加新的分发渠道
1. 在 `src/distributors/` 目录下创建新的分发器
2. 实现 `send(article)` 方法
3. 在 `config/channels.yaml` 中添加配置
4. 注册到分发 Agent

## 📈 数据统计

知识库提供以下统计信息：
- 文章总数
- 按来源分类统计
- 热门标签
- 编程语言分布
- 最近采集的文章

通过 MCP 服务器可以实时查询这些统计信息。

## 🤝 贡献指南

1. Fork 本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 开发规范
- 遵循 PEP 8 Python 代码规范
- 使用 snake_case 命名
- 禁止裸 print() 语句，使用 logging 模块
- 所有异常必须被捕获并适当处理
- 添加适当的文档字符串

## 📄 许可证

本项目遵循 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系方式

- 项目主页: [https://github.com/0xAlanYin/ai-knowledge-base](https://github.com/0xAlanYin/ai-knowledge-base)
- 问题反馈: [GitHub Issues](https://github.com/0xAlanYin/ai-knowledge-base/issues)

## 🙏 致谢

感谢以下开源项目的贡献：
- [OpenCode](https://opencode.ai/) - Agent 开发与编排平台
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Agent 工作流编排
- [OpenClaw](https://github.com/opencode-ai/openclaw) - 网页抓取与数据提取

---

*最后更新: 2024-04-22*
*文档版本: 1.0.0*