# Zowsup Dashboard 实现 TODO 清单

**项目**: 聊天智能管理Dashboard  
**前端框架**: React  
**后端框架**: Flask API  
**数据库**: SQLite (扩展)  
**通信**: WebSocket + SSE  
**创建时间**: 2026-04-28

---

## ✅ 架构决策记录（已确认，不再讨论）

| 决策项 | 结论 | 影响 |
|--------|------|------|
| Dashboard 数据库位置 | **独立 `dashboard.db`**，与账号专属 `db.db` 分离 | Phase 1 所有表建在 `dashboard.db` 里 |
| 多账号支持 | **单账号**，当前 zowbot 是单账号登录 | 不需要 `bot_id` 多账号切换 UI |
| Flask 进程隔离 | **独立进程**，通过 SQLite 文件共享数据，不嵌入 bot 进程 | Flask 和 bot 不共享内存/event loop，无 asyncio 冲突 |
| 进程通信方式 | **共享 SQLite 读** + **调用 bot 暴露的 API**（如有需要） | Flask 只读 `dashboard.db`，bot 写；策略变更通知 bot 可通过本地 HTTP/文件 |

> ⚠️ **重要约束**：Flask 使用标准同步 WSGI，绝不引入 eventlet/gevent（与 bot 的 asyncio 不兼容）

---

## ✅ Phase 1: 数据库 + 基础API（已完成）

### 数据库结构搭建
- [x] 1.1 创建新数据库表结构 (chat_messages, ai_thoughts, user_profiles, strategy_applications, strategy_conflicts, daily_statistics)
- [x] 1.2 添加数据库索引优化 (idx_messages_user, idx_thoughts_user, idx_profiles_bot, idx_strategy_user)
- [x] 1.3 编写数据库迁移脚本 (从账号专属 `db.db` 的 `ai_memory` 表读取历史对话，写入 `dashboard.db` 的 `chat_messages` 表)
- [x] 1.3a 配置 `dashboard.db` 路径 (建议存放在 `data/dashboard.db`，与账号 `db.db` 完全分离)
- [x] 1.4 创建数据库初始化脚本 (`init_dashboard_db.py`，建表 + 建索引 + 设置 WAL 模式)
- [x] 1.4a 配置 SQLite WAL 模式 (`PRAGMA journal_mode=WAL`，防止 bot 写 + Flask 读并发时出现 `database is locked` 错误)
- [x] 1.5 添加数据库连接池管理

### Flask API 框架搭建
- [x] 1.6 创建 Flask 应用结构 (`app/dashboard/api/`)
- [x] 1.6a 编写 Flask 独立进程启动脚本 (`run_dashboard.py`，独立于 bot 的 `script/main.py`，使用标准 WSGI，不引入 eventlet/gevent)
- [x] 1.7 配置 Flask-RESTful 或 Flask-Blueprint
- [x] 1.8 设置 CORS 允许跨域请求
- [x] 1.9 添加请求日志中间件
- [x] 1.10 配置环境变量和配置文件

### 基础 API 端点实现
- [x] 1.11 `GET /api/user-profile` - 获取用户画像
- [x] 1.12 `GET /api/chat-history` - 获取聊天记录
- [x] 1.13 `GET /api/statistics` - 获取统计数据
- [x] 1.14 `POST /api/health-check` - 健康检查端点
- [x] 1.15 编写 API 单元测试 (pytest)

### ✅ Phase 1 验证检查点
**目标**：Flask 服务独立运行，所有 API 端点可访问，`dashboard.db` 数据库表已建好  
**验证命令**：
- `python run_dashboard.py` → 启动成功，无报错  
- `curl http://localhost:5000/api/health` → `{"status": "ok"}`  
- `curl "http://localhost:5000/api/user-profile?jid=test"` → HTTP 200，返回空数据结构（不是 404/500）  
- `curl "http://localhost:5000/api/chat-history?jid=test"` → HTTP 200，返回空列表  
- `curl "http://localhost:5000/api/statistics"` → HTTP 200，返回零值统计  
- 用 SQLite Browser 打开 `data/dashboard.db` → 所有表已创建，`PRAGMA journal_mode` 返回 `wal`  

