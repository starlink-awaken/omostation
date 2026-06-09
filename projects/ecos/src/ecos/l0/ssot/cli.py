"""
SSOT Kernel — cli.py
=====================
命令行入口。

子命令：
  init     初始化新的 SSOT 项目
  compile  编译 YAML 配置为 JSON
  derive   执行规则引擎
  check    只检查不输出报告
  graph    可视化（实体关系图/状态机）
  report   生成报告
  verify   验证元模型正交性
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import sys
from pathlib import Path

from .config_loader import load_domain
from .engine import RuleEngine
from .evolution.evolver import Evolver
from .extractor import TextSource
from .extractor.pipeline import ExtractionPipeline
from .meta_model import MetaType, describe_meta_type, verify_orthogonality
from .reporter import Reporter
from .sync import add_subcommand as add_sync_subcommand
from .sync import cmd_sync

# 导入监控系统模块（可选）
try:
    from .monitoring.alerting import IntelligentAlertingSystem  # noqa: F401
    from .monitoring.architecture import MonitoringArchitecture  # noqa: F401
    from .monitoring.architecture import get_monitoring_architecture  # noqa: F401
    from .monitoring.cli import MonitoringCLI  # noqa: F401
    from .monitoring.collectors import EnhancedMetricsCollector  # noqa: F401
    from .monitoring.dashboard import MonitoringDashboard  # noqa: F401
    from .monitoring.environment import EnvironmentAwareMonitor, get_environment_manager  # noqa: F401
    from .monitoring.storage import InMemoryStorage, JSONStorage  # noqa: F401

    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False


# ── 预置模板 ──────────────────────────────────────────

_TEMPLATES: dict[str, dict[str, str]] = {
    "tech-transfer": {
        "domain.yaml": """# SSOT Domain Config — 技术转移中心
domain:
  name: "tech-transfer-center"
  version: "1.0"
  meta_model_version: "2.0"
  description: "科技成果转移转化中心"
""",
        "entities.yaml": """# 实体定义
entities:
  - id: ORG-中心
    type: Organization
    meta_type: MET-DOMAIN
    name: "技术转移中心"
    status: active
    attributes:
      nature: "成果转化平台"
  - id: ROL-科研人员
    type: Role
    meta_type: MET-DOMAIN
    name: "科研人员"
    status: active
    attributes:
      role: "成果供给方"
  - id: ROL-技术经理人
    type: Role
    meta_type: MET-DOMAIN
    name: "技术经理人"
    status: active
    attributes:
      role: "撮合方"
""",
        "facts.yaml": """# 事实定义
policy: []
data:
  - id: DAT-D-F1
    title: "成果数"
    value: 0
    source: "待补充"
""",
        "rules.yaml": """# 推理规则
rules:
  - id: INF-L1
    pattern: contradiction
    name: "转化率矛盾"
    premises:
      - condition: 'fact_ratio("DAT-D-F2", "DAT-D-F1") < 0.1'
    logic: "转化率偏低，需要相应机制"
""",
        "relations.yaml": "relations: []\n",
        "machines.yaml": "machines: []\n",
        "constraints.yaml": "constraints: []\n",
    },
    "research-lab": {
        "domain.yaml": """# SSOT Domain Config — 研究实验室
domain:
  name: "research-lab"
  version: "1.0"
  meta_model_version: "2.0"
  description: "科研实验室知识管理"
""",
        "entities.yaml": """# 实体定义
entities:
  - id: ORG-实验室
    type: Organization
    meta_type: MET-DOMAIN
    name: "实验室"
    status: active
  - id: ROL-研究员
    type: Role
    meta_type: MET-DOMAIN
    name: "研究员"
    status: active
    attributes:
      role: "研究执行"
  - id: PRJ-在研项目
    type: Project
    meta_type: MET-DOMAIN
    name: "在研项目"
    status: active
""",
        "facts.yaml": """# 事实定义
policy: []
data:
  - id: DAT-D-F1
    title: "论文数"
    value: 0
    source: "待补充"
""",
        "rules.yaml": """# 推理规则
rules: []
""",
        "relations.yaml": "relations: []\n",
        "machines.yaml": "machines: []\n",
        "constraints.yaml": "constraints: []\n",
    },
}


def cmd_init(args):
    """初始化新的 SSOT 项目"""
    domain_name = args.domain or args.name or "my-project"
    target_dir = Path(args.dir) / domain_name

    if target_dir.exists():
        print(f"❌ 目录已存在: {target_dir}")
        return 1

    target_dir.mkdir(parents=True)

    # 使用预置模板
    if args.template and args.template in _TEMPLATES:
        templates = _TEMPLATES[args.template]
        print(f"  📐 使用模板: {args.template}")
    else:
        templates = {
            "domain.yaml": f"""# SSOT Domain Config — {domain_name}
