# AI 技术动态监控系统 - 项目蓝图（Codex Agent）

## 1. 产品概述
构建自动化 AI Agent，定期抓取高质量 AI 内容，进行智能筛选与结构化总结，并推送日报。

## 2. 用户画像
- AI 技术专家
- 软件工程师
- 科技投资者

核心痛点：信息噪声高、追踪前沿突破耗时。

## 3. 技术架构（Codex Agent 优先）

### Phase 1: MVP（快速上线）
流程：
1. 定时触发（Cron）
2. 数据采集（RSS + GitHub API）
3. 规则预筛（白名单/黑名单/时间窗/去重）
4. LLM 单次调用输出结构化结果（相关性 + 摘要）
5. 入库（可选）
6. 日报推送（Email/Slack/飞书）

### Phase 2: Agent（深度洞察）
- 引入工具调用：GitHub Repo 质量检测、网页正文抽取、检索增强
- 进行项目背调：活跃度、代码可信度、社区信号
- 输出“是否值得跟进”的决策建议

## 4. 数据源（初版）
- OpenAI Blog (RSS)
- Anthropic Blog (RSS)
- Hugging Face Blog (RSS)
- Papers with Code (RSS)
- GitHub Trending/Search (Python + AI)

## 5. LLM 输出规范（必须 JSON）
每条内容输出字段：
- `is_relevant` (bool)
- `relevance_score` (0-100)
- `novelty_score` (0-100)
- `actionability_score` (0-100)
- `category` (string)
- `summary_cn` (string)
- `key_points` (string[])
- `project_links` (string[])

## 6. 评分与排序
推荐总分：
`total_score = 0.45 * relevance + 0.30 * novelty + 0.25 * actionability`

## 7. 非功能要求
- Security：API Key 仅通过环境变量注入
- Reliability：失败重试 + 降级输出（至少发送原始高分链接）
- Privacy：仅个人使用，不公开抓取结果

## 8. 里程碑
- M1（1-2天）：抓取 + 去重 + 基础推送
- M2（3-5天）：LLM 结构化筛选 + 排序
- M3（1周）：稳定运行 + 指标看板
- M4（2周+）：Agent 深度背调

## 9. 开发约定（Codex Agent）
- 优先小步提交、可运行优先
- 每个阶段都保留可回滚版本
- 所有 Prompt 与 Schema 放在版本控制中

## 10. 下一步
1. 初始化 `phase1_rss` 的抓取脚本与配置文件
2. 先跑 3 个数据源做 MVP 验证
3. 补齐 GitHub Actions 定时与告警

## 11. 文档入口
- 项目总览与快速启动：`README.md`
- 开发步骤与执行手册：`docs/DEVELOPMENT_GUIDE.md`
- 架构记录与设计决策：`docs/ARCHITECTURE.md`