**合格标准**：所有端点返回 200，bot 进程未受影响（可同时运行两个进程）

---

## ✅ Phase 2: AI 数据管道 + 用户画像引擎（已完成）
> **合并自原 Phase 2 + Phase 3**：单独完成 Phase 2 后，`ai_thoughts` 表有数据，但 `/api/user-profile` 仍返回空（画像计算未实现）；必须整体交付才有可在 API 层验证的输出，故合并为一个 Phase。

### ⚠️ 改造前必做：调用方梳理
- [x] 2.0 列出所有调用 `process_message()` 的地方（当前已知：`zowbot_layer.py:1205`、`ai_test.py:25`、`retry_manager` 内部），确认改造范围
- [x] 2.0a 设计向后兼容策略（新返回值结构要兼容所有调用方，建议返回 `Optional[AIResult]`，`AIResult.response` 保持字符串，调用方可继续用 `if ai_response:`）

### AI思考记录结构化
- [x] 2.1 修改 `AIService.process_message()` 返回结构（改为 `Optional[AIResult]`，`AIResult` 包含 `response: str` + `thought: AIThought`）
- [x] 2.1a 同步更新所有调用方（`zowbot_layer.py`、`ai_test.py`）以适配新返回值，保证现有 bot 逻辑不中断
- [x] 2.2 创建 AI 思考数据结构 (`AIThought` 类)
- [x] 2.3 实现 `_save_ai_thought()` 方法
- [x] 2.4 添加思考记录到数据库
- [x] 2.5 编写 AIService 集成测试

### 错误处理和日志
- [x] 2.6 添加异常处理和重试机制
- [x] 2.7 配置 AI 思考记录的日志级别
- [x] 2.8 添加性能监控 (思考记录保存时间)

---

### 用户画像计算引擎（原 Phase 3 内容）

#### 用户画像聚合引擎
- [x] 3.1 创建 UserProfileAnalyzer 类
- [x] 3.2 实现统计数据聚合逻辑 (交互次数、消息类型分布等)
- [x] 3.3 实现自动标签推断算法 (user_category, communication_style)
- [x] 3.4 实现话题倾向分析 (topic_preferences)
- [x] 3.5 实现满意度评分计算 (satisfaction_score)

#### 趋势和分析 实现 7 天、30 天趋势计算
- [x] 3.7 实现用户分类逻辑 (VIP, 普通, 新用户, 流失风险)
- [x] 3.8 创建后台任务定期更新用户画像 (APScheduler)
- [x] 3.9 编写用户画像计算单元测试

#### 数据库更新 实现批量插入/更新优化
- [x] 3.11 添加事务管理
- [x] 3.12 性能基准测试 (Benchmark)

### ✅ Phase 2 验证检查点
**目标**：完整数据链路可跑通：bot 收到消息 → AI 思考记录入库 → 用户画像计算 → API 返回真实数据  
**验证命令**：
- 同时启动 bot（`python script/main.py`）和 Flask 服务（`python run_dashboard.py`）
- 向 bot 发送一条真实 WhatsApp 测试消息
- `curl "http://localhost:5000/api/user-ai-thoughts?jid=<测试jid>"` → 返回包含真实 AI 思考记录的列表（非空）
- `curl "http://localhost:5000/api/user-profile?jid=<测试jid>"` → 返回包含 `user_category`、`communication_style`、`satisfaction_score`、趋势数据的完整画像（非空）
- `curl "http://localhost:5000/api/chat-history?jid=<测试jid>"` → 返回真实历史对话列表
- 检查 `data/dashboard.db`：`ai_thoughts` 表和 `user_profiles` 表各有至少一条记录  

**合格标准**：以上全部满足，且 **bot 原有 AI 自动回复功能未中断**（Breaking Change 验证）

---

## ✅ Phase 3: 策略引擎（已完成）
> **原 Phase 4**，无内容改动，仅重新编号。