domain:
  name: "{domain_name}"
  version: "1.0"
  meta_model_version: "2.0"
  created: "{datetime.date.today().isoformat()}"
  description: ""
""",
            "entities.yaml": """# 实体定义（组织/角色/项目/资源）
entities: []
""",
            "facts.yaml": """# 事实定义（政策/数据）
policy: []
data: []
""",
            "rules.yaml": """# 推理规则
# 内置 pattern: contradiction / theory_match / chain_trigger / consistency / capability_gap
rules:
  - id: R-INF-001
    pattern: contradiction
    name: "矛盾检测规则"
    premises:
      - condition: 'entity_attr("ORG-X", "mechanism") == "双轨"'
    logic: "检测到结构性矛盾，需要相应解决方案"
""",
            "relations.yaml": """# 关系定义
relations: []
""",
            "machines.yaml": """# 状态机定义
machines: []
""",
            "constraints.yaml": """# 约束规则
constraints: []
""",
        }

    for filename, content in templates.items():
        (target_dir / filename).write_text(content, encoding="utf-8")

    print(f"✅ 已初始化 SSOT 项目: {target_dir}")
    print(f"   领域: {domain_name}")
    print(f"   配置文件: {len(templates)} 个 YAML")
    print("\n下一步: 编辑 entities.yaml / facts.yaml / rules.yaml，然后运行:")
    print("   ssot-kernel compile && ssot-kernel derive")
    return 0


def cmd_compile(args):
    """编译 YAML 配置为 JSON"""
    config = load_domain(args.dir, use_cache=not args.no_cache)

    output = {
        "meta": config.domain,
        "entity_count": len(config.entities),
        "fact_count": len(config.facts),
        "inference_count": len(config.inferences),
        "rule_count": len(config.rules),
        "relation_count": len(config.relations),
        "machine_count": len(config.state_machines),
        "constraint_count": len(config.constraints),
    }

    json_path = Path(args.dir) / "compiled.json"
    json_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"✅ 编译完成: {json_path}")
    print(f"   实体: {output['entity_count']}")
    print(f"   事实: {output['fact_count']}")
    print(f"   推论: {output['inference_count']}")
    print(f"   规则: {output['rule_count']}")
    print(f"   关系: {output['relation_count']}")
    print(f"   状态机: {output['machine_count']}")
    print(f"   约束: {output['constraint_count']}")
    return 0


def _derive_watch(args):
    """监听 YAML 文件变更自动重跑推导"""
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    domain_path = Path(args.dir).resolve()

    class DeriveHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if not event.src_path.endswith(".yaml"):
                return
            if ".checkpoints" in event.src_path:
                return
            print(f"\n🔄 检测到变更: {Path(event.src_path).name}")
            import time

            try:
                _t0 = time.time()
                config = load_domain(str(domain_path))
                engine = RuleEngine()
                report = engine.execute(config, rounds=args.rounds)
                elapsed = time.time() - _t0
                print(
                    f"  ✅ 推导完成: {elapsed:.2f}s | {Reporter.summary_line(report)}"
                )
            except Exception as e:
                print(f"  ❌ {e}")

    event_handler = DeriveHandler()
    observer = Observer()
    observer.schedule(event_handler, str(domain_path), recursive=False)
    observer.start()
    print(f"👀 监听中: {domain_path}/*.yaml (按 Ctrl+C 停止)")
    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    return 0


def cmd_derive(args):
    """执行规则引擎"""
    if args.watch:
        return _derive_watch(args)

    import time

    _t0 = time.time()
    config = load_domain(args.dir)
    _t_load = time.time() - _t0

    engine = RuleEngine()

    if args.verbose:
        print(f"🔧 规则引擎已加载 {len(engine.registry.list_patterns())} 个模式:")
        for p in engine.registry.list_patterns():
            print(f"   ├─ {p}")

    _t1 = time.time()
    report = engine.execute(
        domain=config,
        rules=None,
        rounds=args.rounds,
    )
    _t_exec = time.time() - _t1
    _t_total = time.time() - _t0

    output_dir = Path(args.dir) / "_推导日志"
    output_dir.mkdir(exist_ok=True)

    # 性能日志
    perf_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "domain": config.domain.get("name", "unknown"),
        "load_seconds": round(_t_load, 3),
        "exec_seconds": round(_t_exec, 3),
        "total_seconds": round(_t_total, 3),
        "total_rules": report.total_rules,
        "passed": report.passed,
        "blocker": report.blocker,
        "error": report.error,
        "warn": report.warn,
        "entity_count": len(config.entities),
        "fact_count": len(config.facts),
    }
    perf_path = output_dir / "performance.jsonl"
    with open(perf_path, "a") as pf:
        pf.write(json.dumps(perf_entry, ensure_ascii=False) + "\n")

    # 输出 Markdown
    md = Reporter.to_markdown(report)
    md_path = (
        output_dir / f"derive-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    )
    md_path.write_text(md, encoding="utf-8")
    print(f"📄 报告: {md_path}")

    # 输出 JSON
    js = Reporter.to_json(report)
    js_path = output_dir / "latest-result.json"
    js_path.write_text(js, encoding="utf-8")

    # 终端摘要
    print(f"\n{Reporter.summary_line(report)}")
    return 0 if report.all_passed else 1


def cmd_check(args):
    """只检查，不输出报告"""
    config = load_domain(args.dir)

    engine = RuleEngine()
    report = engine.execute(config, rounds=1)

    print(f"\n{Reporter.summary_line(report)}")

    if args.verbose:
        for r in report.results:
            icon = "✅" if r.passed else "❌"
            print(f"  {icon} {r.protocol_id}: {r.name}")
            for d in r.details:
                print(f"     {d}")

    return 0 if report.all_passed else 1


def cmd_graph(args):
    """生成可视化（支持 --html 输出）"""
    config = load_domain(args.dir)

    # 收集 mermaid 输出到缓冲区
    buf = io.StringIO()

    def _emit(text: str = ""):
        buf.write(text + "\n")

    if args.type == "entities":
        _emit("```mermaid")
        _emit("graph LR")
        for e in config.entities[:20]:
            label = e.name.replace('"', "'")
            _emit(f'    {e.id}["{label}"]')
        for r in config.relations[:30]:
            _emit(f"    {r.source_id} -->|{r.relation_type}| {r.target_id}")
        _emit("```")
    elif args.type == "state-machine":
        for sm in config.state_machines:
            _emit(f"## {sm.name}")
            _emit("```mermaid")
            _emit("stateDiagram-v2")
            for s in sm.states:
                _emit(f"    state {s.id}")
            for t in sm.transitions:
                label = t.condition.replace('"', "'") if t.condition else ""
                if label:
                    _emit(f"    {t.from_state} --> {t.to_state}: {label}")
                else:
                    _emit(f"    {t.from_state} --> {t.to_state}")
            _emit("```")
    else:
        if config.state_machines:
            args.type = "state-machine"
            return cmd_graph(args)
        else:
            args.type = "entities"
            return cmd_graph(args)

    mermaid_text = buf.getvalue()

    # --html 模式：输出自包含 HTML
    if args.html:
        # 从 mermaid 文本提取纯 mermaid 代码（去掉 ```mermaid 包装）
        pure_lines = []
        in_block = False
        for line in mermaid_text.split("\n"):
            if line.strip().startswith("```mermaid"):
                in_block = True
                continue
            if line.strip() == "```" and in_block:
                in_block = False
                continue
            if in_block:
                pure_lines.append(line)

        # 多图时每个图单独 mermaid 块
        diagram_blocks = []
        current: list[str] = []
        for line in mermaid_text.split("\n"):
            if line.startswith("## "):
                if current:
                    diagram_blocks.append("\n".join(current))
                    current = []
                continue
            if line.strip().startswith("```"):
                continue
            if line.strip():
                current.append(line)
        if current:
            diagram_blocks.append("\n".join(current))

        if not diagram_blocks:
            diagram_blocks = ["\n".join(pure_lines)]

        diagrams_html = "\n".join(
            f'<pre class="mermaid">\n{block}\n</pre>' for block in diagram_blocks
        )

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SSOT Graph — {args.type}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js">
  </script>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 2rem; }}
    h1 {{ color: #333; border-bottom: 2px solid #4f46e5; padding-bottom: 0.5rem; }}
    .mermaid {{ margin: 2rem 0; }}
  </style>
</head>
<body>
  <h1>SSOT {args.type}</h1>
  {diagrams_html}
  <script>mermaid.initialize({{startOnLoad:true, theme:"neutral"}})</script>
</body>
</html>"""

        out_path = args.output or str(Path(args.dir) / f"{args.type}.html")
        Path(out_path).write_text(html, encoding="utf-8")
        print(f"✅ HTML 已生成: {out_path}")
        print("   用浏览器打开即可查看")
    else:
        # 普通文本模式：直接输出
        print(mermaid_text)

    return 0


