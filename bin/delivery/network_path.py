"""Network path probe for physical multi-host measures (honest link class).

Used by measure_physical to stamp env_evidence with Wi-Fi vs Ethernet so
G-DEL.3 failures can be attributed to link tail vs protocol.
"""
from __future__ import annotations

import re
import socket
import subprocess
from typing import Any


def _run(cmd: list[str], timeout: float = 5.0) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _iface_for_host(ip: str) -> dict[str, Any]:
    """Best-effort: which local interface routes to ip (macOS route)."""
    out = _run(["route", "-n", "get", ip])
    iface = None
    rtt = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("interface:"):
            iface = line.split(":", 1)[1].strip()
        if "rtt," in line or line.startswith("rtt"):
            # next data line often has numbers
            pass
    # parse rtt from table line
    m = re.search(r"rtt,msec.*?(\d+)\s+(\d+)", out, re.S)
    if m:
        rtt = int(m.group(1))
    return {"route_interface": iface, "route_rtt_msec_hint": rtt, "raw_has_route": bool(iface)}


def _classify_iface(iface: str | None) -> str:
    if not iface:
        return "unknown"
    # macOS convention: en0 often Wi-Fi on laptops; Ethernet may be en0 on mini
    # Use hardware port listing when available
    ports = _run(["networksetup", "-listallhardwareports"])
    wifi_devs = set(re.findall(r"Hardware Port: Wi-Fi\nDevice: (\w+)", ports))
    eth_devs = set(re.findall(r"Hardware Port: Ethernet\nDevice: (\w+)", ports))
    # USB LAN often "USB 10/100/1000 LAN"
    usb_eth = set(re.findall(r"Hardware Port: USB.*\nDevice: (\w+)", ports))
    if iface in wifi_devs:
        return "wifi"
    if iface in eth_devs or iface in usb_eth:
        return "ethernet"
    if iface.startswith("bridge") or iface.startswith("en") and iface in ("en1", "en2", "en3"):
        # ambiguous thunderbolt
        return "other"
    return "unknown"


def _remote_iface_status(ssh_host: str) -> dict[str, Any]:
    """SSH to peer: which iface holds the LAN IP / ethernet active?"""
    script = (
        "python3 - <<'PY'\n"
        "import subprocess,re\n"
        "out=subprocess.check_output(['ifconfig'],text=True,errors='replace')\n"
        "blocks=re.split(r'\\n(?=\\w)', out)\n"
        "ifaces={}\n"
        "for b in blocks:\n"
        "  m=re.match(r'^(\\w+):', b)\n"
        "  if not m: continue\n"
        "  name=m.group(1)\n"
        "  inet=re.search(r'inet (\\d+\\.\\d+\\.\\d+\\.\\d+)', b)\n"
        "  st=re.search(r'status: (\\w+)', b)\n"
        "  media=re.search(r'media: ([^\\n]+)', b)\n"
        "  ifaces[name]={'inet': inet.group(1) if inet else None,\n"
        "    'status': st.group(1) if st else None,\n"
        "    'media': media.group(1).strip() if media else None}\n"
        "import json; print(json.dumps(ifaces))\n"
        "PY"
    )
    try:
        r = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                ssh_host,
                script,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return {"ok": False, "error": (r.stderr or r.stdout)[:200]}
        import json

        ifaces = json.loads(r.stdout.strip().splitlines()[-1])
        eth_active = any(
            n.startswith("en")
            and (info.get("status") == "active")
            and info.get("media")
            and "none" not in str(info.get("media")).lower()
            and "autoselect (none)" not in str(info.get("media")).lower()
            and info.get("inet")
            for n, info in ifaces.items()
            if n == "en0" or "Ethernet" in str(info)
        )
        # simpler: en0 status
        en0 = ifaces.get("en0") or {}
        wifi_like = ifaces.get("en1") or {}
        return {
            "ok": True,
            "en0_status": en0.get("status"),
            "en0_inet": en0.get("inet"),
            "en0_media": en0.get("media"),
            "en1_status": wifi_like.get("status"),
            "en1_inet": wifi_like.get("inet"),
            "ethernet_likely_active": en0.get("status") == "active" and en0.get("inet"),
            "wifi_likely_active": wifi_like.get("status") == "active" and wifi_like.get("inet"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def probe_path(peer_ip: str) -> dict[str, Any]:
    """Probe local route + remote iface for peer_ip."""
    local = _iface_for_host(peer_ip)
    link = _classify_iface(local.get("route_interface"))
    remote = _remote_iface_status(peer_ip)
    # overall link class
    if link == "wifi" or remote.get("wifi_likely_active") and not remote.get("ethernet_likely_active"):
        link_class = "wifi"
    elif link == "ethernet" or remote.get("ethernet_likely_active"):
        link_class = "ethernet"
    else:
        link_class = link

    return {
        "peer_ip": peer_ip,
        "local_hostname": socket.gethostname(),
        "local_route": local,
        "local_link_class": link,
        "remote": remote,
        "link_class": link_class,
        "wired_available": bool(remote.get("ethernet_likely_active")),
        "recommendation": (
            "path is Wi-Fi; plug Ethernet on macmini (en0) and local host for G-DEL.3 remeasure"
            if link_class == "wifi"
            else "ethernet path available — remeasure with large-N"
        ),
    }


if __name__ == "__main__":
    import json
    import sys

    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.31.210"
    print(json.dumps(probe_path(ip), indent=2, ensure_ascii=False))
