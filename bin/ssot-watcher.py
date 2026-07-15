#!/usr/bin/env python3
"""bin/ssot-watcher.py — SSOT 变更追踪和自动化工具

追踪 eCOS v6 SSOT 文件的变更，记录审计日志，并提供预览同步功能。

SSOT 文件列表：
  - docs/project-registry.yaml
  - protocols/port-registry.yaml
  - projects/agora/etc/bos-services.yaml
  - projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml
  - projects/ecos/src/ecos/ssot/mof/m2/ (M2 模式)
  - projects/ecos/src/ecos/ssot/mof/m1/ (M1 实例)
  - .omo/state/system.yaml
  - .omo/_truth/registry/governance-checks.yaml
  - .omo/_truth/registry/agent-workflows.yaml
  - .omo/_truth/registry/runtime-projections.yaml

使用方法：
  uv run --with pyyaml python bin/ssot-watcher.py status
  uv run --with pyyaml python bin/ssot-watcher.py log --limit 20
  uv run --with pyyaml python bin/ssot-watcher.py preview
  uv run --with pyyaml python bin/ssot-watcher.py sync --author "Your Name" --reason "Update for xxx"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# 工作区根目录
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# SSOT 审计日志路径
AUDIT_LOG_PATH = WORKSPACE_ROOT / ".omo" / "ssot-audit-log.jsonl"

# 追踪的 SSOT 文件列表
SSOT_FILES = [
    # 项目元数据
    ("project_registry", "docs/project-registry.yaml"),
    
    # 协议和端口
    ("port_registry", "protocols/port-registry.yaml"),
    ("vault_paths", "protocols/vault-paths.yaml"),
    ("x_axis_registry", "protocols/x-axis-registry.yaml"),
    
    # BOS 服务
    ("bos_services", "projects/agora/etc/bos-services.yaml"),
    
    # L0 约束
    ("l0_constraints", "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml"),
    
    # MOF 模式
    ("mof_m2", "projects/ecos/src/ecos/ssot/mof/m2/"),
    
    # MOF 实例
    ("mof_m1", "projects/ecos/src/ecos/ssot/mof/m1/"),
    
    # 运行时状态
    ("system_state", ".omo/state/system.yaml"),
    
    # 治理
    ("governance_checks", ".omo/_truth/registry/governance-checks.yaml"),
    ("agent_workflows", ".omo/_truth/registry/agent-workflows.yaml"),
    ("runtime_projections", ".omo/_truth/registry/runtime-projections.yaml"),
]


class SSOTFile:
    """表示一个 SSOT 文件或目录"""
    
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = WORKSPACE_ROOT / path
        self._cached_hash: Optional[str] = None
    
    def exists(self) -> bool:
        return self.path.exists()
    
    def compute_hash(self) -> str:
        """计算文件或目录的哈希"""
        if not self.exists():
            return ""
        
        if self.path.is_file():
            return self._hash_file(self.path)
        elif self.path.is_dir():
            return self._hash_directory(self.path)
        
        return ""
    
    def _hash_file(self, file_path: Path) -> str:
        """计算单个文件的 SHA-256 哈希"""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""
    
    def _hash_directory(self, dir_path: Path) -> str:
        """计算目录中所有 YAML 文件的哈希"""
        hasher = hashlib.sha256()
        
        for yaml_file in sorted(dir_path.rglob("*.yaml")) + sorted(dir_path.rglob("*.yml")):
            hasher.update(yaml_file.name.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(self._hash_file(yaml_file).encode("utf-8"))
            hasher.update(b"\0")
        
        return hasher.hexdigest()
    
    def get_current_hash(self) -> str:
        if self._cached_hash is None:
            self._cached_hash = self.compute_hash()
        return self._cached_hash


class AuditLogEntry:
    """表示一条审计日志"""
    
    def __init__(
        self,
        change_type: str,
        ssot_name: str,
        timestamp: str,
        author: str,
        reason: str,
        state_before: Optional[str] = None,
        state_after: Optional[str] = None
    ):
        self.change_type = change_type
        self.ssot_name = ssot_name
        self.timestamp = timestamp
        self.author = author
        self.reason = reason
        self.state_before = state_before
        self.state_after = state_after
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_type": self.change_type,
            "ssot_name": self.ssot_name,
            "timestamp": self.timestamp,
            "author": self.author,
            "reason": self.reason,
            "state_before": self.state_before,
            "state_after": self.state_after
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditLogEntry":
        return cls(
            change_type=data["change_type"],
            ssot_name=data["ssot_name"],
            timestamp=data["timestamp"],
            author=data["author"],
            reason=data["reason"],
            state_before=data.get("state_before"),
            state_after=data.get("state_after")
        )


class SSOTWatcher:
    """SSOT 变更追踪器"""
    
    def __init__(self):
        self.ssot_files = [
            SSOTFile(name, path) 
            for name, path in SSOT_FILES
        ]
        self._ensure_audit_log()
    
    def _ensure_audit_log(self):
        """确保审计日志目录存在"""
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not AUDIT_LOG_PATH.exists():
            AUDIT_LOG_PATH.touch()
    
    def capture_current_state(self) -> Dict[str, str]:
        """捕获当前所有 SSOT 文件的状态"""
        state = {}
        for ssot in self.ssot_files:
            state[ssot.name] = ssot.get_current_hash()
        return state
    
    def load_last_state(self) -> Dict[str, str]:
        """从审计日志加载最后记录的状态"""
        last_state = {}
        
        if AUDIT_LOG_PATH.exists():
            with open(AUDIT_LOG_PATH, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = AuditLogEntry.from_dict(json.loads(line))
                        if entry.state_after:
                            state = json.loads(entry.state_after)
                            last_state.update(state)
                    except Exception:
                        pass
        
        return last_state
    
    def detect_changes(self) -> List[Tuple[str, str, str]]:
        """检测 SSOT 文件变更
        
        返回：列表元组 (change_type, ssot_name, detail)
        change_type: "add", "remove", "modify"
        """
        changes = []
        current_state = self.capture_current_state()
        last_state = self.load_last_state()
        
        # 检查已存在文件的变更
        for name, current_hash in current_state.items():
            last_hash = last_state.get(name, "")
            
            if not last_hash:
                changes.append(("add", name, "New SSOT file"))
            elif last_hash != current_hash:
                changes.append(("modify", name, "Content modified"))
        
        # 检查删除
        for name in last_state:
            if name not in current_state:
                changes.append(("remove", name, "SSOT file removed"))
        
        return changes
    
    def log_changes(self, changes: List[Tuple[str, str, str]], 
                   author: str, reason: str):
        """记录变更到审计日志"""
        current_state = self.capture_current_state()
        last_state = self.load_last_state()
        timestamp = datetime.now().isoformat()
        
        for change_type, ssot_name, detail in changes:
            state_before = last_state.get(ssot_name, "")
            state_after = current_state.get(ssot_name, "")
            
            entry = AuditLogEntry(
                change_type=change_type,
                ssot_name=ssot_name,
                timestamp=timestamp,
                author=author,
                reason=reason,
                state_before=state_before,
                state_after=state_after
            )
            
            with open(AUDIT_LOG_PATH, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
    
    def get_audit_log(self, limit: Optional[int] = None) -> List[AuditLogEntry]:
        """获取审计日志"""
        entries = []
        
        if AUDIT_LOG_PATH.exists():
            with open(AUDIT_LOG_PATH, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(AuditLogEntry.from_dict(json.loads(line)))
                    except Exception:
                        pass
        
        if limit:
            entries = entries[-limit:]
        
        return entries


def print_status(watcher: SSOTWatcher):
    """打印 SSOT 状态"""
    current = watcher.capture_current_state()
    changes = watcher.detect_changes()
    
    print("SSOT 状态:")
    print("=" * 60)
    
    for ssot in watcher.ssot_files:
        status = "✓"
        for ct, name, d in changes:
            if name == ssot.name:
                status = "⚠️" if ct == "modify" else "➕" if ct == "add" else "➖"
                break
        
        hash_str = current.get(ssot.name, "")
        short_hash = hash_str[:8] if hash_str else "(empty)"
        
        print(f"  {status} {ssot.name:20} {short_hash}")
    
    if changes:
        print()
        print("检测到变更:")
        print("-" * 60)
        for ct, name, detail in changes:
            print(f"  {ct.upper():8} {name:20} {detail}")
    else:
        print()
        print("✓ 没有检测到变更")


def print_log(watcher: SSOTWatcher, limit: int = 20):
    """打印审计日志"""
    entries = watcher.get_audit_log(limit)
    
    print("SSOT 审计日志:")
    print("=" * 80)
    
    for entry in reversed(entries):
        time_str = entry.timestamp[:19]
        print(f"[{time_str}] {entry.change_type.upper():8} {entry.ssot_name:20}")
        print(f"  Author: {entry.author}")
        print(f"  Reason: {entry.reason}")
        print()


def preview_sync(watcher: SSOTWatcher):
    """预览同步变更"""
    changes = watcher.detect_changes()
    
    if not changes:
        print("✓ 没有检测到需要同步的变更")
        return
    
    print("将要记录的变更:")
    print("=" * 60)
    for ct, name, detail in changes:
        print(f"  {ct.upper():8} {name:20} {detail}")


def perform_sync(watcher: SSOTWatcher, author: str, reason: str):
    """执行同步并记录变更"""
    changes = watcher.detect_changes()
    
    if not changes:
        print("✓ 没有变更需要同步")
        return 0
    
    watcher.log_changes(changes, author, reason)
    
    print(f"✓ 已记录 {len(changes)} 条变更到审计日志")
    return 0


def main():
    parser = argparse.ArgumentParser(description="SSOT 变更追踪和自动化工具")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # status
    status_parser = subparsers.add_parser("status", help="显示当前 SSOT 状态")
    
    # log
    log_parser = subparsers.add_parser("log", help="显示审计日志")
    log_parser.add_argument("--limit", "-l", type=int, default=20, help="显示条目数限制")
    
    # preview
    preview_parser = subparsers.add_parser("preview", help="预览要同步的变更")
    
    # sync
    sync_parser = subparsers.add_parser("sync", help="同步变更到审计日志")
    sync_parser.add_argument("--author", "-a", required=True, help="变更作者")
    sync_parser.add_argument("--reason", "-r", required=True, help="变更原因")
    
    args = parser.parse_args()
    
    watcher = SSOTWatcher()
    
    if args.command == "status":
        print_status(watcher)
    elif args.command == "log":
        print_log(watcher, args.limit)
    elif args.command == "preview":
        preview_sync(watcher)
    elif args.command == "sync":
        rc = perform_sync(watcher, args.author, args.reason)
        sys.exit(rc)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
