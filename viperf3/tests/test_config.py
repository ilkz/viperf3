from viperf3.config import ClientConfig


def test_default_config_is_valid():
    assert ClientConfig().validate() == []


def test_to_args_basic():
    cfg = ClientConfig(host="example.com", port=5201, duration=10, parallel=4)
    args = cfg.to_args()
    assert "-c" in args and "example.com" in args
    assert "-P" in args and "4" in args
    assert "--json-stream" in args
    assert "-p" in args and "5201" in args


def test_to_args_udp_with_bitrate():
    cfg = ClientConfig(udp=True, bitrate="100M")
    args = cfg.to_args()
    assert "-u" in args
    assert "-b" in args and "100M" in args


def test_to_args_reverse_and_window():
    cfg = ClientConfig(reverse=True, window="256K", omit=2)
    args = cfg.to_args()
    assert "-R" in args
    assert "-w" in args and "256K" in args
    assert "-O" in args and "2" in args


def test_validation_errors():
    cfg = ClientConfig(host="", port=99999, duration=0, parallel=0)
    errors = cfg.validate()
    assert len(errors) >= 3


def test_reverse_and_bidir_conflict():
    cfg = ClientConfig(reverse=True, bidir=True)
    assert any("bidir" in e.lower() for e in cfg.validate())


def test_interval_formatting():
    assert "-i" in ClientConfig(interval=1.0).to_args()
    args = ClientConfig(interval=0.5).to_args()
    idx = args.index("-i")
    assert args[idx + 1] == "0.5"
