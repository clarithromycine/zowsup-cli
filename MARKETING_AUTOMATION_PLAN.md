# 自动化营销功能开发计划

> 版本：v1.2 | 日期：2026-05-13

---

## 一、系统目标

在现有 WhatsApp Bot 基础上，构建一套 **AI 驱动的自动化营销系统**，覆盖从客户引流承接、全程 AI 沟通、到销售漏斗分析的完整链路。

---

## 二、核心概念定义

### 营销任务手册 (Playbook)
一个 Playbook 绑定一个 Bot 实例的全生命周期目标。同一时刻只有一个处于 `active` 状态（全局默认），但导入联系人时可为其指定特定 Playbook 覆盖默认值。

包含字段：
- 营销目标描述
- SOP 步骤树（自定义阶段列表，JSON 数组）
- 产品信息列表
- FAQ（常见问题与回答）
- 禁忌话题 + 话术
- 注入 AI 的 system prompt 模板
- **可用工具列表 `available_tools`**（AI 被授权执行的动作集合，详见"架构决策"章节）

### 客户 (Contact)
以 WhatsApp JID 为唯一标识的自然人。拥有静态基础信息（导入时填写）和动态画像（AI 驱动更新）。

### 客户画像 (Profile)
附属于 Contact 的结构化标签集合，由 AI 在每次对话后自动更新。包含：
- 需求痛点
- 意向度评分（0.0 ~ 1.0）
- 偏好与背景信息
- 需人工介入的问题列表

### 销售阶段 (Stage)
每个 Playbook 定义自己的阶段列表（完全自定义，不硬编码）。Contact 在某个 Playbook 下有且仅有一个当前 Stage，AI 判断是否推进，人工可手动调整。

### 投流用户识别
用户从其他渠道（FB广告、短信、线下活动）看到引流后**主动来加 Bot**，Bot 通过手机号匹配已导入的联系人，加载其背景信息和对应 Playbook，实现个性化承接。

---

## 三、现有系统能力评估

| 模块 | 现状 | 评级 |
|------|------|------|
| WhatsApp 收发消息 | 完整，支持文本/媒体/扩展文本 | ✅ 可直接复用 |
| AI 对话引擎 | GLM/QWEN 双后端，含记忆、重试、过滤 | ✅ 可扩展 |
| `StrategyManager` | 控制语气/风格/语言/system prompt | ⚠️ 需升级为 Playbook |
| `ConversationMemory` | 每用户对话历史，SQLite 存储 | ⚠️ 需扩展客户画像字段 |
| `AIThought` / `models.py` | 记录 intent/tone/strategy 等结构化推理 | ⚠️ 需扩展销售阶段判断 |
| `Materials` 系统 | 管理素材/文件/模板 | ⚠️ 需升级为产品信息+FAQ结构 |
| Dashboard 前端 | React 多页面，已有 Strategy/Materials 页 | ⚠️ 需新增 CRM 页 |
| Dashboard 后端 | Flask Blueprint 架构，Bearer Auth，SQLite | ✅ 架构稳定，可新增 BP |
| 主动发消息 | 目前只有被动回复 | ❌ 核心缺口（Phase G 实现） |
| 客户联系人管理 | 无任何数据模型 | ❌ 核心缺口，需新建 |
| 销售漏斗 / 阶段模型 | 无 | ❌ 需新建 |

---

## 四、数据库架构（新增部分）

```
dashboard.db（现有，新增表）
├── playbooks              — 营销任务手册
├── contacts               — 客户联系人基础信息
├── contact_profiles       — AI 驱动的客户画像（按 playbook 维度）
├── contact_stage_history  — 阶段变更日志
└── campaign_tasks         — 主动外呼任务队列（Phase G）

（现有表保持不变）
├── strategy_applications  — 通用策略（Playbook 激活后优先级低于 playbook）
├── ai_thoughts            — AI 推理记录（新增 stage_assessment 字段）
├── chat_messages          — 对话记录（新增 contact_jid 外键）
└── materials              — 素材库（产品信息可复用）
```

