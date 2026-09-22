"""Detect the egress network interface and its link speed."""
from __future__ import annotations

import re
import socket
import subprocess
from pathlib import Path
from typing import Optional


def egress_interface(host: str) -> Optional[str]:
    """Return the interface the kernel routes traffic to ``host`` through."""
    try:
        addr = socket.getaddrinfo(host, None)[0][4][0]
    except (OSError, IndexError):
        return None
    try:
        out = subprocess.run(
            ["ip", "route", "get", addr],
            capture_output=True, text=True, timeout=2,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"\bdev\s+(\S+)", out)
    if match:
        return match.group(1)
    # Loopback routes may omit "dev" on some kernels
    if addr.startswith("127.") or addr == "::1":
        return "lo"
    return None


def link_speed_mbps(iface: str) -> Optional[int]:
    """Link speed in Mbit/s from sysfs, or None if unknown (e.g. lo, veth)."""
    try:
        value = int(Path(f"/sys/class/net/{iface}/speed").read_text().strip())
    except (OSError, ValueError):
        return None
    return value if value > 0 else None
