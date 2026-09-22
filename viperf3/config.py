"""Client configuration model, CLI argument builder and preset storage."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "viperf3"


PRESETS_FILE = _config_dir() / "presets.json"


@dataclass
class ClientConfig:
    """Parameters for an iperf3 client run."""

    host: str = "127.0.0.1"
    port: int = 5201
    duration: int = 10          # -t
    parallel: int = 1           # -P
    reverse: bool = False       # -R
    bidir: bool = False         # --bidir
    udp: bool = False           # -u
    bitrate: str = ""           # -b (e.g. "100M"); mainly for UDP
    interval: float = 1.0       # -i
    omit: int = 0               # -O (seconds to omit)
    window: str = ""            # -w (TCP window size, e.g. "256K")
    extra: str = ""             # raw extra flags

    def validate(self) -> list[str]:
        """Return a list of human-readable validation errors (empty = ok)."""
        errors: list[str] = []
        if not self.host.strip():
            errors.append("Host is required")
        if not (1 <= self.port <= 65535):
            errors.append("Port must be between 1 and 65535")
        if self.duration < 1:
            errors.append("Duration must be >= 1 second")
        if self.parallel < 1:
            errors.append("Parallel streams must be >= 1")
        if self.interval <= 0:
            errors.append("Interval must be > 0")
        if self.omit < 0:
            errors.append("Omit must be >= 0")
        if self.reverse and self.bidir:
            errors.append("Reverse and bidir cannot be combined")
        return errors

    def to_args(self) -> list[str]:
        """Build the iperf3 argument list (without the executable name)."""
        args = [
            "-c", self.host.strip(),
            "-p", str(self.port),
            "-t", str(self.duration),
            "-i", _fmt_num(self.interval),
            "-P", str(self.parallel),
            "--json-stream",
        ]
        if self.udp:
            args.append("-u")
        if self.bitrate.strip():
            args += ["-b", self.bitrate.strip()]
        if self.reverse:
            args.append("-R")
        if self.bidir:
            args.append("--bidir")
        if self.omit > 0:
            args += ["-O", str(self.omit)]
        if self.window.strip():
            args += ["-w", self.window.strip()]
        if self.extra.strip():
            args += self.extra.strip().split()
        return args


def _fmt_num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


# --------------------------------------------------------------------------- #
# Preset persistence                                                          #
# --------------------------------------------------------------------------- #
def load_presets() -> dict[str, ClientConfig]:
    if not PRESETS_FILE.exists():
        return {}
    try:
        raw = json.loads(PRESETS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    result: dict[str, ClientConfig] = {}
    for name, data in raw.items():
        try:
            result[name] = ClientConfig(**data)
        except TypeError:
            continue
    return result


def save_preset(name: str, config: ClientConfig) -> None:
    presets = load_presets()
    presets[name] = config
    _write_presets(presets)


def delete_preset(name: str) -> None:
    presets = load_presets()
    presets.pop(name, None)
    _write_presets(presets)


def _write_presets(presets: dict[str, ClientConfig]) -> None:
    PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {name: asdict(cfg) for name, cfg in presets.items()}
    PRESETS_FILE.write_text(json.dumps(data, indent=2))