def cmd_report(args):
    """生成报告"""
    config = load_domain(args.dir)

    engine = RuleEngine()
    report = engine.execute(config, rounds=args.rounds)

    if args.format == "json":
        print(Reporter.to_json(report))
    elif args.format == "md":
        print(Reporter.to_markdown(report))
    else:
        print(Reporter.to_markdown(report))

    return 0


def cmd_completion(args):
    """输出 Shell 自动补全脚本（支持 bash/zsh）"""
    shell = args.shell or "bash"
    prog = "ssot-kernel"
    subcommands = [
        "init",
        "compile",
        "derive",
        "check",
        "graph",
        "report",
        "verify",
        "evolve",
        "extract",
        "stats",
        "export",
        "sync",
        "completion",
    ]

    if shell == "zsh":
        comp = f"""#compdef {prog}
_{prog}() {{
  local -a subcmds
  subcmds=(
    {" ".join(f'"{c}:{c}"' for c in subcommands)}
  )
  _describe '{prog} commands' subcmds
}}
compdef _{prog} {prog}
"""
    else:
        comp = f"""_{prog}() {{
  local cur="${{COMP_WORDS[COMP_CWORD]}}"
  local prev="${{COMP_WORDS[COMP_CWORD-1]}}"
  local opts="{" ".join(subcommands)}"
  if [ $COMP_CWORD -eq 1 ]; then
    COMPREPLY=($(compgen -W "${{opts}}" -- "${{cur}}"))
  fi
}}
complete -F _{prog} {prog}
"""
    print(comp)
    return 0


