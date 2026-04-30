# AI 客服对话系统优化计划

> 每个 Phase 完成后均可独立验证，验证通过后再开始下一个 Phase。

---

## Phase 1 — 满意度收集 ✅ DONE

**目标**：AI 回复后沉默一段时间，自动发送满意度询问，并将 1-5 分结果写入 `user_profiles.satisfaction_score`。

**实现范围**：
- `conf/config.conf.example` — 新增 `[AI_SATISFACTION]` 配置节
- `app/zowbot_layer.py` — 新增满意度状态跟踪、定时任务、评分写入方法
  - `_sat_state: dict` — per-user 状态（last_ai_reply、asked、waiting）
  - `_satisfaction_timer_task()` — 每 30s 轮询，超时发送问卷
  - `_is_satisfaction_reply()` / `_handle_satisfaction_reply()` — 拦截并处理评分消息
  - `_record_ai_reply()` — AI 回复后重置计时器
  - `_write_satisfaction_score()` — EMA 写入 `user_profiles.satisfaction_score`
  - `onMessage` — 集成拦截逻辑 + AI 回复后 record

**验证方法**：
```
1. 启动 bot，向 bot 发送一条普通消息，收到 AI 回复
2. 修改 config.conf 将 timeout_minutes = 1（测试用）
3. 等待约 1 分钟，bot 应自动发来满意度询问消息
4. 回复 "4"
5. 查询：SELECT satisfaction_score FROM user_profiles WHERE user_jid='<你的jid>';
   应出现 0.8000（4/5）
6. bot 应自动回复感谢语
```

---

## Phase 2 — 上下文轮数可配置 ✅ DONE

**目标**：把 hardcode 的 `[-10:]` / `days=3` 改为从 Strategy 配置读取。

**实现范围**：
- `app/dashboard/strategy/strategy_manager.py` — 新增 `context_turns`（默认 10）、`context_days`（默认 3）字段
- `app/ai_module/ai_service.py` — `get_recent_memory` 和截取改为读合并策略
- `dashboard-frontend/src/pages/StrategyPage.tsx` — 表单增加「上下文轮数」「记忆天数」两个 InputNumber

**验证方法**：
```
1. 通过 Dashboard 将某用户策略 context_turns 改为 3
2. 与 bot 完成 5 轮对话
3. 开启 debug 日志，观察第 6 条消息发出的 LLM 请求 payload
4. messages 数组中历史条数 ≤ 3 ✓
```

---

## Phase 3 — 紧急程度标签 + 意图→策略自动匹配 ✅ DONE

**目标**：将 intent 检测反馈回策略；新增 urgency_level 标签。

**实现范围**：
- `app/dashboard/utils/migrations.py` — `ai_thoughts` 表新增 `urgency_level TEXT` 列
- `app/ai_module/ai_service.py` — `_build_thought()` 检测紧急关键词写 `urgency_level`；新增 `_auto_adjust_strategy()` 临时注入
- `dashboard-frontend` — ChatHistory 展示 urgency 徽标

**验证方法**：
```
1. 发送含"急"/"urgent"的消息
   → SELECT urgency_level FROM ai_thoughts ORDER BY id DESC LIMIT 1; 应为 'high'
2. 连发 3 条 support 类消息
   → 第 3 条 ai_thoughts.tone 应为 'empathetic'
3. Dashboard ChatHistory 展示 urgency 标记 ✓
```

---

## Phase 4 — 长期用户画像自动积累 ✅ DONE

**目标**：从每轮 ai_thoughts 自动归纳用户偏好，写入 user_profiles，不依赖二次 LLM 调用。

**实现范围**：
- `app/ai_module/ai_service.py` — 成功回复后调用 `_update_user_profile()`
  - `topic_preferences` 累加 detected_keywords
  - `communication_style` 从 tone 历史推断
  - `user_category` 基于 total_interactions + satisfaction_score
- `user_profiles.trend_7d/trend_30d` — daily_cleanup 时顺带更新

**验证方法**：
```
1. 与 bot 完成 6 轮对话
2. SELECT user_category, topic_preferences, communication_style
   FROM user_profiles WHERE user_jid='<你的jid>';
   应出现非空的合理值
3. Dashboard UserProfile 页面标签自动更新 ✓
```

---

## 优先级与状态总览

| Phase | 描述 | 难度 | 用户价值 | 状态 |
|---|---|---|---|---|
| 1 | 满意度收集 | 低 | 高 | ✅ DONE |
| 2 | 上下文轮数可配置 | 低 | 中 | ✅ DONE |
| 3 | 意图→策略自动匹配 + urgency | 中 | 高 | ✅ DONE |
| 4 | 用户画像自动积累 | 中 | 中 | ✅ DONE |