### ⚠️ 设计前必做：策略加载机制
- [x] 4.0 设计策略数据结构和 `AIService` 加载策略机制
  - 全局策略 vs 个人策略优先级规则（个人 > 全局）
  - **实际实现**：`StrategyManager` 每次调用时直接读取 DB（per-call，无缓存）；Flask 写入 → bot 处理下一条消息时自动生效，**不需要**文件信号/HTTP通知
  - 原计划的「文件信号/本地HTTP/定时轮询」热推送方案已废弃，per-call DB 读取足够满足需求且更简单
  - **在此任务完成之前不要开始 4.11/4.12**

### 策略应用逻辑
- [x] 4.1 创建 `StrategyManager` 类
- [x] 4.2 实现全局策略应用接口 (`POST /api/apply-global-strategy`)
- [x] 4.3 实现个人策略应用接口 (`POST /api/apply-strategy`)
- [x] 4.4 实现策略版本控制
- [x] 4.5 策略生效时间控制（**实际：无 TTL**，策略永久有效直到下次 `apply_strategy`；per-call 读 DB 等同于每次都加载最新策略）

### 策略冲突检测
- [x] 4.6 实现冲突检测算法
- [x] 4.7 记录冲突消息（**实际：写入独立 `strategy_conflicts` 表**；`chat_messages` 本身无冲突标记字段；`strategy_conflicts.message_id` 可关联）
- [x] 4.8 创建冲突预警系统
- [x] 4.9 冲突解决（**实际：rollback 回滚机制**；无主动 AI 建议；`POST /api/strategy/rollback` 恢复上一版本）
- [x] 4.10 编写冲突检测测试

### 策略执行
- [x] 4.11 在 AI 回复时应用策略
- [x] 4.12 修改 `AIService.process_message()` 支持策略应用
- [x] 4.13 记录策略应用的审计日志
- [x] 4.14 实现策略回滚功能

### ✅ Phase 3 验证检查点
**目标**：策略 API 可操作，bot 后续回复实际遵循所设策略  
**验证命令**：
- `curl -X POST http://localhost:5000/api/apply-global-strategy -H "Content-Type: application/json" -d '{"response_style":"formal","tone":"polite"}'` → 200 OK  
- 向 bot 发送测试消息 → 观察回复风格是否符合策略设置（主观判断 + 审计日志验证）  
- `curl -X POST http://localhost:5000/api/apply-strategy -H "Content-Type: application/json" -d '{"jid":"<测试jid>","style":"concise"}'` → 200 OK  
- `curl "http://localhost:5000/api/user-profile?jid=<测试jid>"` → 返回中包含当前策略字段  
- 检查 `data/dashboard.db`：`strategy_applications` 表有审计记录  
- 执行回滚操作 → 确认回滚后 bot 回复风格恢复  

**合格标准**：以上全部满足；策略变更通知机制已简化为 per-call DB 读取（无需推送，bot 下一条消息自动生效）

---

## ✅ Phase 4: 实时通信 + React 前端（已完成）
> **合并自原 Phase 5 + Phase 6**：WebSocket/SSE 纯后端部分无用户可见的验证点（只能 curl/wscat 调试），必须与前端一起交付，才能在浏览器中端到端验证完整实时推送链路。

### WebSocket 实现
- [x] 5.1 集成 Flask-SocketIO
- [x] 5.2 实现 WebSocket 连接管理
- [x] 5.3 实现 `subscribe_user_updates` 事件处理
- [x] 5.4 实现 `new_message` 事件推送
- [x] 5.5 实现 `strategy_applied` 事件推送
- [x] 5.6 实现 `profile_updated` 事件推送
- [x] 5.7 测试 WebSocket 连接稳定性

### SSE 实现
- [x] 5.8 创建 SSE 端点 `GET /api/statistics-stream`
- [x] 5.9 实现后台统计数据更新线程
- [x] 5.10 实现 SSE 推送逻辑 (按需策略)
- [x] 5.11 添加连接心跳检测
- [x] 5.12 编写 SSE 压力测试