### contacts 表关键字段
```json
{
  "jid": "60123456789@s.whatsapp.net",
  "phone": "60123456789",
  "display_name": "潜在客户A",
  "source": "fb_ad",
  "source_campaign": "5月促销活动",
  "initial_notes": "点击了产品B的广告，填写了表单，表示对价格敏感",
  "tags": ["高意向", "价格敏感"],
  "assigned_playbook_id": 3
}
```

---

## 五、开发阶段规划

> **原则**：每个 Phase 完成后必须有一个具体的人工验证方法，验证通过才能进入下一个 Phase。

---

### Phase 1 — 数据库建表 & 基础数据结构

**目标**：建立所有新功能依赖的数据库表结构，不涉及任何业务逻辑。

**工作内容**：
- 在 `dashboard.db` 新增表：`playbooks`、`contacts`、`contact_profiles`、`contact_stage_history`
- `AIResult` / `models.py` 扩展：新增 `actions: List[dict]` 字段（初期为空列表，为后续工具调用预留）
- 数据库迁移脚本：`app/marketing/db_init.py`，幂等执行（已存在则跳过）

**验证方法**：
```bash
python -c "from app.marketing.db_init import init_marketing_tables; init_marketing_tables()"
# 然后用 sqlite3 打开 dashboard.db，执行 .tables 命令
# 预期输出包含：playbooks  contacts  contact_profiles  contact_stage_history
```

---

### Phase 2 — Playbook 后端 API

**目标**：Playbook 的完整 CRUD + 激活逻辑，纯后端，不涉及前端。

**工作内容**：
- `app/marketing/playbook.py`：PlaybookManager 类，含 create / update / delete / activate / get_active
- Flask Blueprint：`GET/POST /api/playbooks/`、`PUT/DELETE /api/playbooks/<id>`、`POST /api/playbooks/<id>/activate`
- 激活逻辑：同时只有一个 `is_active=1`，激活新的自动将旧的置为 inactive
- Playbook 数据结构包含 `available_tools` 字段（JSON 数组）

**验证方法**：
```bash
# 用 curl 或 Postman 执行：
POST /api/playbooks/  {"name": "测试手册", "goal": "销售产品A", ...}
POST /api/playbooks/1/activate
GET  /api/playbooks/  → 确认 id=1 的 is_active=true，其余为 false
```

---

### Phase 3 — Playbook 前端页面

**目标**：在 Dashboard 中可视化管理 Playbook，操作结果实时反映到后端。

**工作内容**：
- 新增 `PlaybookPage.tsx`
- 列表视图：显示所有 Playbook + 当前激活状态 + 激活/停用按钮
- 编辑器：分 Tab（目标描述 / SOP阶段 / 产品列表 / FAQ / 禁忌话题 / 可用工具）
- 预览区：实时显示该 Playbook 生成的 system prompt 样本

**验证方法**：
- 浏览器打开 Dashboard → PlaybookPage
- 创建一个 Playbook，填写目标描述和两条 FAQ
- 点击激活，确认页面上状态变为"激活中"
- 刷新页面，状态保持（持久化验证）
- 点击"预览 System Prompt"，确认文本中包含刚填写的目标描述和 FAQ 内容

---

### Phase 4 — Playbook 注入 AI 对话

**目标**：激活的 Playbook 内容自动注入每次 AI 对话的 system prompt。

**工作内容**：
- `StrategyManager.build_system_prompt()` 读取当前激活 Playbook，将目标描述 + SOP摘要 + 产品简介 + 禁忌 注入 prompt
- `AIService` 初始化时加载 active Playbook，对话过程中使用
- Playbook 更新后下一次对话生效（无需重启 Bot）

