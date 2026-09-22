"""Parser for iperf3 ``--json-stream`` output.

Each line of stream output is a standalone JSON object of the form::

    {"event": "<start|interval|end|error>", "data": {...}}

The parser is tolerant: malformed / partial lines are ignored so the UI never
crashes on unexpected output.
"""
from __future__ import annotations

import json
from typing import Iterator, Union

from .models import Interval, StartInfo, StreamSample, Summary

ParsedEvent = Union[StartInfo, Interval, Summary, "ErrorEvent"]


class ErrorEvent:
    def __init__(self, message: str):
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"ErrorEvent({self.message!r})"


def parse_line(line: str) -> ParsedEvent | None:
    """Parse a single json-stream line into a model, or ``None`` to skip."""
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None

    event = obj.get("event")
    data = obj.get("data", {})

    if event == "start":
        return _parse_start(data)
    if event == "interval":
        return _parse_interval(data)
    if event == "end":
        return _parse_summary(data)
    if event == "error":
        return ErrorEvent(str(data) if data else "unknown error")
    return None


def parse_lines(lines: Iterator[str]) -> Iterator[ParsedEvent]:
    for line in lines:
        parsed = parse_line(line)
        if parsed is not None:
            yield parsed


def _parse_start(data: dict) -> StartInfo:
    test_start = data.get("test_start", {}) or {}
    proto = test_start.get("protocol", "TCP")
    return StartInfo(
        version=data.get("version", ""),
        connecting_to=_format_target(data.get("connecting_to")),
        protocol=proto,
        num_streams=int(test_start.get("num_streams", 1) or 1),
        reverse=bool(test_start.get("reverse", 0)),
    )


def _format_target(connecting_to) -> str:
    if isinstance(connecting_to, dict):
        host = connecting_to.get("host", "")
        port = connecting_to.get("port", "")
        return f"{host}:{port}" if port else str(host)
    return str(connecting_to or "")


def _parse_interval(data: dict) -> Interval:
    summ = data.get("sum", {}) or {}
    reverse = data.get("sum_bidir_reverse") or {}
    streams = []
    for s in data.get("streams", []) or []:
        streams.append(
            StreamSample(
                socket=int(s.get("socket", 0) or 0),
                bits_per_second=float(s.get("bits_per_second", 0.0) or 0.0),
                retransmits=_opt_int(s.get("retransmits")),
                sender=bool(s.get("sender", True)),
            )
        )
    return Interval(
        start=float(summ.get("start", 0.0) or 0.0),
        end=float(summ.get("end", 0.0) or 0.0),
        seconds=float(summ.get("seconds", 0.0) or 0.0),
        bits_per_second=float(summ.get("bits_per_second", 0.0) or 0.0),
        bytes=int(summ.get("bytes", 0) or 0),
        retransmits=_opt_int(summ.get("retransmits")),
        packets=_opt_int(summ.get("packets")),
        jitter_ms=_opt_float(summ.get("jitter_ms")),
        lost_percent=_opt_float(summ.get("lost_percent")),
        omitted=bool(summ.get("omitted", False)),
        reverse_bps=_opt_float(reverse.get("bits_per_second")),
        streams=streams,
    )


def _parse_summary(data: dict) -> Summary:
    sent = data.get("sum_sent", {}) or {}
    received = data.get("sum_received", {}) or {}
    # UDP puts everything under "sum"
    udp_sum = data.get("sum", {}) or {}
    cpu = data.get("cpu_utilization_percent", {}) or {}
    bidir_sent = data.get("sum_sent_bidir_reverse") or {}
    bidir_received = data.get("sum_received_bidir_reverse") or {}
    return Summary(
        sent_bps=float(sent.get("bits_per_second", udp_sum.get("bits_per_second", 0.0)) or 0.0),
        received_bps=float(
            received.get("bits_per_second", udp_sum.get("bits_per_second", 0.0)) or 0.0
        ),
        bidir_sent_bps=_opt_float(bidir_sent.get("bits_per_second")),
        bidir_received_bps=_opt_float(bidir_received.get("bits_per_second")),
        retransmits=_opt_int(sent.get("retransmits")),
        jitter_ms=_opt_float(udp_sum.get("jitter_ms") or received.get("jitter_ms")),
        lost_percent=_opt_float(udp_sum.get("lost_percent") or received.get("lost_percent")),
        cpu_local=_opt_float(cpu.get("host_total")),
        cpu_remote=_opt_float(cpu.get("remote_total")),
    )


def _opt_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
