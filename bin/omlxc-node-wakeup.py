#!/usr/bin/env python3
# bin/omlxc-node-wakeup.py — AetherForge 从机物理节点网络唤醒 (WoL) 自愈代理
#
# 从 project-registry.yaml 读取 compute_nodes MAC 地址与 LAN IP，并发送 Magic Packet 唤醒包。
# 
# 用法:
#   python3 bin/omlxc-node-wakeup.py --node mac-mini-M4
#   python3 bin/omlxc-node-wakeup.py --all

import os
import sys
import socket
import argparse
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
PROJ_REG = WORKSPACE / "docs" / "project-registry.yaml"


def load_compute_nodes() -> dict:
    """从 project-registry.yaml 读取节点硬件配置"""
    if not PROJ_REG.is_file():
        print(f"❌ 注册表文件不存在: {PROJ_REG}", file=sys.stderr)
        return {}
    try:
        import yaml
        data = yaml.safe_load(PROJ_REG.read_text(encoding="utf-8")) or {}
        return data.get("compute_nodes", {})
    except Exception as e:
        print(f"❌ 读取注册表 YAML 失败: {e}", file=sys.stderr)
        return {}


def send_magic_packet(mac_address: str, ip_address: str = "255.255.255.255", port: int = 9) -> bool:
    """构造并发送 Wake-on-LAN Magic Packet"""
    try:
        # 格式化 MAC 地址
        clean_mac = mac_address.replace(":", "").replace("-", "").replace(".", "")
        if len(clean_mac) != 12:
            raise ValueError(f"不合法的 MAC 地址长度: {mac_address}")
        mac_bytes = bytes.fromhex(clean_mac)
        
        # 构造 Magic Packet (6个0xFF + 16次MAC)
        packet = b'\xff' * 6 + mac_bytes * 16
        
        # 发送广播
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # 发送到全局广播
            s.sendto(packet, ("255.255.255.255", port))
            # 同时发给具体 IP 作为防线
            if ip_address != "255.255.255.255":
                s.sendto(packet, (ip_address, port))
                
        return True
    except Exception as e:
        print(f"⚠️ 发送唤醒包失败 [{mac_address} -> {ip_address}]: {e}", file=sys.stderr)
        return False


def wakeup_node(name: str, node_data: dict) -> bool:
    mac = node_data.get("mac")
    lan_ip = node_data.get("lan_ip", "255.255.255.255")
    
    if not mac:
        print(f"❌ 节点 '{name}' 未登记 MAC 地址，无法唤醒。")
        return False
        
    print(f"🔌 正在尝试网络唤醒节点 '{name}'...")
    print(f"    MAC 地址: {mac}")
    print(f"    局域网 IP: {lan_ip}")
    
    # 广播唤醒 (Port 9 默认，同时发往 Port 7)
    ok9 = send_magic_packet(mac, lan_ip, port=9)
    ok7 = send_magic_packet(mac, lan_ip, port=7)
    
    if ok9 or ok7:
        print(f"✅ 唤醒信号已成功向节点 '{name}' 发出。")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=" omlxc 本地算力从机 Wake-on-LAN 唤醒代理")
    parser.add_argument("--node", "-n", help="指定要唤醒的节点名称 (例如: mac-mini-M4)")
    parser.add_argument("--all", "-a", action="store_true", help="唤醒注册表中的所有支持的从机节点")
    args = parser.parse_args()

    nodes = load_compute_nodes()
    if not nodes:
        return 1

    if args.node:
        if args.node not in nodes:
            print(f"❌ 节点 '{args.node}' 未在注册表中定义。可用节点: {list(nodes.keys())}", file=sys.stderr)
            return 1
        success = wakeup_node(args.node, nodes[args.node])
        return 0 if success else 1
        
    elif args.all:
        success_count = 0
        for name, data in nodes.items():
            # 本机 MBP 自身无需唤醒
            if "MBP" in name:
                continue
            if wakeup_node(name, data):
                success_count += 1
        return 0 if success_count > 0 else 1
        
    else:
        # 默认模式：询问或唤醒非本地 MBP 的其他离线从机
        print("💡 提示: 请使用 --node <name> 唤醒特定节点，或 --all 唤醒所有从机。")
        print("可用从机列表:")
        for name in nodes.keys():
            if "MBP" not in name:
                print(f"  - {name} ({nodes[name].get('ip')})")
        return 0


if __name__ == "__main__":
    sys.exit(main())