### API 完整性
- [→] 5.13 `POST /api/apply-strategy` → **已在 Phase 3 (4.3) 实现，此处跳过**
- [→] 5.14 `POST /api/apply-global-strategy` → **已在 Phase 3 (4.2) 实现，此处跳过**
- [→] 5.15 `GET /api/user-ai-thoughts` → **已在 Phase 2 实现，此处跳过**
- [x] 5.16 添加 API 速率限制
- [x] 5.17 实现 API Token 认证 (**必须实现**，Dashboard 管理 WhatsApp 真实账号对话数据，不可跳过；最低要求：Header Bearer Token 校验)

---

### React 前端搭建（原 Phase 6 内容）

### 项目初始化
- [x] 6.1 使用 **Vite** 初始化 React 项目 (`npm create vite@latest`，CRA 已于 2023 年停止维护)
- [x] 6.2 配置 Vite 构建选项 (开发环境代理 `/api` → Flask，生产环境打包路径)
- [x] 6.3 添加 ESLint 和 Prettier
- [x] 6.4 配置 TypeScript (可选)
- [x] 6.5 设置目录结构

### 状态管理
- [x] 6.6 集成 Redux 或 Zustand
- [x] 6.7 创建 store 配置
- [x] 6.8 创建 action creators
- [x] 6.9 创建 reducers
- [x] 6.10 设置中间件 (日志、异常处理)

### UI 组件库
- [x] 6.11 选择 UI 库 (Ant Design / Material-UI / Chakra)
- [x] 6.12 配置主题和样式
- [x] 6.13 创建全局样式
- [x] 6.14 设置响应式布局

### 核心页面组件

#### 左侧联系人列表
- [x] 6.15 ContactList 组件
- [x] 6.16 联系人搜索和筛选
- [x] 6.17 联系人分组标签展示
- [x] 6.18 活跃指示器和统计摘要
- [x] 6.19 联系人项选中状态管理

#### 中间聊天记录区
- [x] 6.20 ChatHistory 组件
- [x] 6.21 消息列表展示
- [x] 6.22 消息虚拟化 (大列表优化)
- [x] 6.23 消息类型多样化显示 (文本/图片/视频/表情等)
- [x] 6.24 消息时间戳和状态显示
- [x] 6.25 自动加载更多消息 (分页)
- [x] 6.26 消息输入框 (只读展示)

#### 右侧用户画像面板
- [x] 6.27 UserProfile 组件
- [x] 6.28 用户基本信息展示
- [x] 6.29 自动标签展示
- [x] 6.30 沟通特点分析展示
- [x] 6.31 互动趋势图表
- [x] 6.32 推荐策略展示
- [x] 6.33 当前策略展示
- [x] 6.34 策略快速编辑弹窗

### 底部统计面板
- [x] 6.35 StatisticsPanel 组件
- [x] 6.36 基础数据卡片
- [x] 6.37 消息分布 Pie Chart
- [x] 6.38 用户特征分布 Bar Chart
- [x] 6.39 时间热力图 Heatmap
- [x] 6.40 AI 表现指标
- [x] 6.41 异常预警列表

### 全局策略设置页面
- [x] 6.42 GlobalStrategy 页面
- [x] 6.43 策略表单组件
- [x] 6.44 响应风格选项
- [x] 6.45 回复速度选项
- [x] 6.46 语气选择选项
- [x] 6.47 AI 模块配置
- [x] 6.48 应用和预览按钮

### 通信集成
- [x] 6.49 WebSocket 连接管理 Hook
- [x] 6.50 SSE 连接管理 Hook
- [x] 6.51 实时消息更新处理
- [x] 6.52 实时统计更新处理
- [x] 6.53 错误重连机制

### HTTP 请求
- [x] 6.54 Axios 或 Fetch 配置
- [x] 6.55 创建 API 服务层
- [x] 6.56 实现 API 拦截器
- [x] 6.57 错误处理和提示

### 数据可视化
- [x] 6.58 集成 Chart.js 或 ECharts
- [x] 6.59 创建 Pie Chart 组件
- [x] 6.60 创建 Bar Chart 组件
- [x] 6.61 创建 Heatmap 组件
- [x] 6.62 创建 Line Chart 组件 (趋势)