**验证方法**：
- 激活一个包含特定目标描述（例如"专注销售马来西亚保险产品"）的 Playbook
- 用测试号发一条消息给 Bot
- 在 Dashboard 的对话记录中查看 `ai_thoughts.raw_thought`，确认 AI 的推理过程中出现了 Playbook 中的关键词
- 修改 Playbook 内容后再发一条消息，确认新内容生效

---

### Phase 5 — 联系人后端 API

**目标**：联系人数据的完整 CRUD + CSV 批量导入，纯后端。

**工作内容**：
- `app/marketing/contacts.py`：ContactManager 类
- `POST /api/contacts/import`：支持单条 JSON + CSV 文件上传（自动解析手机号、来源、初始备注）
- `GET /api/contacts/`：列表，支持 `?stage=&source=&tag=` 过滤
- `GET/PUT/DELETE /api/contacts/<jid>`
- CSV 格式规范：`phone, display_name, source, source_campaign, initial_notes, tags, assigned_playbook_id`

**验证方法**：
```bash
# 准备一个 3 行的 contacts.csv，POST 到导入接口
POST /api/contacts/import  (multipart, file=contacts.csv)
# 返回 {"imported": 3, "skipped": 0, "errors": []}
GET  /api/contacts/  → 确认返回 3 条记录，字段完整
GET  /api/contacts/6012345678@s.whatsapp.net  → 确认单条数据正确
```

---

### Phase 6 — 联系人前端页面

**目标**：在 Dashboard 中可视化管理联系人，支持批量导入。

**工作内容**：
- 新增 `ContactsPage.tsx`
- 列表视图：显示 JID / 姓名 / 来源 / 当前阶段 / 意向分 / 最后互动时间
- 搜索 + 过滤（按来源活动、按阶段、按标签）
- CSV 批量导入：拖拽上传 + 预览解析结果 + 确认导入
- 单条联系人详情抽屉：显示基础信息和初始备注

**验证方法**：
- 打开 Dashboard → ContactsPage
- 拖拽上传一个 CSV 文件，确认预览正确显示解析结果
- 点击确认导入，列表刷新出现新联系人
- 点击任意联系人，抽屉显示完整基础信息
- 在搜索框输入手机号，确认过滤正确

---

### Phase 7 — ContactMatcher（投流用户识别）

**目标**：Bot 收到新消息时，自动用手机号匹配已导入联系人，加载其背景和对应 Playbook。

**工作内容**：
- `app/marketing/contact_matcher.py`：`match_by_phone(jid) → Contact | None`
- 在 `zowbot_layer.py` 消息处理入口，接收消息后先调用 `ContactMatcher`
- 命中时：将联系人的 `initial_notes` + `source_campaign` 注入本次对话的 system prompt 前缀；加载 `assigned_playbook_id` 对应的 Playbook（覆盖全局默认）
- 未命中时：走全局 active Playbook，正常流程

**验证方法**：
- 在 Dashboard 导入一个联系人：手机号 `601XXXXXXXX`，initial_notes = `"已发5月促销短信，对A产品感兴趣"`
- 用该手机号对应的 WhatsApp 账号发消息给 Bot
- 查看 Dashboard 对话记录，确认 AI 的回复中自然体现了"A产品"或"促销"相关的上下文
- 再用一个**未导入**的号码发消息，确认 AI 走普通回复流程，没有任何联系人背景信息

---

### Phase 8 — AI 多层推理管道 & 结构化输出框架

**目标**：将 `AIService` 从单次 LLM 调用重构为三层专职管道（L1/L2/L3），同时在 L3 引入结构化工具调用输出。详细架构见「决策四」。本 Phase 只建立管道骨架——ActionExecutor 用占位日志代替真实执行，L2 仅在复杂消息时触发。

**工作内容**：