def cmd_verify(args):
    """验证元模型正交性"""
    violations = verify_orthogonality()
    if violations:
        print("❌ 元模型正交性验证未通过:")
        for v in violations:
            print(f"  {v}")
        return 1
    else:
        print("✅ 8 个 MET-Type 两两正交（交集为空）")
        print(f"\n可用的元类型 ({len(MetaType)}):")
        for mt in MetaType:
            desc = describe_meta_type(mt)
            print(f"  {mt.value:20s} — {desc.get('nature', '')}")
        return 0


def cmd_evolve(args):
    """进化分析：从数据中挖掘新规则建议"""
    evolver = Evolver(args.dir)

    if args.action == "analyze":
        report = evolver.analyze()
        print("\n=== 进化分析 ===")
        print(f"{report.summary}")
        print("\n建议列表:")
        for s in report.suggestions:
            tier_icon = {"high": "🔴", "medium": "🟡", "low": "🔵"}
            icon = tier_icon.get(s.tier, "⚪")
            print(f"\n{icon} [{s.tier}] [{s.source}] {s.name}")
            print(f"   理由: {s.rationale}")
            print(f"   置信度: {s.confidence}")
            print("   规则片段:")
            for line in s.yaml_snippet.split("\n"):
                print(f"     {line}")

        print(f"\n检查点: {report.checkpoint}")
        print(
            f"建议: ssot-kernel evolve --dir {args.dir} --action apply --id <suggestion_id>"
        )

    elif args.action == "apply":
        # 通过 ID 应用建议
        target_id = args.id
        report = evolver.analyze()
        target = [s for s in report.suggestions if s.id == target_id]
        if not target:
            print(f"❌ 未找到建议: {target_id}")
            print("可用建议: 先运行 ssot-kernel evolve --action analyze")
            return 1

        success = evolver.apply_suggestion(target[0], auto_confirm=True)
        if success:
            print(f"✅ 已应用规则建议: {target[0].name}")
            print("重新推导中...")
            print(f"  {evolver.verify_evolution()}")
        else:
            print("❌ 应用失败（可能已存在相同规则）")

    elif args.action == "checkpoints":
        cps = evolver.cp.list_checkpoints()
        if not cps:
            print("无检查点")
            return 0
        print(f"\n检查点列表 ({len(cps)}):")
        for cp in cps[:10]:
            print(
                f"  {cp['created_at']} | {cp['label'] or '未标记'} | {len(cp['files'])} 文件"
            )

    elif args.action == "restore":
        cp_name = args.name
        if not cp_name:
            cps = evolver.cp.list_checkpoints()
            if cps:
                cp_name = cps[0]["name"]
                print(f"未指定检查点，使用最新的: {cp_name}")
            else:
                print("❌ 无检查点可恢复")
                return 1
        restored = evolver.cp.restore(cp_name)
        print(f"✅ 已恢复 {len(restored)} 个文件从 {cp_name}")

    return 0


