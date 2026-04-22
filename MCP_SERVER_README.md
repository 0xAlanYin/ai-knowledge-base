# MCP Knowledge Server

这是一个 MCP (Model Context Protocol) 服务器，用于搜索和查询 AI 知识库中的文章。

## 功能特性

- **search_articles**: 按关键词搜索文章（标题、摘要、标签）
- **get_article**: 按 ID 获取完整文章内容
- **knowledge_stats**: 获取知识库统计信息

## 安装与使用

### 1. 直接运行测试

```bash
# 测试知识库功能
python test_mcp_server.py
```

### 2. 作为 MCP Server 运行

MCP Server 使用 JSON-RPC 2.0 over stdio 协议：

```bash
# 启动服务器（通过 stdio 通信）
python mcp_knowledge_server.py
```

### 3. 在 Claude Desktop 中配置

在 Claude Desktop 的配置文件中添加：

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

## API 文档

### search_articles 工具

搜索知识库中的文章。

**参数**:
- `keyword` (string, required): 搜索关键词（不区分大小写）
- `limit` (integer, optional): 返回结果数量，默认 5，范围 1-20

**搜索范围**:
- 文章标题
- 文章摘要
- 标签
- 来源描述

**返回格式**:
```json
[
  {
    "id": "文章ID",
    "title": "文章标题",
    "source": "来源类型",
    "summary": "摘要（前200字符）",
    "score": "匹配分数",
    "tags": ["标签1", "标签2"],
    "source_url": "来源URL",
    "language": "编程语言",
    "stars": "GitHub星数"
  }
]
```

### get_article 工具

获取完整文章内容。

**参数**:
- `article_id` (string, required): 文章ID

**返回格式**:
完整的文章 JSON 数据（与 knowledge/articles/processed/ 目录下的格式相同）

### knowledge_stats 工具

获取知识库统计信息。

**参数**: 无

**返回格式**:
```json
{
  "total_articles": 15,
  "sources": {
    "github_trending": 15
  },
  "top_tags": [
    {"tag": "tool", "count": 8},
    {"tag": "agent", "count": 8}
  ],
  "languages": {
    "Python": 5,
    "TypeScript": 3,
    "Go": 2
  },
  "recent_articles": [
    {
      "id": "文章ID",
      "title": "文章标题",
      "source": "来源类型",
      "collected_at": "采集时间"
    }
  ]
}
```

## 技术实现

### 文件结构
```
ai-knowledge-base/
├── mcp_knowledge_server.py    # MCP 服务器主文件
├── test_mcp_server.py         # 测试脚本
├── MCP_SERVER_README.md       # 本文档
└── knowledge/articles/processed/  # 文章数据目录
```

### 依赖
- 仅使用 Python 标准库
- 无第三方依赖

### 协议
- JSON-RPC 2.0 over stdio
- 支持 MCP initialize、tools/list、tools/call 方法

## 文章数据格式

文章使用以下 JSON 格式：
```json
{
  "id": "唯一ID",
  "title": "文章标题",
  "source_url": "来源URL",
  "source_type": "来源类型",
  "source_metadata": {
    "stars": "GitHub星数",
    "language": "编程语言",
    "description": "描述",
    "topics": ["主题1", "主题2"]
  },
  "content": {
    "raw": "原始内容",
    "summary": "AI生成的摘要",
    "key_points": ["关键点1", "关键点2"]
  },
  "analysis": {
    "category": "分类",
    "relevance_score": 0.9,
    "tags": ["标签1", "标签2"]
  }
}
```

## 故障排除

### 常见问题

1. **服务器无法启动**
   - 检查 Python 版本（需要 Python 3.7+）
   - 检查文件路径是否正确

2. **找不到文章**
   - 确认 knowledge/articles/processed/ 目录存在且包含 JSON 文件
   - 检查文件权限

3. **搜索无结果**
   - 尝试不同的关键词
   - 检查关键词是否拼写正确

### 日志
服务器将错误信息输出到 stderr，正常操作信息也会输出到 stderr。

## 扩展开发

要添加新工具，修改 `MCPServer` 类中的 `self.tools` 字典和 `_handle_tools_call` 方法。

## 许可证

本项目遵循 AI 知识库项目的相同许可证。