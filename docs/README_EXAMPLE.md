# AI News Monitor

一个用于自动抓取、筛选并总结 AI 新闻的项目。

## 功能特点
- 自动抓取多来源新闻
- 关键词过滤
- 每日摘要生成
- 支持邮件/IM 推送

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动程序
```bash
python main.py
```

## 配置示例
在 `.env` 中配置：

```env
NEWS_API_KEY=your_api_key
PUSH_WEBHOOK_URL=https://example.com/webhook
```

## 输出示例
| 时间 | 标题 | 来源 |
|---|---|---|
| 2026-03-07 | OpenAI 发布新模型能力更新 | OpenAI Blog |
| 2026-03-07 | 多模态代理进入企业落地阶段 | TechCrunch |

## 目录结构
```text
.
├─ main.py
├─ requirements.txt
├─ .env
└─ reports/
```

## License
MIT
