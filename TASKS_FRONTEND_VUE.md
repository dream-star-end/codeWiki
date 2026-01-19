# Vue 前端重构任务表（DeepWiki 风格）

状态说明：`[ ]` 未开始，`[x]` 已完成

## Phase 0 - 技术选型与规划
- [x] 框架：Vue 3 + Vite + TypeScript
- [x] 路由：Vue Router（单页 + 详情页）
- [x] 状态：Pinia（全局状态）
- [x] UI 框架：Naive UI（暗色调友好、组件齐全）
- [x] 图表渲染：Mermaid + marked
- [ ] 规范：ESLint + Prettier

## Phase 1 - 项目初始化与基础设施
- [x] 初始化 Vite 项目骨架（`frontend-vue/`）
- [ ] 配置 alias、环境变量（`VITE_API_BASE`）
- [x] 接入 UI 框架与全局样式（深色主题）
- [x] 基础布局：顶部栏 + 左侧导航 + 主内容区
- [ ] 公共组件：按钮、卡片、标签、状态提示、加载态

## Phase 2 - 核心页面与布局
- [x] 首页（仓库输入 + 生成按钮）
- [x] 生成进度条与任务状态区
- [x] 左侧 Pages 导航（列表/分组）
- [x] 右侧内容：文档渲染区（Markdown）
- [ ] 右侧 Tabs：文档 / 图表 / 问答

## Phase 3 - 业务功能接入
- [x] 仓库分析接口：`POST /repos/ingest`
- [x] 任务轮询：`GET /jobs/{id}`
- [ ] 文档数据：`GET /repos/{id}/summary`、`/docs/{module_id}`
- [x] 模块列表：`GET /repos/{id}/modules`
- [x] 依赖视图：`GET /repos/{id}/deps`
- [x] 检索：`POST /repos/{id}/search`
- [x] 问答：`POST /repos/{id}/answer`
- [x] AI 文档：`POST /repos/{id}/ai/summary`、`/ai/modules`

## Phase 4 - 可视化与图表
- [x] 架构图（module_deps）
- [x] 数据流图（file_deps）
- [x] 序列图（symbol_deps）
- [ ] 图表“空状态”与加载动画
- [ ] 图表导出（PNG/SVG，可选）

## Phase 5 - 用户体验与可用性
- [x] 模型配置持久化（localStorage）
- [ ] 失败提示与错误边界
- [ ] 搜索结果高亮 + 引用路径展示
- [ ] 文档内锚点导航
- [ ] 页面布局响应式适配（>=1440 / 1024 / 768）

## Phase 6 - 深度功能（对齐 DeepWiki）
- [x] “Export as Markdown / JSON”  
- [x] “Add access tokens” 区域（展示，不入库）
- [ ] Pages 分组与颜色标识（Overview/Architecture/Usage 等）
- [ ] 文档版块卡片化（Quick Start / Architecture / Module Details）

## Phase 7 - 工程化与部署
- [ ] 打包构建 `pnpm build`
- [x] 产物部署说明（静态部署）
- [x] CORS 与 API Base 配置指引

## Phase 8 - 质量保障
- [ ] 基础单元测试（关键工具函数）
- [ ] E2E 测试（可选 Playwright）
- [ ] UI 回归截图（可选）
