"""X1-X4 治理检查器实现"""

from __future__ import annotations

from pathlib import Path

from .primitives import CheckResult, CheckStatus, CheckSeverity, GovernanceCheck


class X1AuditChainChecker(GovernanceCheck):
    """X1 审计链检查器 — 检查操作是否安全"""
    
    def __init__(self, repo_root: str | Path):
        super().__init__("x1-audit-chain", "X1")
        self.repo_root = Path(repo_root)
    
    def execute(self) -> CheckResult:
        issues = []
        
        # 检查 debt-audit.sh
        if not (self.repo_root / "scripts" / "debt-audit.sh").exists():
            issues.append("debt-audit.sh 不存在")
        
        # 检查审计报告
        report_path = self.repo_root / "debt-audit-report.md"
        if not report_path.exists():
            issues.append("审计报告不存在")
        
        # 检查 pre-commit hooks
        projects = ["kairon", "agora", "cockpit", "ecos", "omo", "metaos", "runtime"]
        missing_hooks = []
        for proj in projects:
            hook_path = self.repo_root / "projects" / proj / ".githooks" / "pre-commit"
            if not hook_path.exists():
                missing_hooks.append(proj)
        
        if missing_hooks:
            issues.append(f"缺少 pre-commit: {', '.join(missing_hooks)}")
        
        if not issues:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.PASS,
                message="X1 审计链检查通过",
            )
        elif len(issues) <= 2:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.WARN,
                message=f"X1 审计链有 {len(issues)} 个警告",
                metadata={"issues": issues},
            )
        else:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.FAIL,
                message=f"X1 审计链有 {len(issues)} 个问题",
                severity=CheckSeverity.HIGH,
                metadata={"issues": issues},
            )
    
    def get_description(self) -> str:
        return "检查操作是否安全：债务审计 + 操作审计"


class X2StalenessChecker(GovernanceCheck):
    """X2 抗熵检查器 — 检查数据是否新鲜"""
    
    def __init__(self, repo_root: str | Path):
        super().__init__("x2-staleness", "X2")
        self.repo_root = Path(repo_root)
    
    def execute(self) -> CheckResult:
        import yaml
        
        system_yaml = self.repo_root / ".omo" / "state" / "system.yaml"
        if not system_yaml.exists():
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.FAIL,
                message="system.yaml 不存在",
                severity=CheckSeverity.HIGH,
            )
        
        with open(system_yaml) as f:
            data = yaml.safe_load(f) or {}
        
        debt_weight = data.get("debt_weight", 0)
        debt_health = data.get("debt_metrics", {}).get("debt_health", 0)
        
        issues = []
        if debt_weight < 0.7:
            issues.append(f"debt_weight = {debt_weight} (< 0.7)")
        elif debt_weight < 0.9:
            issues.append(f"debt_weight = {debt_weight} (0.7-0.9)")
        
        if debt_health < 70:
            issues.append(f"debt_health = {debt_health} (< 70)")
        elif debt_health < 90:
            issues.append(f"debt_health = {debt_health} (70-90)")
        
        metadata = {
            "debt_weight": debt_weight,
            "debt_health": debt_health,
        }
        
        if not issues:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.PASS,
                message=f"X2 抗熵检查通过 (weight={debt_weight}, health={debt_health})",
                metadata=metadata,
            )
        elif len(issues) == 1 and "0.7-0.9" in issues[0]:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.WARN,
                message="X2 抗熵有警告",
                metadata=metadata,
            )
        else:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.FAIL,
                message="X2 抗熵检查失败",
                severity=CheckSeverity.HIGH,
                metadata=metadata,
            )
    
    def get_description(self) -> str:
        return "检查数据是否新鲜：债务新鲜度 + 健康度趋势"


class X3ValueChecker(GovernanceCheck):
    """X3 价值栈检查器 — 检查投入是否合理"""
    
    def __init__(self, repo_root: str | Path):
        super().__init__("x3-value", "X3")
        self.repo_root = Path(repo_root)
    
    def execute(self) -> CheckResult:
        issues = []
        
        # 检查 SLA 文档
        sla_path = self.repo_root / ".omo" / "_knowledge" / "governance" / "sla.md"
        if not sla_path.exists():
            issues.append("sla.md 不存在")
        
        # 检查债务优先级
        debt_items_dir = self.repo_root / ".omo" / "debt" / "items"
        if debt_items_dir.exists():
            import yaml
            critical_count = 0
            for f in debt_items_dir.glob("*.yaml"):
                with open(f) as fh:
                    data = yaml.safe_load(fh) or {}
                if data.get("severity") == "critical":
                    critical_count += 1
            
            if critical_count > 0:
                issues.append(f"有 {critical_count} 项 critical 债务")
        
        metadata = {
            "sla_exists": sla_path.exists(),
        }
        
        if not issues:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.PASS,
                message="X3 价值栈检查通过",
                metadata=metadata,
            )
        else:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.WARN if len(issues) == 1 else CheckStatus.FAIL,
                message=f"X3 价值栈有 {len(issues)} 个问题",
                metadata=metadata,
            )
    
    def get_description(self) -> str:
        return "检查投入是否合理：债务优先级 + SLA 达成"


class X4ConsistencyChecker(GovernanceCheck):
    """X4 一致性检查器 — 检查规则是否被遵守"""
    
    def __init__(self, repo_root: str | Path):
        super().__init__("x4-consistency", "X4")
        self.repo_root = Path(repo_root)
    
    def execute(self) -> CheckResult:
        issues = []
        
        # 检查 CI 工作流
        ci_dir = self.repo_root / ".github" / "workflows"
        if ci_dir.exists():
            ci_count = len(list(ci_dir.glob("*.yml")))
            if ci_count < 5:
                issues.append(f"CI 工作流只有 {ci_count} 个 (< 5)")
        else:
            issues.append(".github/workflows/ 不存在")
        
        # 检查 pre-commit 配置
        projects = ["kairon", "agora", "cockpit", "ecos", "omo", "metaos", "runtime"]
        missing_githooks = []
        for proj in projects:
            githooks_dir = self.repo_root / "projects" / proj / ".githooks"
            if not githooks_dir.exists():
                missing_githooks.append(proj)
        
        if missing_githooks:
            issues.append(f"缺少 .githooks/: {', '.join(missing_githooks)}")
        
        metadata = {
            "ci_count": ci_count if ci_dir.exists() else 0,
            "missing_githooks": missing_githooks,
        }
        
        if not issues:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.PASS,
                message="X4 一致性检查通过",
                metadata=metadata,
            )
        else:
            return CheckResult(
                check_id=self.check_id,
                dimension=self.dimension,
                status=CheckStatus.WARN if len(issues) == 1 else CheckStatus.FAIL,
                message=f"X4 一致性有 {len(issues)} 个问题",
                metadata=metadata,
            )
    
    def get_description(self) -> str:
        return "检查规则是否被遵守：CI + pre-commit + 文档"