### ✅ Phase 4 验证检查点
**目标**：在浏览器中看到完整可用的 Dashboard，实时更新正常工作  
**验证方式**：
- 同时启动：`npm run dev`（前端 Vite）+ `python run_dashboard.py`（Flask 后端）+ `python script/main.py`（bot）
- 打开 `http://localhost:5173` → 看到完整 Dashboard（左/中/右三栏 + 底部统计面板全部渲染，无空白/报错）
- 在左侧联系人列表选中一个联系人 → 中间聊天记录加载，右侧用户画像显示标签和评分
- 向 bot 发送测试消息 → 聊天记录**实时刷新**（WebSocket 推送，无需手动刷新页面）
- 底部统计面板数字**实时变化**（SSE 推送）
- 在全局策略页填写策略 → 点击应用 → bot 后续回复遵循新策略
- 断开网络重连后，WebSocket/SSE 自动恢复连接  

**✅ Phase 4 验收状态（2026-04-28）**：
- 后端全部通过（86/86 tests passed, 0 skipped）
- `npm run build` 干净通过（3729 modules，输出到 `app/dashboard/static/`）
- 前端 `npm run dev` 已启动，代理正确指向 `127.0.0.1:5000`
- `run_dashboard.py` 在 venv 下正常启动，Flask-SocketIO threading 模式运行
- 右侧用户画像面板新增「调整此会话策略」Modal（per-JID 策略即时生效）+ 「回滚策略」按钮
- 待完整端到端验证（需同时启动 bot + 发送真实消息）

---

## ✅ Phase 5: Bot 登录管理（已完成，2026-04-28，20/20 tests）

### 架构说明
> Bot 进程（asyncio）与 Flask 进程独立，通过 `data/bot_status.json` 状态文件 + subprocess 通信。
> Flask 启动子进程执行 `script/regwithscan.py` / `script/regwithlinkcode.py`，捕获 stdout 获取 QR/链接码，通过 SSE 推送到前端。

### 后端 API（新建 `app/dashboard/api/bot_control.py`）
- [x] B.1 `GET  /api/bot/status` — 读取 `data/bot_status.json`，返回 `{running, jid, uptime}`
- [x] B.2 `POST /api/bot/login-scan` — 启动 `regwithscan.py` 子进程，写入 PID 文件
- [x] B.3 `GET  /api/bot/qr-stream` — SSE 端点，推送 QR 码 base64（子进程 stdout 捕获）
- [x] B.4 `POST /api/bot/login-linkcode` — 启动 `regwithlinkcode.py`，返回链接码
- [x] B.5 `POST /api/bot/logout` — 发送 SIGTERM 给 bot 进程（PID 文件），更新状态文件
- [x] B.6 Bot 状态写入机制 — `script/main.py` 启动/退出时写 `data/bot_status.json`

### 前端页面（新建 `src/pages/BotLoginPage.tsx`）
- [x] B.7 登录入口页面（扫码 / 链接码 两种模式选择）
- [x] B.8 QR 码展示组件（轮询 SSE，二维码过期自动刷新）
- [x] B.9 链接码输入组件（输入手机号，显示返回的链接码）
- [x] B.10 登录成功后跳转到主 Dashboard
- [x] B.11 顶部导航栏显示 Bot 在线状态指示灯 + 当前账号 JID

### 测试
- [x] B.12 编写 `tests/test_phase5_bot_control.py`

### ✅ Phase 5 验证检查点
**目标**：可在 Dashboard 界面完成 bot 账号登录，无需命令行  
**验证命令**：
- 打开 `http://localhost:5173/login` → 看到扫码/链接码两种登录方式
- 选择扫码 → QR 码在页面显示 → 手机 WhatsApp 扫码 → 页面自动跳转到 Dashboard 主页
- 选择链接码 → 输入手机号 → 页面显示 8 位链接码 → 在手机端输入 → 登录成功
- 顶部显示「● 在线 +86xxxxxxxxx」
- `GET /api/bot/status` → `{"running": true, "jid": "+86xxxxxxxxx@s.whatsapp.net"}`