def cmd_extract(args):
    """提取：从原始文本或文件中提取知识结构"""
    import sys

    # 读取输入
    raw_text = ""
    source_name = args.name or ""
    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"❌ 文件不存在: {args.file}")
            return 1
        raw_text = filepath.read_text("utf-8")
        source_name = source_name or filepath.name
    elif not sys.stdin.isatty():
        raw_text = sys.stdin.read()
        source_name = source_name or "stdin"
    else:
        print("❌ 请提供输入。用法:")
        print("  ssot-kernel extract --file document.md")
        print("  cat document.md | ssot-kernel extract")
        print("  ssot-kernel extract --text '原始内容'")
        return 1

    source = TextSource(
        raw_text=raw_text,
        source_type=args.type or "free_text",
        source_name=source_name,
    )

    # 运行流水线
    pipe = ExtractionPipeline(domain_dir=args.dir)

    # 如果指定 --llm，强制只使用 LLM 提取器
    if args.llm:
        from .extractor.llm import LLMExtractor, OllamaBackend

        if args.llm_model:
            # 用户明确指定模型 → 只用 Ollama（单一后端）
            llm_ext = LLMExtractor(backends=[OllamaBackend(model=args.llm_model)])
        else:
            # 未指定模型 → 自动检测后端链（Ollama → 硅基流动 → DeepSeek → OpenAI）
            llm_ext = LLMExtractor(auto_detect=True)

        if llm_ext.can_handle(source):
            pipe.extractors = [llm_ext]
        else:
            print("❌ 无可用的 LLM 后端")
            print("  请启动 Ollama (ollama serve) 或配置 API Key:")
            print("    export SILICONFLOW_API_KEY=sf-xxx")
            print("    export DEEPSEEK_API_KEY=sk-xxx")
            print("    export OPENAI_API_KEY=sk-xxx")
            return 1

    # 先跑提取（不自动写入），展示结果让用户确认
    result = pipe.run(source, auto_write=False)

    extraction = result["result"]
    validation = result["validation"]

    # 输出结果
    print("\n=== 提取结果 ===")
    print(f"总候选: {len(extraction.candidates)}")
    print(f"  ├─ 实体: {len(extraction.entity_candidates)}")
    print(f"  ├─ 事实: {len(extraction.fact_candidates)}")
    print(f"  ├─ 推论: {len(extraction.inference_candidates)}")
    print(f"  ├─ 关系: {len(extraction.relation_candidates)}")
    print(f"  └─ 规则: {len(extraction.rule_candidates)}")
    print(f"提取摘要: {extraction.summary[:200] if extraction.summary else '无'}")

    if args.verbose:
        for c in extraction.candidates[:10]:
            print(f"  [{c.category}] {c.id or '(无ID)'} conf={c.confidence}")

    print("\n=== 校验结果 ===")
    print(f"通过: {'✅' if validation.passed else '❌'}")
    if validation.conflicts:
        print(f"冲突 ({len(validation.conflicts)}):")
        for cf in validation.conflicts[:5]:
            print(
                f"  [{cf.severity}] {cf.field}: {cf.existing_value} vs {cf.extracted_value}"
            )

    # 写入确认
    if args.write and extraction.candidates:
        try:
            resp = input("\n是否写入 YAML 文件？(y/N) ").strip().lower()
            if resp in ("y", "yes"):
                from .extractor.base import YamlWriter

                writer = YamlWriter(args.dir)
                applied = writer.apply(extraction, auto_confirm=True)
                result["applied_files"] = applied
                print("\n=== 已写入 ===")
                for f in applied:
                    print(f"  ✅ {f}")
            else:
                print("  ⏭️  已跳过写入")
        except (EOFError, KeyboardInterrupt):
            print("\n  ⏭️  已跳过写入（非交互环境）")

    if result.get("errors"):
        print("\n=== 错误/提示 ===")
        for e in result["errors"][:5]:
            print(f"  {e}")

    # 提取失败时输出人工干预建议
    if not extraction.candidates:
        print(f"\n{pipe.suggest_manual(source)}")

    return 0 if extraction.candidates else 1


