import socket
import threading

from iox_stats.collectors import Collector, Snapshot, fmt_bytes, fmt_rate, fmt_uptime, measure_ping


def test_sample_returns_sane_values():
    c = Collector()
    c.sample()
    s = c.sample()
    assert isinstance(s, Snapshot)
    assert 0 <= s.cpu_percent <= 100
    assert 0 <= s.ram_percent <= 100
    assert s.ram_total > 0 and s.disk_total > 0
    assert 0 <= s.disk_percent <= 100
    assert s.net_down_bps >= 0 and s.net_up_bps >= 0
    assert s.uptime_s > 0
    assert len(s.cpu_per_core) >= 1
    assert s.ping_pending is True  # no ping thread started


def test_snapshot_to_dict_roundtrip():
    d = Snapshot(cpu_percent=5).to_dict()
    assert d["cpu_percent"] == 5 and "ping_ms" in d


def test_ping_injection():
    c = Collector()
    c.set_ping_result(12.5)
    s = c.sample()
    assert s.ping_ms == 12.5 and s.ping_ok and not s.ping_pending
    c.set_ping_result(None)
    s = c.sample()
    assert s.ping_ms is None and not s.ping_ok and not s.ping_pending


def test_measure_ping_local_server_and_unreachable():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    accepted = threading.Thread(target=lambda: srv.accept(), daemon=True)
    accepted.start()
    ms = measure_ping("127.0.0.1", port, timeout=1)
    assert ms is not None and ms < 500
    accepted.join(timeout=2)        # the accept must be finished before the port is closed (else a race)
    srv.close()
    assert measure_ping("127.0.0.1", port, timeout=0.5) is None


def test_ping_thread_updates_state():
    c = Collector(ping_host="127.0.0.1", ping_port=9, ping_interval=0.1)  # port 9: refused -> offline
    c.start()
    try:
        import time

        for _ in range(30):
            if not c.sample().ping_pending:
                break
            time.sleep(0.1)
        s = c.sample()
        assert not s.ping_pending and s.ping_ms is None
    finally:
        c.stop()


def test_formatters():
    assert fmt_bytes(0) == "0 B"
    assert fmt_bytes(1536) == "1.5 KB"
    assert fmt_bytes(5 * 1024**3) == "5.0 GB"
    assert fmt_rate(2048) == "2.0 KB/s"
    assert fmt_uptime(59) == "0m"
    assert fmt_uptime(3600 * 5 + 60 * 7) == "5h 7m"
    assert fmt_uptime(86400 * 2 + 3600 * 3) == "2d 3h"