---

## ✅ Phase 6: 集成测试和优化（原 Phase 5，顺延）已完成，2026-04-29，52/52 tests
> **原 Phase 7**，重新编号为 Phase 6。

### 端到端测试
- [x] 7.1 编写 E2E 测试用例 (Cypress/Playwright)
- [x] 7.2 测试联系人列表交互
- [x] 7.3 测试聊天记录加载
- [x] 7.4 测试用户画像更新
- [x] 7.5 测试策略应用流程

### 性能优化
- [x] 7.6 前端打包优化 (代码分割)
- [x] 7.7 后端数据库查询优化
- [x] 7.8 缓存策略实现 (TTL+LRU 内存缓存)
- [x] 7.9 API 响应时间基准测试
- [x] 7.10 前端加载时间测试

### 安全性
- [x] 7.11 实现 CSRF 保护
- [x] 7.12 实现 XSS 防护
- [x] 7.13 输入验证
- [x] 7.14 API 认证令牌刷新
- [x] 7.15 安全审计日志

### ✅ Phase 6 验收状态
**完成时间**：2026-04-29  
**测试结果**：`pytest tests/` → **158/158 passed**（106 Phase 1-5 + 52 Phase 6 新增）  
**关键交付物**：
- `app/dashboard/api/security.py` — CSP / X-Frame-Options / Referrer-Policy / Permissions-Policy 响应头
- `app/dashboard/utils/audit_log.py` — AUTH_SUCCESS / AUTH_FAILURE / TOKEN_VERIFY 结构化审计日志
- `app/dashboard/api/validators.py` — JID / 分页 / 字符串字段 输入验证器
- `app/dashboard/utils/cache.py` — 线程安全 TTL+LRU 内存缓存（maxsize=256, ttl=60s）
- `app/dashboard/api/auth.py` — `/api/auth/verify` + `/api/auth/refresh` 端点
- `app/dashboard/utils/db_init.py` — 5 个新复合索引 + `PRAGMA optimize`
- `dashboard-frontend/vite.config.ts` — manualChunks 代码分割（vendor-react/antd/echarts/state/network）
- `dashboard-frontend/e2e/*.spec.ts` — 4 个 Playwright 测试套件（app-load / contact-list / chat-history / user-profile）
- `tests/test_phase6_security.py` — 52 个 pytest 测试（TTLCache/Benchmark/Headers/Validation/Auth/AuditLog/DBIndexes）

---

## ✅ Phase 7: 部署和文档（已完成，2026-04-29）
> **原 Phase 8**，无内容改动，仅重新编号。

### 部署准备
- [x] 8.1 Docker 容器化 — `Dockerfile`, `docker-compose.yml`, `dashboard-frontend/Dockerfile.frontend`, `dashboard-frontend/nginx.conf`, `.dockerignore`
- [x] 8.2 环境配置文件 (.env) — `.env.example`, dotenv 已集成到 `run_dashboard.py` + `config.py`
- [x] 8.3 数据库备份和恢复脚本 — `scripts/backup_db.py`, `scripts/restore_db.py`
- [x] 8.4 生产环境检查清单 — `scripts/check_production.py`

### 文档编写
- [x] 8.5 API 文档 (Swagger/OpenAPI) — `docs/openapi.yaml`, `/api/docs` + `/api/openapi.yaml` 端点
- [x] 8.6 前端组件文档 (Storybook) — `.storybook/main.ts|preview.ts`, 3 组件 Stories（ContactList, ChatHistory, UserProfile）
- [x] 8.7 部署指南 — `docs/DEPLOY.md`
- [x] 8.8 运维手册 — `docs/OPERATIONS.md`
- [x] 8.9 用户使用指南 — `docs/USER_GUIDE.md`