**L1 — ContextAssembler**（`app/ai_module/context_assembler.py`，新建）：
- 整合 `ConversationMemory` 查询 + `ContactMatcher` 匹配，统一输出 `ContextBundle` dataclass
- 计算 `message_complexity`（0.0~1.0）：问候/确认→低，含异议/多意图/陌生用户→高
- 关键字段：`message_complexity`、`recent_turns`、`contact_profile`、`active_playbook`、`relevant_snippets`

**L2 — IntentAnalyzer**（`app/ai_module/intent_analyzer.py`，新建）：
- 使用轻量模型（GLM-4-Flash / Qwen-Turbo），单次调用，输出 `IntentAnalysis` dataclass
- 关键字段：`intent_type`、`detected_needs`、`info_gaps`、`recommended_sop_step`、`confidence`
- 结果写入 `ai_thoughts` 表（新增列）

**L3 — ResponseGenerator**（改造现有 `AIService` 核心）：
- 输入接口改为 `(user_message, context: ContextBundle, intent: IntentAnalysis)`
- GLM / Qwen 后端统一包装 `tool_call` 接口，差异不暴露给上层
- 解析结构化输出，填充 `AIResult.actions`

**路径路由器**（在 `AIService.process_message()` 入口）：
- `complexity < 0.4` → 快速路径（跳过 L2，`intent` 传入 `IntentAnalysis.empty()`）
- `complexity ≥ 0.4` → 深度路径（L1 → L2 → L3 顺序执行）

**ActionExecutor 框架**（`app/marketing/action_executor.py`，新建）：
- 根据 `action.type` 分发；本 Phase 全部 action 走 `log_only` 占位，打印到日志

**验证方法**：

验证一（快速路径）— 发一条简单问候 "你好"：
```
预期日志出现：[ContextAssembler] complexity=0.1x → fast path
预期日志不出现：[IntentAnalyzer]（确认 L2 被跳过）
预期日志出现：[ResponseGenerator] reply generated
```

验证二（深度路径 + 结构化输出）— 发 "我想买，怎么付款"：
```
预期日志出现：[ContextAssembler] complexity=0.8x → deep path
预期日志出现：[IntentAnalyzer] intent_type=buying_signal, confidence=0.9x
预期日志出现：[ActionExecutor] log_only: {"type": "update_stage", "stage": "qualified"}
```

验证三：两次测试的 AI 文字回复均正常到达用户 WhatsApp（管道重构不破坏对话基础功能）

---

### Phase 9 — AI 画像自动更新

**目标**：对话后 AI 自动更新联系人的画像（意向分、痛点、阶段），并激活 `update_stage` / `update_profile` 工具调用。

**工作内容**：
- `ProfileUpdater`：每 N 条消息触发一次，以对话摘要 + 当前画像 + Playbook 阶段标准为输入，调用 LLM 输出结构化更新
- `ActionExecutor` 实现 `update_stage`：写入 `contact_profiles.stage` + 追加 `contact_stage_history` 记录
- `ActionExecutor` 实现 `update_profile`：更新 `pain_points_json`、`intent_score`、`background_json`
- `ActionExecutor` 实现 `escalate_human`：设置 `needs_human=true`，暂停 AI 自动回复

**验证方法**：
- 用已导入联系人的号码与 Bot 进行 5 轮对话，内容涉及产品兴趣
- 打开 Dashboard → 联系人详情，确认：
  - `intent_score` 数值发生了变化
  - `stage` 字段更新为符合对话内容的阶段
  - `contact_stage_history` 出现了一条变更记录
- 发一条 Bot 无法回答的消息（例如"给我你们老板的个人电话"），确认 `needs_human` 被设置为 true，AI 停止回复

---

### Phase 10 — AI-CRM 列表视图

**目标**：CRM 页面的联系人列表，展示所有联系人的最新营销状态。

**工作内容**：
- `GET /api/crm/contacts`：返回联系人列表，含当前阶段、意向分、最后互动时间、needs_human 标记
- 新增 `CRMPage.tsx`（列表视图部分）
- 列显示：姓名 / 来源活动 / 当前阶段 / 意向分（进度条） / 最后互动时间 / 人工介入标记
- 支持按阶段、来源过滤

