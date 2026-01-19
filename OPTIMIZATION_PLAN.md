# Codebase Analyzer 优化计划

## 项目目标

**核心定位**：辅助用户学习Git开源项目，为代码开发提供智能Codebase上下文支持。

## 项目现状分析

### ✅ 已完成功能

**后端 (Backend)**
| 功能 | 状态 | 说明 |
|------|------|------|
| 仓库导入 | ✅ | 支持 Git URL 和本地路径 |
| Python 解析 | ✅ | tree-sitter AST解析，类/函数/导入提取 |
| Java 解析 | ✅ | tree-sitter AST解析，类/方法/导入提取 |
| 文件依赖图 | ✅ | 基于 import 分析的文件级依赖 |
| 符号依赖图 | ✅ | 符号级调用/继承/使用关系 |
| 模块聚类 | ✅ | 目录结构 + 依赖密度聚类 |
| FAISS 检索 | ✅ | 向量索引，支持语义搜索 |
| Q&A 接口 | ✅ | OpenAI 兼容的问答端点 |
| AI 文档生成 | ✅ | 仓库总结和模块文档 |
| 数据库持久化 | ✅ | SQLite 存储分析结果 |
| Job 队列 | ✅ | 异步任务和进度跟踪 |

**前端 (Frontend-Vue)**
| 功能 | 状态 | 说明 |
|------|------|------|
| 仓库分析提交 | ✅ | 输入URL/路径启动分析 |
| 进度展示 | ✅ | 实时轮询显示进度 |
| 模块导航 | ✅ | 左侧Pages列表 |
| 文档渲染 | ✅ | Markdown渲染 |
| Mermaid图表 | ✅ | 架构图/数据流/序列图 |
| 问答功能 | ✅ | Q&A Tab |
| 导出功能 | ✅ | Markdown/JSON导出 |
| 多语言支持 | ✅ | 中文/英文切换 |

### ❌ 待完善功能

1. **代码浏览** - 无法查看源代码
2. **符号跳转** - 无法跳转到定义/引用
3. **代码解释** - 缺乏逐行/函数解释
4. **学习路径** - 缺乏推荐阅读顺序
5. **Codebase导出** - 无法导出AI IDE上下文
6. **对话历史** - Q&A无记忆
7. **代码搜索** - 仅支持语义搜索

---

## 优化方案

### Phase 1: 代码浏览与学习辅助 (优先级: 高)

#### 1.1 代码浏览器 API

**后端新增接口**:

```
GET /repos/{repo_id}/files
- 返回文件树结构

GET /repos/{repo_id}/files/{path}
- 返回指定文件内容（带语法高亮标记）

GET /repos/{repo_id}/symbols/{symbol_id}
- 返回符号详情（定义位置、签名、文档）

GET /repos/{repo_id}/symbols/{symbol_id}/references
- 返回符号的所有引用位置

GET /repos/{repo_id}/symbols/{symbol_id}/definition
- 跳转到符号定义
```

**前端新增组件**:

- `CodeBrowser.vue` - 文件树 + 代码编辑器（只读）
- `SymbolPanel.vue` - 符号信息面板
- 代码高亮：使用 Shiki 或 Prism
- 点击符号跳转到定义/引用

#### 1.2 智能代码解释

**后端新增接口**:

```
POST /repos/{repo_id}/explain
- body: { file_path, line_start?, line_end?, symbol_id? }
- response: { explanation, context, related_symbols }

POST /repos/{repo_id}/explain/function
- body: { symbol_id }
- response: { summary, params, returns, examples, complexity }
```

**前端交互**:
- 选中代码 → 右键"解释代码"
- 函数/类悬停显示AI摘要

#### 1.3 学习路径推荐

**后端新增接口**:

```
GET /repos/{repo_id}/learning-path
- response: { 
    recommended_order: [...],
    entry_points: [...],
    key_concepts: [...],
    difficulty_levels: { beginner: [...], intermediate: [...], advanced: [...] }
  }

GET /repos/{repo_id}/learning-path/{module_id}
- 返回模块内的学习路径
```

**算法**:
1. 分析依赖图，找出入口点（低依赖、高被依赖）
2. 拓扑排序，生成阅读顺序
3. 根据代码复杂度分级

---

### Phase 2: Codebase 上下文支持 (优先级: 高)

#### 2.1 上下文导出

**后端新增接口**:

```
POST /repos/{repo_id}/codebase/export
- body: { 
    format: "cursor" | "copilot" | "markdown" | "json",
    scope: "full" | "module" | "files",
    module_ids?: string[],
    file_paths?: string[],
    include_deps?: boolean,
    max_tokens?: number
  }
- response: {
    content: string,
    token_count: number,
    files_included: string[]
  }
```

**导出格式**:

1. **Cursor/IDE 格式**:
```
<codebase>
<file path="src/main.py">
... 代码内容 ...
</file>
...
</codebase>
```

2. **Copilot 格式**:
```markdown
## Project Structure
- src/
  - main.py (entry point)
  - utils/
    - helpers.py

## Key Files
### src/main.py
```python
...
```
```

3. **智能上下文摘要**:
```
POST /repos/{repo_id}/codebase/context
- body: { query: string, max_tokens?: number }
- response: { context: string, sources: Citation[] }
```

