# PROJECT - AI-News-Monitor

## 1. 目标
构建一个“可持续运行”的 AI 技术情报产品：
- 自动抓取高价值信息
- 进行结构化筛选与排序
- 输出可执行中文简报

## 2. 目标用户
- AI 技术专家
- 软件工程师
- 科技投资者

核心问题：信息噪声高，人工筛选成本大。

## 3. 当前范围（MVP）
- 数据源：RSS + GitHub Search
- 分析模式：LLM / heuristic / fallback
- 输出：digest（json+md+html）+ agent_report
- 可观测性：Trace 日志（Scout / Analyst / Critic）

## 4. 成功标准
- 每次运行都能稳定产出日报
- 输出条数、来源分布可控（TopK + quota）
- 出错时自动回退，链路不中断
- 非开发同学能读懂日报与文档

## 5. 阶段路线
- Phase 1（现在）：半自动手动触发，稳定产出
- Phase 2：提升深度分析（Agent 背调、质量评估）
- Phase 3：自动调度 + 发布站点 + 告警

## 6. 不做什么（当前）
- 不做复杂多用户系统
- 不做模型训练闭环
- 不接入高成本全网实时抓取