**验证方法**：
- 打开 Dashboard → CRMPage
- 确认列表显示已对话的联系人，字段正确
- 过滤"需人工介入"，确认只显示 `needs_human=true` 的联系人
- 按阶段过滤，确认结果正确

---

### Phase 11 — AI-CRM 联系人详情 & 漏斗视图

**目标**：联系人完整画像页面 + 销售漏斗图。

**工作内容**：
- 联系人详情页：基础信息 + AI 画像摘要 + 完整对话时间线 + 阶段变更历史 + 手动调整阶段入口
- `GET /api/crm/funnel?playbook_id=<id>`：按阶段统计人数、平均停留时长
- 漏斗视图：各阶段人数柱状图/漏斗图 + 转化率，支持按来源活动筛选
- `POST /api/crm/<jid>/stage`：人工手动修改阶段

**验证方法**：
- 点击 CRM 列表中任意联系人，详情页正确显示对话时间线和阶段历史
- 手动修改某联系人阶段，确认 `contact_stage_history` 记录变更人为"human"
- 漏斗视图中各阶段人数与 contacts 表实际数据一致（手动用 SQL 核对）
- 按某个来源活动筛选漏斗，确认只显示该活动的联系人

---

### Phase 12 — 人工介入机制

**目标**：人工从 Dashboard 直接接管对话、发消息、将处理方式沉淀回 Playbook。

**工作内容**：
- `POST /api/crm/<jid>/human-reply`：从 Dashboard 向用户发消息（调用 zowbot_layer 发送接口）
- `POST /api/crm/<jid>/resolve`：标记已处理 + 写入 Playbook（可选追加到 FAQ / 禁忌 / SOP 某字段）+ 恢复 AI
- 介入界面：对话记录（只读）+ 发消息输入框 + "记录处理方式"对话框

**验证方法**：
- 触发一个 `needs_human=true` 的联系人
- 在 Dashboard 介入界面输入一条消息并发送，确认目标号码的 WhatsApp 收到了这条消息
- 填写"处理方式"并选择追加到 FAQ，确认 Playbook 的 FAQ 字段新增了该条目
- 点击"恢复 AI"，再向 Bot 发一条消息，确认 AI 恢复自动回复

---

### Phase G — 主动外呼（可选，后期设计）

**适用场景**：高转化意愿的特定客群（博彩、游戏福利、限时活动），需运营人员手动圈定名单并审核后触发，绝不自动批量运行。

**包含模块**：
- 任务调度器（`campaign_tasks` 队列）
- 主动发消息接口（`send_proactive_message`）
- 限速/防封号机制（随机发送间隔、单日上限、优先已互动联系人）

---

## 六、关键风险点

| 风险 | 说明 | 建议 |
|------|------|------|
| WhatsApp 主动外呼封号 | Phase G 风险最高 | 严格限速，运营审核，小规模测试 |
| AI 画像更新 token 成本 | 高频更新消耗大 | 批量更新 + 轻量模型做画像分析 |
| SQLite 并发写 | 多并发写场景 | WAL 模式 + 异步写队列 |
| 阶段定义灵活性 | 不同产品销售阶段差异大 | Playbook 的阶段列表完全自定义 JSON |
| 单 Bot 多 Playbook 路由 | 不同客群需要不同手册 | `assigned_playbook_id` 在联系人级别覆盖全局默认 |

---

## 七、依赖关系图

```
Phase 1  (数据库建表)
  → Phase 2  (Playbook 后端 API)
      → Phase 3  (Playbook 前端页面)
          → Phase 4  (Playbook 注入 AI 对话)
  → Phase 5  (联系人后端 API)
      → Phase 6  (联系人前端页面)
      → Phase 7  (ContactMatcher)      ← 依赖 Phase 1+2+5
          → Phase 8  (AI 多层管道 + 结构化输出框架)  ← 依赖 Phase 4+7
              → Phase 9  (AI 画像自动更新)
                  → Phase 10 (CRM 列表视图)
                      → Phase 11 (CRM 详情 & 漏斗)
                          → Phase 12 (人工介入机制)
──────────────────────────────────────────────────
Phase G  (主动外呼，可选)              ← 依赖 Phase 1-12 全部完成
```