根据用户问题，智能选取相关代码片段组成上下文。

#### 2.2 项目摘要增强

```
GET /repos/{repo_id}/codebase/summary
- response: {
    overview: string,
    architecture: string,
    tech_stack: string[],
    key_patterns: string[],
    entry_points: Entry[],
    dependencies: Dep[],
    test_coverage?: number
  }
```

---

### Phase 3: 搜索与交互优化 (优先级: 中)

#### 3.1 混合搜索

**后端优化**:

```
POST /repos/{repo_id}/search
- body: {
    query: string,
    mode: "semantic" | "keyword" | "hybrid",
    scope: "code" | "doc" | "all",
    file_types?: string[],
    module_scope?: string[]
  }
```

- 语义搜索：现有 FAISS
- 关键词搜索：ripgrep 集成
- 混合模式：加权组合

#### 3.2 对话历史

**后端新增**:

```
POST /repos/{repo_id}/chat
- body: {
    message: string,
    conversation_id?: string,
    model: ModelConfig
  }
- response: {
    answer: string,
    citations: Citation[],
    conversation_id: string,
    suggestions?: string[]
  }

GET /repos/{repo_id}/chat/{conversation_id}/history
- 返回对话历史
```

**前端**:
- 对话式界面
- 历史记录保存
- 上下文关联问答

#### 3.3 图表交互增强

- 点击模块节点 → 跳转到模块详情
- 点击文件节点 → 打开代码浏览器
- 图表缩放/拖拽
- 节点搜索高亮

---

### Phase 4: 文档质量提升 (优先级: 中)

#### 4.1 README 分析

```
GET /repos/{repo_id}/readme
- response: {
    raw: string,
    parsed: {
      title: string,
      description: string,
      installation: string,
      usage: string,
      api?: string,
      contributing?: string
    }
  }
```

#### 4.2 API 文档生成

```
POST /repos/{repo_id}/docs/api
- body: { module_id?, format: "markdown" | "openapi" }
- response: { content: string }
```

自动提取：
- 函数签名和参数
- 类型注解
- docstring
- 示例代码

#### 4.3 示例代码提取

```
GET /repos/{repo_id}/examples
- response: {
    examples: [{
      name: string,
      description: string,
      code: string,
      file_path: string,
      line_range: [number, number]
    }]
  }
```

从测试文件、example目录、docstring中提取。

---

## 技术实现要点

### 后端

1. **代码浏览**
   - 新增 `app/services/code_browser.py`
   - 文件树构建 + 内容读取
   - 语法高亮：pygments 或返回 token 让前端高亮

2. **符号跳转**
   - 扩展 `db.py` 添加符号索引查询
   - 新增 `app/services/symbol_navigator.py`

3. **上下文导出**
   - 新增 `app/services/codebase_export.py`
   - Token 计算：tiktoken
   - 智能裁剪策略

4. **对话系统**
   - 新增 `app/services/conversation.py`
   - 对话表：conversation_id, repo_id, messages
   - 上下文窗口管理

### 前端

1. **代码浏览器**
   - Monaco Editor (只读模式)
   - 文件树组件
   - 符号列表 + 跳转

2. **对话界面**
   - ChatPanel.vue
   - 消息列表 + 输入框
   - 引用展示

3. **图表交互**
   - 替换 Mermaid → D3.js / ECharts
   - 支持节点点击事件

---

## 实施优先级

| 阶段 | 功能 | 预估工时 | 优先级 |
|------|------|---------|--------|
| P1.1 | 代码浏览器 API + 前端 | 3-4天 | 🔴 高 |
| P1.2 | 符号跳转/定义查找 | 2天 | 🔴 高 |
| P2.1 | Codebase 上下文导出 | 2-3天 | 🔴 高 |
| P1.3 | 代码解释功能 | 2天 | 🟡 中 |
| P3.1 | 混合搜索 | 2天 | 🟡 中 |
| P3.2 | 对话历史 | 2天 | 🟡 中 |
| P1.4 | 学习路径推荐 | 2天 | 🟡 中 |
| P3.3 | 图表交互增强 | 3天 | 🟢 低 |
| P4 | 文档质量提升 | 2-3天 | 🟢 低 |

---

## 下一步行动

1. **立即开始**：实现代码浏览器 API（`/files`, `/files/{path}`）
2. **本周目标**：完成 Phase 1.1 + 1.2
3. **月度目标**：完成 Phase 1 + Phase 2

---

## 文件结构变更

```
backend/app/
├── api/
│   └── routes.py           # 新增 /files, /symbols, /codebase 路由
├── services/
│   ├── code_browser.py     # 新增：文件浏览
│   ├── symbol_navigator.py # 新增：符号跳转
│   ├── codebase_export.py  # 新增：上下文导出
│   ├── conversation.py     # 新增：对话管理
│   ├── learning_path.py    # 新增：学习路径
│   └── ...

frontend-vue/src/
├── components/
│   ├── CodeBrowser.vue     # 新增：代码浏览器
│   ├── SymbolPanel.vue     # 新增：符号面板
│   ├── ChatPanel.vue       # 新增：对话面板
│   └── ...
├── views/
│   └── HomeView.vue        # 修改：集成新组件
└── stores/
    └── wiki.ts             # 修改：新增状态
```
