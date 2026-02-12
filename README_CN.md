# 📋 agent-log-analyzer

AI Agent日志分析工具。解析、搜索和可视化Agent执行日志。

## 功能特点

- **模式检测** — 自动发现重复失败模式
- **错误聚类** — 相似错误归组分析
- **时间线可视化** — 执行流程图表
- **多格式支持** — JSON, JSONL, 纯文本

## 快速开始

```bash
python agent_log.py analyze agent.log
python agent_log.py patterns agent.log --min-count 3
python agent_log.py timeline agent.log
```

## 许可证
MIT