def cmd_stats(args):
    """输出知识库统计信息"""
    config = load_domain(args.dir)

    # 实体统计
    orgs = [e for e in config.entities if e.entity_type == "Organization"]
    roles = [e for e in config.entities if e.entity_type == "Role"]
    projects = [e for e in config.entities if e.entity_type == "Project"]
    others = [
        e
        for e in config.entities
        if e.entity_type not in ("Organization", "Role", "Project")
    ]

    # 事实统计
    policies = [f for f in config.facts if f.tags and "policy" in f.tags]
    data_facts = [f for f in config.facts if f.tags and "data" in f.tags]

    # 关系统计
    rel_types = {}
    for r in config.relations:
        rel_types[r.relation_type] = rel_types.get(r.relation_type, 0) + 1

    # 引用热度
    ref_counts: dict[str, int] = {}
    for inf in config.inferences:
        for dep in inf.derives_from:
            ref_counts[dep] = ref_counts.get(dep, 0) + 1
    for r in config.relations:
        ref_counts[r.source_id] = ref_counts.get(r.source_id, 0) + 1

    top_refs = sorted(ref_counts.items(), key=lambda x: -x[1])[:10]

    # 输出
    print(f"📊 SSOT 知识库统计: {config.domain.get('name', 'unknown')}")
    print("=" * 50)
    print(f"\n🏛 实体 ({len(config.entities)})")
    print(f"   ├─ 组织: {len(orgs)}")
    print(f"   ├─ 角色: {len(roles)}")
    print(f"   ├─ 项目: {len(projects)}")
    print(f"   └─ 其他: {len(others)}")

    print(f"\n📋 事实 ({len(config.facts)})")
    print(f"   ├─ 政策: {len(policies)}")
    print(f"   ├─ 数据: {len(data_facts)}")
    print(f"   └─ 有警告: {sum(1 for f in config.facts if f.warnings)}")

    print(f"\n🔗 关系 ({len(config.relations)})")
    for t, c in sorted(rel_types.items(), key=lambda x: -x[1])[:8]:
        print(f"   ├─ {t}: {c}")

    print(f"\n📎 推论 ({len(config.inferences)})")
    print(f"   ├─ 有理论支撑: {sum(1 for i in config.inferences if i.theory)}")
    print(f"   └─ 缺理论支撑: {sum(1 for i in config.inferences if not i.theory)}")

    print(f"\n⚙️  状态机 ({len(config.state_machines)})")
    for sm in config.state_machines:
        print(f"   ├─ {sm.name}: {len(sm.states)} 状态, {len(sm.transitions)} 转换")

    print(f"\n📏 规则 ({len(config.rules)})")
    patterns = {}
    for r in config.rules:
        patterns[r.pattern] = patterns.get(r.pattern, 0) + 1
    for p, c in sorted(patterns.items(), key=lambda x: -x[1]):
        print(f"   ├─ {p}: {c}")

    if top_refs:
        print("\n🔥 引用热度 TOP 10")
        for eid, count in top_refs:
            entity = config.find_entity(eid)
            name = entity.name if entity else eid
            print(f"   ├─ [{count}x] {name}")

    print(f"\n约束: {len(config.constraints)}")
    return 0


