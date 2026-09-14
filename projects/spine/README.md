# Spine — LECP Ingress Pipeline

Spine 是 omostation 的邮件/日历信号入口管道，负责解析原始邮件和日历事件并通过 LECP（分类、提取、路由）分诊引擎写入系统信号流。

## 核心能力

- **邮件解析** (`spine/ingress/parsers/email_parser.py`)：解析 `.eml` / MIME 邮件，提取正文、附件、头部
- **日历解析** (`spine/ingress/parsers/calendar_parser.py`)：解析 `.ics` 日历事件，提取时间、参与人、循环规则
- **LECP 分诊** (`spine/ingress/triage/lecp_triage.py`)：对信号进行分类、优先级判定、路由到对应下游

## 开发

```bash
cd projects/spine
uv pip install -e ".[dev]"
pytest
```

## 依赖

- Python ≥ 3.13
- icalendar ≥ 5.0
- structlog ≥ 24.0