---

## 八、关键架构决策（编码前锁定）

以下三个决策影响多个 Phase 的数据结构，必须在 Phase A 编码前确认，避免后期重构。

---

### 决策一：投放模式 — 精准名单投放（非广播式 CTWA）

本系统的投流模式是**精准名单投放**：预先持有目标用户的电话号码，针对这批号码发送短信/定向广告，用户主动进入 WhatsApp 对话后系统已知其完整背景。

```
已有电话号码名单
    → 针对这批号码发短信 / WhatsApp模板消息 / FB定向广告
    → 导入时标注"已发 5月促销短信"+ 其他初始背景
    → 用户主动发消息时，系统在第一条回复前就已拥有完整上下文
```

**这比官方 CTWA referral 对象更强**：官方方案只能在用户点击广告后才知道广告 ID，本系统在用户开口前就已有完整背景。

因此，`contacts` 表的 `source` / `source_campaign` / `initial_notes` 字段由**导入时填写**，不依赖任何自动归因机制。这是非官方协议限制下的最合理解法，也是本系统的正确使用姿势。

---

### 决策二：AI 结构化输出（MCP 式工具调用架构）

AI 的输出从纯文本升级为**结构化的"回复文本 + 可选动作"**：

```json
{
  "reply_text": "好的，这是我们的产品介绍，请查收",
  "actions": [
    { "type": "send_document", "params": { "material_id": "brochure_v2" } }
  ]
}
```

```json
{
  "reply_text": null,
  "actions": [
    { "type": "escalate_human", "reason": "用户要求具体报价，超出 AI 授权范围" }
  ]
}
```

```json
{
  "reply_text": "明白了，我已为您记录",
  "actions": [
    { "type": "update_stage", "stage": "qualified" }
  ]
}
```

**架构含义**：

| 层 | 改造内容 |
|----|---------|
| **Playbook** | 新增 `available_tools` 字段，声明该 Playbook 允许 AI 执行的动作集合 + 每个工具的触发描述，注入 system prompt |
| **LLM 后端** | GLM / Qwen 均支持 function calling，统一包装为 `tool_call` 接口，后端差异不暴露给 `AIService` |
| **`AIResult` / `models.py`** | 从 `AIResult(text)` 扩展为 `AIResult(text, actions[])`，保持向后兼容 |
| **`ActionExecutor`（新模块）** | 接收 `actions[]`，调用 `zowbot_layer` 对应接口执行：发文件、发图片、推进阶段、触发人工介入、主动发消息等 |

**预定义 action type 清单（Phase A 时设计，后续扩展）**：

| action type | 说明 |
|-------------|------|
| `send_document` | 发送素材库中的文件/图片/视频 |
| `send_template` | 发送消息模板 |
| `update_stage` | 推进/回退联系人的销售阶段 |
| `update_profile` | 更新联系人画像字段 |
| `escalate_human` | 触发人工介入流程 |
| `schedule_followup` | 安排定时跟进（Phase G 实现） |

---

### 决策三：`AIResult` 结构从设计之初支持 `text + actions[]`

不先做纯文本再改造，从 Phase A 开始 `models.py` 就包含 `actions` 字段（初期可为空列表），为 Phase C/D' 的工具调用做好接口预留。

---

### 决策四：AI 推理管道——多层专职架构（非单次调用）