def cmd_export(args):
    """导出知识库为通用格式"""
    config = load_domain(args.dir)
    fmt = args.format
    out = args.output

    if fmt == "json":
        data = {
            "domain": config.domain.get("name", "unknown"),
            "entities": [
                {
                    "id": e.id,
                    "type": e.entity_type,
                    "name": e.name,
                    "status": e.status,
                    "attributes": dict(e.attributes),
                }
                for e in config.entities
            ],
            "facts": [
                {
                    "id": f.id,
                    "title": f.title,
                    "value": f.value,
                    "unit": f.unit,
                    "source": f.source,
                }
                for f in config.facts
            ],
            "inferences": [
                {
                    "id": i.id,
                    "title": i.title,
                    "conclusion": i.conclusion,
                    "theory": i.theory,
                    "derives_from": i.derives_from,
                }
                for i in config.inferences
            ],
            "relations": [
                {"source": r.source_id, "type": r.relation_type, "target": r.target_id}
                for r in config.relations
            ],
            "rules": [
                {"id": r.id, "pattern": r.pattern, "name": r.name} for r in config.rules
            ],
            "state_machines": [
                {
                    "id": sm.id,
                    "name": sm.name,
                    "states": [{"id": s.id, "name": s.name} for s in sm.states],
                    "transitions": [
                        {
                            "from": t.from_state,
                            "to": t.to_state,
                            "condition": t.condition,
                        }
                        for t in sm.transitions
                    ],
                }
                for sm in config.state_machines
            ],
        }
        output = json.dumps(data, ensure_ascii=False, indent=2)

    elif fmt == "csv":
        import csv
        import io

        buf = io.StringIO()

        w = csv.writer(buf)
        w.writerow(["type", "id", "name", "detail"])
        for e in config.entities:
            w.writerow(["entity", e.id, e.name, e.entity_type])
        for f in config.facts:
            w.writerow(["fact", f.id, f.title, str(f.value or "")])
        for i in config.inferences:
            w.writerow(["inference", i.id, i.title, i.conclusion[:60]])
        for r in config.relations:
            w.writerow(
                ["relation", f"{r.source_id}→{r.target_id}", r.relation_type, ""]
            )
        output = buf.getvalue()

    elif fmt == "md":
        lines = [f"# SSOT 知识库: {config.domain.get('name', 'unknown')}", ""]
        lines.append(f"生成时间: {datetime.datetime.now().isoformat()}", "")
        lines.append("## 实体")
        for e in config.entities:
            attrs = "; ".join(f"{k}={v}" for k, v in list(e.attributes.items())[:3])
            lines.append(f"- **{e.id}**: {e.name} ({e.entity_type}) — {attrs}")
        lines.append("")
        lines.append("## 事实")
        for f in config.facts:
            lines.append(f"- **{f.id}**: {f.title} = {f.value} {f.unit}")
        lines.append("")
        lines.append("## 推论")
        for i in config.inferences:
            theory = f" [{i.theory}]" if i.theory else ""
            lines.append(f"- **{i.id}**: {i.title}{theory}")
        lines.append("")
        lines.append("## 规则")
        for r in config.rules:
            lines.append(f"- **{r.id}** ({r.pattern}): {r.name}")
        lines.append("")
        lines.append("## 关系")
        for r in config.relations:
            lines.append(f"- {r.source_id} --[{r.relation_type}]--> {r.target_id}")
        output = "\n".join(lines)

    else:
        print(f"❌ 不支持的格式: {fmt}（可选: json, csv, md）")
        return 1

    if out:
        Path(out).write_text(output, encoding="utf-8")
        print(f"✅ 已导出: {out} ({len(output)} 字节)")
    else:
        print(output)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ssot-kernel",
        description="SSOT Kernel — 单一事实源知识工程通用引擎 v2.0",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument(
        "--debug", action="store_true", help="出错时显示完整 Python 错误栈"
    )

    # 共享参数：所有子命令都继承 --debug
    _common = argparse.ArgumentParser(add_help=False)
    _common.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)

    sub = parser.add_subparsers(dest="command", help="子命令")

    # init
    p_init = sub.add_parser("init", help="初始化新的 SSOT 项目", parents=[_common])
    p_init.add_argument("--domain", "-d", default=None, help="领域名称")
    p_init.add_argument("--name", "-n", default=None, help="领域名称（别名）")
    p_init.add_argument("--dir", default=".", help="父目录")
    p_init.add_argument(
        "--template",
        "-t",
        default="",
        choices=["", "tech-transfer", "research-lab"],
        help="预置模板（tech-transfer / research-lab）",
    )

    # compile
    p_compile = sub.add_parser("compile", help="编译 YAML 为 JSON", parents=[_common])
    p_compile.add_argument("--dir", default=".")
    p_compile.add_argument(
        "--no-cache", action="store_true", help="跳过缓存，强制重新加载"
    )

    # derive
    p_derive = sub.add_parser("derive", help="执行规则引擎", parents=[_common])
    p_derive.add_argument("--dir", default=".")
    p_derive.add_argument("--rounds", type=int, default=1, help="多轮迭代次数")
    p_derive.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    p_derive.add_argument(
        "--watch", "-w", action="store_true", help="监听 YAML 文件变更自动重跑"
    )

    # check
    p_check = sub.add_parser("check", help="只检查不输出报告", parents=[_common])
    p_check.add_argument("--dir", default=".")
    p_check.add_argument("--verbose", "-v", action="store_true")

    # graph
    p_graph = sub.add_parser(
        "graph", help="可视化（mermaid 实体图/状态机）", parents=[_common]
    )
    p_graph.add_argument("--dir", default=".")
    p_graph.add_argument(
        "--type", choices=["entities", "state-machine"], default="entities"
    )
    p_graph.add_argument(
        "--html",
        action="store_true",
        help="输出自包含 HTML（内嵌 mermaid.js CDN，浏览器可直接打开）",
    )
    p_graph.add_argument(
        "--output",
        "-o",
        default="",
        help="HTML 输出路径（默认: {dir}/entities.html 或 machines.html）",
    )

    # report
    p_report = sub.add_parser("report", help="生成报告", parents=[_common])
    p_report.add_argument("--dir", default=".")
    p_report.add_argument("--format", choices=["md", "json"], default="md")
    p_report.add_argument("--rounds", type=int, default=1)

    # verify
    sub.add_parser("verify", help="验证元模型正交性")

    # extract
    p_extract = sub.add_parser("extract", help="从文本提取知识结构", parents=[_common])
    p_extract.add_argument("--dir", default=".", help="目标领域目录（校验和写入目标）")
    p_extract.add_argument("--file", "-f", default="", help="源文件路径")
    p_extract.add_argument(
        "--type",
        "-t",
        default="free_text",
        choices=["free_text", "document", "structured", "conversation"],
        help="源文本类型",
    )
    p_extract.add_argument("--name", "-n", default="", help="源名称（用于元信息）")
    p_extract.add_argument(
        "--write", "-w", action="store_true", help="校验通过后自动写入 YAML"
    )
    p_extract.add_argument(
        "--llm", action="store_true", help="强制使用 LLM 提取（跳过模板）"
    )
    p_extract.add_argument(
        "--llm-model", default="", help="LLM 模型名（如 qwen2.5:7b，默认自动检测）"
    )

    # completion
    p_comp = sub.add_parser(
        "completion", help="输出 Shell 自动补全脚本", parents=[_common]
    )
    p_comp.add_argument(
        "--shell", default="bash", choices=["bash", "zsh"], help="Shell 类型"
    )

    # stats
    p_stats = sub.add_parser("stats", help="输出知识库统计信息", parents=[_common])
    p_stats.add_argument("--dir", default=".", help="领域配置目录")

    # export
    p_export = sub.add_parser("export", help="导出知识库为通用格式", parents=[_common])
    p_export.add_argument("--dir", default=".", help="领域配置目录")
    p_export.add_argument(
        "--format", choices=["json", "csv", "md"], default="md", help="导出格式"
    )
    p_export.add_argument("--output", "-o", default="", help="输出文件路径")

    # sync
    add_sync_subcommand(sub, _common)

    # evolve
    p_evolve = sub.add_parser(
        "evolve", help="进化分析：从数据挖掘新规则", parents=[_common]
    )
    p_evolve.add_argument("--dir", default=".")
    p_evolve.add_argument(
        "--action",
        default="analyze",
        choices=["analyze", "apply", "checkpoints", "restore"],
        help="操作",
    )
    p_evolve.add_argument("--id", default="", help="要应用的规则建议 ID")
    p_evolve.add_argument("--name", default="", help="检查点名称（用于 restore）")

    # 监控子命令
    if MONITORING_AVAILABLE:
        monitoring_sub = sub.add_parser(
            "monitor", help="智能监控系统", parents=[_common]
        )

        monitor_subparsers = monitoring_sub.add_subparsers(
            dest="monitor_command", help="监控子命令"
        )

        # monitor start
        p_monitor_start = monitor_subparsers.add_parser("start", help="启动监控")
        p_monitor_start.add_argument("--duration", type=int, help="监控时长（秒）")
        p_monitor_start.add_argument("--export", help="导出数据到文件")

        # monitor status
        monitor_subparsers.add_parser("status", help="查看监控状态")

        # monitor alerts
        p_monitor_alerts = monitor_subparsers.add_parser("alerts", help="查看告警信息")
        p_monitor_alerts.add_argument("--severity", help="过滤严重程度")
        p_monitor_alerts.add_argument(
            "--stats", action="store_true", help="显示统计信息"
        )
        p_monitor_alerts.add_argument(
            "--report", action="store_true", help="生成告警报告"
        )

        # monitor metrics
        p_monitor_metrics = monitor_subparsers.add_parser("metrics", help="查看指标")
        p_monitor_metrics.add_argument(
            "--category",
            choices=["system", "execution", "business", "quality", "all"],
            default="all",
            help="指标类别",
        )
        p_monitor_metrics.add_argument(
            "--history", type=int, help="历史时间窗口（分钟）"
        )
        p_monitor_metrics.add_argument("--export", help="导出数据到文件")

        # monitor report
        p_monitor_report = monitor_subparsers.add_parser("report", help="生成监控报告")
        p_monitor_report.add_argument("--export", help="导出报告到文件")

        # monitor dashboard
        p_monitor_dashboard = monitor_subparsers.add_parser(
            "dashboard", help="监控仪表板"
        )
        p_monitor_dashboard.add_argument(
            "--html", action="store_true", help="生成HTML仪表板"
        )
        p_monitor_dashboard.add_argument("--export", help="导出仪表板数据")

    args = parser.parse_args(argv)
    debug = getattr(args, "debug", False)

    try:
        return _dispatch(args, parser)
    except Exception as e:
        if debug:
            import traceback

            traceback.print_exc()
        else:
            print(f"❌ {e.__class__.__name__}: {e}")
            print("  使用 --debug 查看完整错误栈")
        return 1


def _dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.command == "init":
        return cmd_init(args)
    elif args.command == "compile":
        return cmd_compile(args)
    elif args.command == "derive":
        return cmd_derive(args)
    elif args.command == "check":
        return cmd_check(args)
    elif args.command == "graph":
        return cmd_graph(args)
    elif args.command == "report":
        return cmd_report(args)
    elif args.command == "evolve":
        return cmd_evolve(args)
    elif args.command == "verify":
        return cmd_verify(args)
    elif args.command == "extract":
        return cmd_extract(args)
    elif args.command == "stats":
        return cmd_stats(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command == "sync":
        return cmd_sync(args)
    elif args.command == "completion":
        return cmd_completion(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
