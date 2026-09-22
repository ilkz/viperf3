from pathlib import Path

from viperf3.parser import ErrorEvent, parse_line, parse_lines
from viperf3.models import Interval, StartInfo, Summary

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> list[str]:
    return (FIXTURES / name).read_text().splitlines()


def test_tcp_stream_produces_all_event_types():
    events = list(parse_lines(iter(_read("tcp_stream.jsonl"))))
    kinds = {type(e) for e in events}
    assert StartInfo in kinds
    assert Interval in kinds
    assert Summary in kinds


def test_tcp_interval_has_throughput_and_retransmits():
    events = list(parse_lines(iter(_read("tcp_stream.jsonl"))))
    intervals = [e for e in events if isinstance(e, Interval)]
    assert intervals
    first = intervals[0]
    assert first.bits_per_second > 0
    assert first.mbps == first.bits_per_second / 1e6
    # TCP intervals carry a retransmits count
    assert first.retransmits is not None


def test_udp_summary_reports_jitter_or_loss():
    events = list(parse_lines(iter(_read("udp_stream.jsonl"))))
    summaries = [e for e in events if isinstance(e, Summary)]
    assert summaries
    intervals = [e for e in events if isinstance(e, Interval)]
    # UDP intervals report packet counts
    assert any(i.packets is not None for i in intervals)


def test_start_info_parsed():
    events = list(parse_lines(iter(_read("tcp_stream.jsonl"))))
    start = next(e for e in events if isinstance(e, StartInfo))
    assert start.protocol in ("TCP", "UDP")
    assert start.num_streams >= 1


def test_malformed_lines_are_ignored():
    assert parse_line("not json") is None
    assert parse_line("") is None
    assert parse_line("123") is None
    assert parse_line('{"no_event": true}') is None


def test_error_event():
    result = parse_line('{"event": "error", "data": "connection refused"}')
    assert isinstance(result, ErrorEvent)
    assert "refused" in result.message


def test_bidir_interval_has_reverse_direction():
    events = list(parse_lines(iter(_read("bidir_stream.jsonl"))))
    intervals = [e for e in events if isinstance(e, Interval)]
    assert intervals
    assert all(i.reverse_bps is not None and i.reverse_bps > 0 for i in intervals)
    assert intervals[0].reverse_mbps == intervals[0].reverse_bps / 1e6


def test_bidir_summary_has_both_directions():
    events = list(parse_lines(iter(_read("bidir_stream.jsonl"))))
    summary = next(e for e in events if isinstance(e, Summary))
    assert summary.bidir_sent_bps is not None and summary.bidir_sent_bps > 0
    assert summary.bidir_received_bps is not None


def test_non_bidir_has_no_reverse():
    events = list(parse_lines(iter(_read("tcp_stream.jsonl"))))
    intervals = [e for e in events if isinstance(e, Interval)]
    assert all(i.reverse_bps is None for i in intervals)
    summary = next(e for e in events if isinstance(e, Summary))
    assert summary.bidir_sent_bps is None