**背景**：现有 `AIService.process_message()` 是单次 LLM 调用，将记忆召回、意图理解、策略选择、响应生成全部压缩在同一个 prompt 里。每项职责都无法单独优化，问题追踪困难，context window 随对话轮次膨胀难以控制。现代 Code Agent（Cursor、Copilot Agent）的核心架构正是「多层专职」——规划层不生成代码，执行层不做规划，各层独立调优。本系统采用相同思路。

**三层管道结构**：

```
用户消息
  ↓
[L1: 上下文组装层]  — 无 LLM，纯 DB 查询 + 记忆检索
    · 从 ConversationMemory 召回相关片段（最近 N 轮 + 关键词相关片段）
    · 加载联系人画像 / Playbook / 当前销售阶段
    · 计算 message_complexity 分值（决定走快速或深度路径）
    输出 → ContextBundle（结构化 dataclass）
  ↓
[L2: 意图与需求分析层]  — 轻量 LLM（深度路径触发；快速路径跳过）
    · 意图分类：buying_signal | objection | question | chitchat | complaint | off_topic
    · 识别用户已透露的痛点 / 需求
    · 标记信息缺口（AI 下一步应主动探问的方向）
    · 对齐 Playbook SOP：当前对话属于哪一步？
    输出 → IntentAnalysis（持久化到 ai_thoughts 表）
  ↓
[L3: 响应生成层]  — 主力 LLM
    · 输入：用户消息 + ContextBundle + IntentAnalysis
    · 持有完整工具调用权限（available_tools 注入 system prompt）
    · 职责单一：生成回复 + 输出动作，不再兼顾意图推断
    输出 → AIResult { reply_text, actions[] }
```

**路径分流规则**：

| 条件 | 路径 | 目标延迟 |
|------|------|----------|
| `message_complexity < 0.4`（问候、单一问题、是/否确认） | 快速路径：L1 → L3 | < 2s |
| `message_complexity ≥ 0.4`（异议、多意图混合、首次接触） | 深度路径：L1 → L2 → L3 | < 5s |

**与现有模块的映射**：

| 新组件 | 对应现有代码 | 变化方向 |
|--------|------------|----------|
| `ContextAssembler` | `ConversationMemory` + `ContactMatcher` | 整合为统一查询入口，结构化输出 ContextBundle |
| `IntentAnalyzer` | `AIThought` 中混合的意图判断部分 | 独立为单次轻量 LLM 调用，专职分析 |
| `ResponseGenerator` | `AIService.process_message()` 核心 | 职责收窄为「仅生成回复 + 动作」 |
| `IntentAnalysis` | `AIThought` 扩展字段 | 新增 intent_type / info_gaps / recommended_sop_step 等字段 |

**成本控制**：L1 零 LLM 成本；L2 使用低成本模型（GLM-4-Flash / Qwen-Turbo）；仅 L3 使用高能力模型。整体 token 消耗与原来基本持平，但回复质量更高，出错时可精确定位到具体层。

---

## 九、竞争力评估摘要

### 真实优势
- **零 Meta 消息费**：竞品全部基于官方 API，按对话收费；本系统绕过该层
- **灰色/受限行业的唯一选项**：博彩、成人、高息金融等行业被竞品平台拒绝服务
- **私有部署 + 数据主权**：数据不经过第三方 SaaS
- **精准名单模式**：比官方 CTWA 归因更强的上下文控制
- **知识沉淀闭环**：人工介入 → 写入 Playbook → AI 进化，而非消耗人力的 Team Inbox

### 核心风险
- **账号封禁**：非官方协议，Meta 持续加强检测，这是最大生死风险
- **目标客群（灰色行业）账号生命周期短**：需要设计账号池和快速恢复机制
- **AI 能力差距收窄**：竞品已上线 AI Agents，本系统的 AI 深度优势窗口期有限

### 战略建议
产品差异化建立在"非官方协议 + 灰色行业 + 私有部署"组合上。如未来需服务合规企业，考虑提供基于官方 Business API 的版本，两个版本共享同一套 AI/CRM/Playbook 内核，仅底层通信层不同。

