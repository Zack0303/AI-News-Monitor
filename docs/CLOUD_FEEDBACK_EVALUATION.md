# CLOUD FEEDBACK EVALUATION

## 1. 目标
把当前本地 `localStorage` 反馈升级为跨设备、可统计、可追踪的云端反馈系统。

## 2. 当前方案（本地）
- 事件存于浏览器本地：`anm_feedback_events`
- 优点：零成本、上线快
- 缺点：无法跨设备、无法多人协作、统计不完整

## 3. 云端候选方案

### 方案 A：Supabase（推荐）
1. 技术栈
- Postgres + Row Level Security
- 前端直接调用 REST/SDK
- 可配合 Edge Functions 做聚合

2. 优点
- 上手快，文档成熟
- 数据模型清晰，SQL 查询强
- 免费层对早期项目够用

3. 风险
- 需要设计匿名用户策略与限流
- 需要处理 API key 暴露边界（仅公开 anon key）

### 方案 B：Cloudflare Worker + D1 / KV
1. 技术栈
- Worker 接收事件 API
- D1 或 KV 存储反馈

2. 优点
- 与静态站点集成自然
- 边缘网络延迟低
- 成本可控

3. 风险
- 需要自己维护更多后端逻辑
- 统计分析能力不如 SQL 直观

### 方案 C：Firebase
1. 技术栈
- Firestore + Cloud Functions

2. 优点
- 前端 SDK 成熟
- 实时能力强

3. 风险
- 成本模型在规模增长后需关注
- 查询模型和 SQL 思维不同

## 4. 推荐结论
短中期建议：`Supabase`

原因：
1. 反馈事件天然适合结构化存储与 SQL 聚合
2. 开发效率高，便于快速迭代模型权重
3. 成本和复杂度平衡较好

## 5. 数据模型建议
表：`feedback_events`
- `id` (uuid)
- `created_at` (timestamp)
- `item_id` (text)
- `title` (text)
- `source` (text)
- `href` (text)
- `label` (like/dislike/open)
- `client_id` (匿名设备 id)
- `session_id` (可选)

索引：
- `(created_at)`
- `(item_id, label)`
- `(source, label)`

## 6. 分阶段落地
1. Phase 1（最小可用）
- 仅接入事件写入 API
- 每日离线拉取事件，生成 `preference_profile.json`

2. Phase 2（增强）
- 增加实时看板（点赞率、来源偏好）
- 增加反作弊规则（频控、UA/IP 简单检测）

3. Phase 3（优化）
- 支持账号级偏好
- 支持人群分层画像（工程/产品/投资）

## 7. 安全与隐私
1. 不收集敏感个人信息
2. client_id 使用匿名随机 id
3. 对反馈 API 增加速率限制
4. 明确隐私说明（仅用于推荐优化）