### 监控和日志
- [x] 8.10 配置应用日志系统 — `app/dashboard/utils/logging_setup.py`（RotatingFileHandler，`logs/dashboard.log` + `logs/dashboard_audit.log`）
- [x] 8.11 设置错误追踪 (Sentry) — `_init_sentry()` 已集成到 `create_app()`，由 `SENTRY_DSN` 环境变量激活
- [x] 8.12 性能监控 (APM) — 见 `docs/MONITORING.md`（Sentry Perf / Prometheus 方案）
- [x] 8.13 创建告警规则 — 见 `docs/MONITORING.md`（Sentry Alerts + Prometheus Alertmanager 规则）

### ✅ Phase 7 交付摘要

| 类别 | 交付物 |
|------|--------|
| Docker | `Dockerfile`, `docker-compose.yml`, `Dockerfile.frontend`, `nginx.conf`, `.dockerignore` |
| 环境配置 | `.env.example`，dotenv 集成 |
| 数据库运维 | `scripts/backup_db.py`, `scripts/restore_db.py`, `scripts/check_production.py` |
| API 文档 | `docs/openapi.yaml` + `/api/docs` Swagger UI |
| 前端文档 | Storybook 配置 + 3 个组件 Stories |
| 指南文档 | `docs/DEPLOY.md`, `docs/OPERATIONS.md`, `docs/USER_GUIDE.md`, `docs/MONITORING.md` |
| 日志系统 | `app/dashboard/utils/logging_setup.py` — 旋转文件日志 |
| 错误追踪 | Sentry SDK 集成（可选，`SENTRY_DSN` 激活） |

### ✅ Phase 7 验证检查点
**目标**：系统可在目标环境生产部署，文档足以让新人从零上手  
**验证方式**：
- `python run_dashboard.py --env=production` → 生产模式启动成功，无调试信息泄露
- 备份脚本正常执行（`data/dashboard.db` 有备份文件产生）
- 打开 Swagger/OpenAPI 文档页面 → 所有端点有描述、有请求示例
- 按 README 部署指南从零操作一遍（最好由未参与开发的人操作）→ 能成功启动完整系统  

**合格标准**：生产环境和开发环境均可独立启动；文档无缺失步骤

---

## 🗂️ 文件结构规划

```
zowsup-cli/
├── app/
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py           # Flask 路由
│   │   │   ├── websocket.py        # WebSocket 事件处理
│   │   │   └── sse.py              # SSE 端点
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── chat_message.py
│   │   │   ├── ai_thought.py
│   │   │   ├── user_profile.py
│   │   │   ├── strategy.py
│   │   │   └── daily_stat.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── profile_analyzer.py    # 用户画像分析
│   │   │   ├── strategy_manager.py    # 策略管理
│   │   │   └── statistics_service.py  # 统计服务
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── db_init.py            # 数据库初始化
│   │   │   └── migrations.py         # 数据库迁移
│   │   └── config.py                 # 配置文件
│   ├── ai_module/
│   │   └── ai_service.py             # 修改支持思考记录
│   └── zowbot_layer.py               # 修改支持思考记录保存
│
├── dashboard-frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ContactList.jsx
│   │   │   ├── ChatHistory.jsx
│   │   │   ├── UserProfile.jsx
│   │   │   ├── StatisticsPanel.jsx
│   │   │   ├── StrategyPanel.jsx
│   │   │   └── common/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   └── GlobalStrategy.jsx
│   │   ├── services/
│   │   │   ├── api.js              # API 服务层
│   │   │   ├── websocket.js        # WebSocket 管理
│   │   │   └── sse.js              # SSE 管理
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js
│   │   │   ├── useSSE.js
│   │   │   └── useDashboardState.js
│   │   ├── store/
│   │   │   ├── index.js            # Redux 配置
│   │   │   ├── slices/
│   │   │   │   ├── contactsSlice.js
│   │   │   │   ├── chatSlice.js
│   │   │   │   ├── profileSlice.js
│   │   │   │   └── statisticsSlice.js
│   │   │   └── middleware/
│   │   ├── styles/
│   │   │   ├── index.css
│   │   │   └── theme.css
│   │   ├── utils/
│   │   │   ├── constants.js
│   │   │   └── helpers.js
│   │   ├── App.jsx
│   │   └── index.jsx
│   ├── package.json
│   └── .env.example
│
├── tests/
│   ├── unit/
│   │   ├── test_profile_analyzer.py
│   │   ├── test_strategy_manager.py
│   │   └── test_api_endpoints.py
│   ├── integration/
│   │   ├── test_websocket.py
│   │   └── test_sse.py
│   └── e2e/
│       └── dashboard.spec.js
│
└── docs/
    ├── API.md
    ├── DEPLOYMENT.md
    ├── USER_GUIDE.md
    └── ARCHITECTURE.md
```

