#!/usr/bin/env python3
"""
L1 运行时健康探针扫描器

检测项:
- omlxcd daemon 状态
- Matrix/Scheduler 进程存活
- KEI 沙箱可用性
- AetherForge GPU 利用率
- Surface 传感器桥接状态

Usage:
    python3 bin/runtime-health-scan.py [--json] [--output <file>]
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class RuntimeHealthProbe:
    """L1 运行时健康探针"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: Dict[str, Any] = {}
        self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    def check_omlxcd_daemon(self) -> Dict:
        """检查 omlxcd daemon 状态"""
        result = {
            "component": "omlxcd",
            "status": "unknown",
            "checks": []
        }
        
        # 检查进程是否存在
        try:
            proc = subprocess.run(
                ["pgrep", "-f", "omlxcd"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if proc.returncode == 0:
                pid = proc.stdout.strip().split()[0]
                result["status"] = "healthy"
                result["checks"].append(f"PID: {pid}")
            else:
                result["status"] = "not_running"
                result["checks"].append("Process not found")
                
        except Exception as e:
            result["status"] = "error"
            result["checks"].append(f"Check failed: {e}")
        
        return result
    
    def check_matrix_scheduler(self) -> Dict:
        """检查 Matrix/Scheduler 进程"""
        result = {
            "component": "matrix_scheduler",
            "status": "unknown",
            "checks": []
        }
        
        processes = ["matrix", "scheduler"]
        running = []
        
        for proc_name in processes:
            try:
                proc = subprocess.run(
                    ["pgrep", "-f", proc_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if proc.returncode == 0:
                    pids = proc.stdout.strip().split()
                    running.append(f"{proc_name}({len(pids)} processes)")
                else:
                    result["checks"].append(f"{proc_name}: not running")
                    
            except Exception as e:
                result["checks"].append(f"{proc_name} check failed: {e}")
        
        if running:
            result["status"] = "healthy"
            result["checks"].extend(running)
        else:
            result["status"] = "degraded"
        
        return result
    
    def check_kei_sandbox(self) -> Dict:
        """检查 KEI 沙箱可用性"""
        result = {
            "component": "kei_sandbox",
            "status": "unknown",
            "checks": []
        }
        
        # 检查 KEI 相关目录和权限
        kei_paths = [
            "/var/lib/kei",
            "/tmp/kei-sandbox",
        ]
        
        available = []
        for path in kei_paths:
            if os.path.exists(path):
                available.append(path)
            else:
                result["checks"].append(f"{path}: not found")
        
        if available:
            result["status"] = "healthy"
            result["checks"].append(f"Paths: {', '.join(available)}")
        else:
            result["status"] = "not_configured"
            result["checks"].append("KEI paths not configured")
        
        return result
    
    def check_aetherforge_gpu(self) -> Dict:
        """检查 AetherForge GPU 利用率"""
        result = {
            "component": "aetherforge_gpu",
            "status": "unknown",
            "checks": []
        }
        
        # 检查 nvidia-smi (如果有)
        try:
            proc = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used --format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if proc.returncode == 0:
                gpu_info = proc.stdout.strip()
                result["status"] = "healthy"
                result["checks"].append(f"GPU info: {gpu_info[:100]}...")
            else:
                result["status"] = "not_available"
                result["checks"].append("nvidia-smi not available or no GPU detected")
                
        except FileNotFoundError:
            result["status"] = "not_available"
            result["checks"].append("nvidia-smi command not found")
        except Exception as e:
            result["status"] = "error"
            result["checks"].append(f"GPU check failed: {e}")
        
        return result
    
    def check_surface_sensor_bridge(self) -> Dict:
        """检查 Surface 传感器桥接状态"""
        result = {
            "component": "surface_sensor_bridge",
            "status": "unknown",
            "checks": []
        }
        
        # 检查 surface 守护进程
        try:
            proc = subprocess.run(
                ["pgrep", "-f", "surface.*daemon"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if proc.returncode == 0:
                result["status"] = "healthy"
                result["checks"].append("Surface daemon running")
            else:
                result["status"] = "not_running"
                result["checks"].append("Surface daemon not running")
                
        except Exception as e:
            result["status"] = "error"
            result["checks"].append(f"Check failed: {e}")
        
        return result
    
    def run_all_checks(self) -> Dict:
        """运行所有健康检查"""
        self.results = {
            "timestamp": self.timestamp,
            "components": {}
        }
        
        checks = [
            self.check_omlxcd_daemon,
            self.check_matrix_scheduler,
            self.check_kei_sandbox,
            self.check_aetherforge_gpu,
            self.check_surface_sensor_bridge,
        ]
        
        overall_status = "healthy"
        
        for check_func in checks:
            component_result = check_func()
            component_name = component_result["component"]
            self.results["components"][component_name] = component_result
            
            if component_result["status"] == "not_running" or component_result["status"] == "error":
                overall_status = "unhealthy"
            elif component_result["status"] == "degraded" or component_result["status"] == "not_available":
                if overall_status == "healthy":
                    overall_status = "degraded"
        
        self.results["overall_status"] = overall_status
        self.results["summary"] = {
            "total_components": len(checks),
            "healthy_components": sum(1 for c in self.results["components"].values() if c["status"] == "healthy"),
            "degraded_components": sum(1 for c in self.results["components"].values() if c["status"] in ["degraded", "not_available"]),
            "unhealthy_components": sum(1 for c in self.results["components"].values() if c["status"] in ["not_running", "error"])
        }
        
        return self.results
    
    def print_report(self):
        """打印人类可读的报告"""
        print("="*60)
        print("L1 运行时健康探针报告")
        print("="*60)
        print(f"时间戳：{self.timestamp}")
        print(f"总体状态：{self.results['overall_status'].upper()}")
        print()
        print("组件状态:")
        
        for name, data in self.results["components"].items():
            status_icon = {
                "healthy": "✅",
                "degraded": "⚠️",
                "not_available": "❓",
                "not_running": "❌",
                "error": "💥"
            }.get(data["status"], "❓")
            
            print(f"\n{status_icon} {name.upper()}")
            for check in data["checks"]:
                print(f"   - {check}")
        
        print("\n" + "="*60)
        print("汇总:")
        summary = self.results["summary"]
        print(f"   总组件数：{summary['total_components']}")
        print(f"   ✅ 正常：{summary['healthy_components']}")
        print(f"   ⚠️ 降级：{summary['degraded_components']}")
        print(f"   ❌ 异常：{summary['unhealthy_components']}")
        print("="*60)
    
    def to_json(self) -> str:
        """输出 JSON 格式"""
        return json.dumps(self.results, indent=2, ensure_ascii=False)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="L1 运行时健康探针扫描器")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--output", "-o", type=str, help="输出文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    probe = RuntimeHealthProbe(verbose=args.verbose)
    results = probe.run_all_checks()
    
    if args.json:
        output = probe.to_json()
        print(output)
    else:
        probe.print_report()
        output = None
    
    if args.output:
        with open(args.output, 'w') as f:
            if args.json:
                f.write(output)
            else:
                f.write(probe.to_json())
        print(f"\n报告已保存到：{args.output}")
    
    # 退出码：healthy=0, degraded=1, unhealthy=2
    status = results["overall_status"]
    if status == "healthy":
        sys.exit(0)
    elif status == "degraded":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
