"""Data models for iperf3 json-stream events."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StreamSample:
    """Per-stream throughput inside a single interval."""

    socket: int
    bits_per_second: float
    retransmits: Optional[int] = None
    sender: bool = True


@dataclass
class Interval:
    """One reporting interval (typically 1 second)."""

    start: float
    end: float
    seconds: float
    bits_per_second: float
    bytes: int = 0
    retransmits: Optional[int] = None  # TCP only
    packets: Optional[int] = None      # UDP only
    jitter_ms: Optional[float] = None  # UDP only
    lost_percent: Optional[float] = None
    omitted: bool = False
    reverse_bps: Optional[float] = None  # --bidir: server→client direction
    streams: list[StreamSample] = field(default_factory=list)

    @property
    def mbps(self) -> float:
        return self.bits_per_second / 1e6

    @property
    def reverse_mbps(self) -> float:
        return (self.reverse_bps or 0.0) / 1e6

    @property
    def midpoint(self) -> float:
        return (self.start + self.end) / 2.0


@dataclass
class StartInfo:
    """Metadata emitted at test start."""

    version: str = ""
    connecting_to: str = ""
    protocol: str = "TCP"
    num_streams: int = 1
    reverse: bool = False


@dataclass
class Summary:
    """Final result of a test."""

    sent_bps: float = 0.0
    received_bps: float = 0.0
    # --bidir: totals for the reverse (server→client) direction
    bidir_sent_bps: Optional[float] = None
    bidir_received_bps: Optional[float] = None
    retransmits: Optional[int] = None
    jitter_ms: Optional[float] = None
    lost_percent: Optional[float] = None
    cpu_local: Optional[float] = None
    cpu_remote: Optional[float] = None

    @property
    def sent_mbps(self) -> float:
        return self.sent_bps / 1e6

    @property
    def received_mbps(self) -> float:
        return self.received_bps / 1e6