---

## 📊 时间估算

| Phase | 内容 | 任务数 | 预计时间 | 验证检查点 | 优先级 |
|-------|------|--------|---------|-----------|--------|
| Phase 1 | 数据库 + Flask API | 17 | 2周 | `curl /api/health` 返回 200，DB 表已创建 | 🔴 高 |
| Phase 2 | AI数据管道 + 用户画像 | 22 | 3周 | `/api/user-profile` 返回真实计算数据 | 🔴 高 |
| Phase 3 | 策略引擎 | 15 | 2周 | 策略生效，bot 回复遵循策略 | 🔴 高 |
| Phase 4 | 实时通信 + React前端 | 61 | 5周 | 浏览器看到完整 Dashboard + 实时更新 | 🟠 中 |
| Phase 5 | 集成测试 + 优化 | 15 | 1周 | 所有测试通过，P95 < 200ms | 🟡 低 |
| Phase 6 | 部署 + 文档 | 13 | 1周 | 生产启动成功，文档可跟随操作 | 🟡 低 |
| **总计** | - | **143** | **14-15周** | - | - |

---

## 🚀 快速启动建议

**如果时间紧张，优先顺序（按新编号）：**
1. Phase 1（数据库 + Flask API）- **必须**，是所有后续工作的基础
2. Phase 2（AI数据管道 + 用户画像）- **必须**，核心功能数据链路
3. Phase 3（策略引擎）- **重要**，提供策略管理能力
4. Phase 4 前半段（WebSocket/SSE 后端 + React 框架 + 左/中/右三面板）- **重要**
5. Phase 4 后半段（统计面板、全局策略页、图表）- **支持**
6. Phase 5 + Phase 6（测试和部署）- **可后续**

**MVP 版本 (7-8周):**
- 完成 Phase 1-3（全部后端功能）
- 完成 Phase 4 的左/中/右三面板 + WebSocket 实时推送
- 基础统计面板（可暂无 Heatmap 和 ECharts 图表）
- 跳过 E2E 测试和 Docker 容器化

---

## 📝 注意事项

1. **数据库迁移**: 历史数据来源是账号专属 `db.db` 的 `ai_memory` 表，不是日志文件；迁移前先备份
2. **进程隔离**: Flask 进程只能读 `dashboard.db`，bot 进程写；**禁止**在 Flask 代码里 import 任何 bot 模块（防止 asyncio event loop 冲突）
3. **SQLite WAL**: 必须在初始化时设置 WAL 模式，否则高频写入时 Flask 会频繁遇到 `database is locked`
4. **Breaking Change**: Phase 2 修改 `process_message()` 返回值时必须先更新所有调用方，否则 bot 立即崩溃
5. **策略通知机制**: Phase 4 开始前必须确定 Flask → bot 策略变更通知方案（轮询/文件/HTTP），否则策略引擎无法联调
6. **API 认证**: 5.17 必须实现，不可跳过
7. **性能**: 大量消息场景下前端需要虚拟化列表（6.22）
8. **测试覆盖**: 至少80%的核心业务逻辑
9. **文档**: API 文档需要及时更新

---

**更新日期**: 2026-04-28  
**负责人**: (待指定)  
**上次更新**: v1.1 - 架构决策确认（独立 dashboard.db / 单账号 / Flask 独立进程），修正数据迁移方向，新增 WAL 模式/进程隔离/Breaking Change 等关键任务，修正时间估算为 13-15 周
