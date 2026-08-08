"""Cockpit roadmap items.

Split from api_system_map_catalog.py (god-module SRP, T6-10).
Pure data, no logic dependencies.
"""

from __future__ import annotations

from typing import Any

ROADMAP_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "id": "first-mile-system-map",
        "priority": "P0",
        "stage": "now",
        "status": "shipped",
        "title": "建立 Cockpit 第一入口地图",
        "domain": "entry",
        "cockpit_page": "SystemMap",
        "problem": "页面多但缺一张总图，用户不知道从哪里开始。",
        "actions": (
            "按站点结构、使用路径、架构层级、功能域和项目矩阵组织入口。",
            "把权威读源集中展示，避免 Cockpit 自己维护漂移事实。",
        ),
        "acceptance": (
            "用户能从首页或侧边栏进入 SystemMap。",
            "SystemMap 能定位项目、能力域、常用路径和 SSOT 读源。",
        ),
    },
    {
        "id": "global-search-routing",
        "priority": "P0",
        "stage": "now",
        "status": "shipped",
        "title": "让全局搜索真正能导航",
        "domain": "entry",
        "cockpit_page": "SystemMap",
        "problem": "顶部搜索框原先更像摆设，不能跨页面、项目、能力域检索。",
        "actions": (
            "接入页面、项目别名和能力关键词的站内导航搜索。",
            "支持输入项目名、能力域、页面名后直接跳转目标页面。",
        ),
        "acceptance": (
            "搜索 cockpit、治理、OPC、compute 等关键词能返回可点击入口。",
            "无匹配时明确提示，不吞键盘操作。",
        ),
    },
    {
        "id": "domain-app-health-actions",
        "priority": "P0",
        "stage": "now",
        "status": "shipped",
        "title": "领域应用健康检查与启动动作",
        "domain": "domain-apps",
        "cockpit_page": "DomainApps",
        "problem": "应用中心能展示 contract，但启动、健康检查、验证还没有形成闭环。",
        "actions": (
            "为每个 domain app 增加 health probe 和 verify command 状态。",
            "把 start/open/verify 的边界明确成只读、复制命令或受控动作。",
        ),
        "acceptance": (
            "家庭驾驶舱、OPC、family-hub 都显示最新健康状态。",
            "高风险写入类能力在 UI 中有安全门提示。",
        ),
    },
    {
        "id": "project-native-status",
        "priority": "P1",
        "stage": "next",
        "status": "shipped",
        "title": "把定位视图升级为项目原生状态面",
        "domain": "project-coverage",
        "cockpit_page": "SystemMap",
        "problem": "部分项目原先只能被定位，缺少目录、文档、命令和构建清单状态。",
        "actions": (
            "从项目目录、AGENTS.md 和常见 manifest 读取基础状态。",
            "在项目矩阵中展示文档覆盖、命令、风险和下一步。",
        ),
        "acceptance": (
            "项目矩阵不只显示职责，还能看到基础可操作状态。",
            "缺文档、缺命令或缺 manifest 的项目有明确风险提示。",
        ),
    },
    {
        "id": "project-runtime-probes",
        "priority": "P1",
        "stage": "next",
        "status": "shipped",
        "title": "项目运行探针与最近验证",
        "domain": "project-coverage",
        "cockpit_page": "SystemMap",
        "problem": "基础状态已接入后，还需要把端口监听和最近验证放到同一个项目面。",
        "actions": (
            "接入端口注册表和 agent-workflow 验证事件。",
            "在项目矩阵中显示运行状态、监听端口和最近验证。",
        ),
        "acceptance": (
            "项目矩阵能区分目录就绪、服务运行、验证通过三个层次。",
            "高频项目能看到最近一次验证命令和结果。",
        ),
    },
    {
        "id": "project-runtime-actions",
        "priority": "P2",
        "stage": "now",
        "status": "shipped",
        "title": "项目级受控运行操作",
        "domain": "project-coverage",
        "cockpit_page": "SystemMap",
        "problem": "Cockpit 现在能看项目运行态，但还不能安全地执行项目级 start/verify/restart。",
        "actions": (
            "把可执行动作收敛到受控命令和确认门。",
            "高风险操作只提供复制命令或显式确认入口。",
        ),
        "acceptance": (
            "项目矩阵能区分只读信息和可执行动作。",
            "所有执行动作都有审计和失败反馈。",
        ),
    },
    {
        "id": "project-action-execution-audit",
        "priority": "P2",
        "stage": "now",
        "status": "shipped",
        "title": "项目动作执行与审计",
        "domain": "project-coverage",
        "cockpit_page": "TaskCenter",
        "problem": "项目动作需要在统一任务中心内形成可审批、可控进程、可审计的执行闭环。",
        "actions": (
            "保持 verify 通过受控任务队列执行，并把退出码和日志回写 OMO。",
            "为 start/stop/restart 接入人工审批、独立进程组、日志和失败反馈。",
        ),
        "acceptance": (
            "用户能在 TaskCenter 看到项目动作执行历史。",
            "每次执行都有命令、退出码、日志位置、触发人和进程状态。",
            "未获批的中高风险动作不能启动、停止或重启服务。",
        ),
    },
    {
        "id": "ssot-deep-links",
        "priority": "P1",
        "stage": "now",
        "status": "shipped",
        "title": "SSOT 行级深链",
        "domain": "governance",
        "cockpit_page": "SystemMap",
        "problem": "当前能指向权威文件，但不能一键定位到具体条目。",
        "actions": (
            "为 project registry、port registry、BOS services、GaC rules 生成行级定位。",
            "在页面卡片上补 source key 和 source path。",
        ),
        "acceptance": (
            "点击项目或能力能知道权威读源和具体来源。",
            "新增页面不会复制易漂移计数。",
        ),
    },
    {
        "id": "source-open-actions",
        "priority": "P2",
        "stage": "now",
        "status": "shipped",
        "title": "来源证据预览",
        "domain": "governance",
        "cockpit_page": "SystemMap",
        "problem": "当前已经能展示和复制 path:line，但用户仍需要离开 Cockpit 才能核对来源内容。",
        "actions": (
            "提供只读 source_ref 预览接口，按 workspace 白名单读取目标行附近内容。",
            "前端点击来源定位时直接展示文件、行号和上下文，同时保留复制精确位置。",
        ),
        "acceptance": (
            "点击来源能在 SystemMap 内看到目标行附近的权威内容。",
            "预览接口拒绝 Workspace 外部路径，且不执行本机打开命令。",
        ),
    },
    {
        "id": "guided-ops-checklists",
        "priority": "P2",
        "stage": "now",
        "status": "shipped",
        "title": "面向场景的操作清单",
        "domain": "usage",
        "cockpit_page": "SystemMap",
        "problem": "使用路径已经成型，但还没有逐步勾选式执行面。",
        "actions": (
            "把日常体检、治理闭环、知识工作、领域作战做成 checklist。",
            "把 checklist 的完成证据连接到任务中心和日志。",
        ),
        "acceptance": (
            "用户能按场景完成一次端到端巡检。",
            "每个 checklist 有下一步入口和证据位置。",
        ),
    },
    {
        "id": "playbook-evidence-persistence",
        "priority": "P2",
        "stage": "now",
        "status": "shipped",
        "title": "操作清单证据持久化",
        "domain": "usage",
        "cockpit_page": "TaskCenter",
        "problem": "操作清单现在能指导使用，但完成状态和证据还需要进入任务中心。",
        "actions": (
            "为 playbook step 增加任务中心只读草稿和证据字段。",
            "先提供可复制任务材料，正式写入仍走 C2G/OMO 受控入口。",
        ),
        "acceptance": (
            "用户能在 TaskCenter 看见每个 playbook 的任务草稿。",
            "草稿包含步骤、证据字段和安全门说明。",
        ),
    },
    {
        "id": "playbook-omo-writeback",
        "priority": "P2",
        "stage": "later",
        "status": "shipped",
        "title": "操作清单写入 OMO",
        "domain": "usage",
        "cockpit_page": "TaskCenter",
        "problem": "TaskCenter 已能通过 OMO broker 把 playbook 草稿写入 planned task；当前重点是持续校验审批、证据和来源回链。",
        "actions": (
            "保持 playbook 草稿到 planned task 的 OMO broker 写回链路可用。",
            "持续校验完成时间、证据链接和触发来源。",
        ),
        "acceptance": (
            "用户能把草稿转成正式 OMO planned task。",
            "写入有审计记录且不绕过治理 broker。",
        ),
    },
)
