# FEEDBACK TRAINING GUIDE

## 1. 目标
把你的偏好信号持续转成排序权重，让日报更贴合你的兴趣。

## 2. 两类反馈入口
1. 手动投喂（高质量强信号）
2. 页面点赞/点踩（行为信号）

## 3. 手动投喂流程
```powershell
python .\scripts\add_liked_item.py --url "https://github.com/org/repo" --title "Repo Name" --tags "agent,infra" --note "工程质量高"
python .\scripts\update_preference_profile.py
```

建议：
- 每天至少投喂 3~5 条你明确喜欢的内容
- `tags` 保持稳定（例如 `agent,infra,benchmark,opensource`）

## 4. 页面反馈流程
1. 在页面卡片上点 `👍` 或 `👎`
2. 点击 `导出反馈 JSON`
3. 导入反馈并更新画像：
```powershell
python .\scripts\import_web_feedback.py --input .\anm_feedback_export.json
python .\scripts\update_preference_profile.py
```

## 5. 画像文件说明
文件：`feedback/preference_profile.json`

核心字段：
- `source_weights`：对来源偏好
- `domain_weights`：对域名偏好
- `keyword_weights`：对关键词偏好
- `positive_events` / `negative_events`：样本规模

## 6. 排序如何使用画像
在 `phase1_rss/pipeline/select.py` 中：
- 计算 `preference_score`
- 计算 `personalized_total_score`
- 以 `personalized_total_score` 作为排序主键

可调参数：
- `PREFERENCE_ALPHA`（默认 1.5）
  - 偏低：更保守，接近基础评分
  - 偏高：更个性化，排序变化更大

## 7. 每周维护建议
1. 每周清理明显错误标签
2. 每周检查 `positive_events / negative_events` 是否失衡
3. 每周抽样 20 条结果，人工判断“命中率是否提升”

