from viperf3.netinfo import egress_interface, link_speed_mbps


def test_loopback_interface():
    assert egress_interface("127.0.0.1") == "lo"


def test_unresolvable_host():
    assert egress_interface("definitely-not-a-real-host.invalid") is None


def test_loopback_has_no_link_speed():
    # sysfs does not report a speed for lo
    assert link_speed_mbps("lo") is None


def test_unknown_interface_speed():
    assert link_speed_mbps("no-such-iface0") is None
