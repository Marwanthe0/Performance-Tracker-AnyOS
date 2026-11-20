"""
test_monitor.py - Verification test suite for SystemMonitor and Sparkline.
"""

import time
import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from performance_track.monitor import SystemMonitor
from performance_track.sparkline import (
    generate_sparkline,
    generate_bar,
    format_bytes,
    format_rate,
    format_short_rate
)

def test_sparkline():
    assert generate_sparkline([]) == ""
    assert generate_sparkline([0, 50, 100]) == " ▅█"
    bar = generate_bar(50, width=10)
    assert bar == "[█████░░░░░]"
    assert format_bytes(1024) == "1.0 KB"
    assert format_rate(1024 * 1024) == "1.0 MB/s"
    assert format_short_rate(1024 * 1024 * 2.5) == "2.5M"
    print("Sparkline tests passed!")

def test_monitor():
    monitor = SystemMonitor(history_size=30)
    time.sleep(0.5)
    data = monitor.update()

    # CPU checks
    assert 'cpu' in data
    assert 0.0 <= data['cpu']['percent'] <= 100.0
    assert len(data['cpu']['cores']) > 0
    assert len(data['cpu']['load']) == 3
    print(f"CPU Verified: {data['cpu']['percent']:.1f}% across {data['cpu']['cores_count']} cores")

    # RAM checks
    assert 'ram' in data
    assert data['ram']['total'] > 0
    assert 0.0 <= data['ram']['percent'] <= 100.0
    print(f"RAM Verified: {data['ram']['percent']:.1f}% ({format_bytes(data['ram']['used'])} / {format_bytes(data['ram']['total'])})")

    # Performance Track checks
    assert 'track' in data
    assert data['track']['net_rx_rate'] >= 0.0
    assert data['track']['net_tx_rate'] >= 0.0
    assert data['track']['disk_read_rate'] >= 0.0
    assert data['track']['disk_write_rate'] >= 0.0
    print(f"Performance Track Verified: Net ↓ {format_rate(data['track']['net_rx_rate'])}, Disk {format_rate(data['track']['disk_read_rate'] + data['track']['disk_write_rate'])}")

    # Top processes check
    cpu_procs = monitor.get_top_processes(count=3, sort_by='cpu')
    assert len(cpu_procs) > 0
    print(f"Top CPU Process Verified: {cpu_procs[0]['name']} ({cpu_procs[0]['cpu']}%)")

    mem_procs = monitor.get_top_processes(count=3, sort_by='mem')
    assert len(mem_procs) > 0
    print(f"Top RAM Process Verified: {mem_procs[0]['name']} ({mem_procs[0]['mem']}%)")

    print("All SystemMonitor tests passed successfully!")

def test_config():
    from performance_track.config import Config
    cfg = Config()
    assert cfg.get("update_interval") is not None
    assert cfg.get("display_mode") in ["balanced", "sparkline", "compact", "minimal", "detailed"]
    print("Config tests passed!")

def test_system():
    monitor = SystemMonitor(history_size=10)
    data = monitor.update()
    assert "system" in data
    assert "hostname" in data["system"]
    assert "kernel" in data["system"]
    assert len(data["system"]["hostname"]) > 0
    print(f"System Info Verified: Host {data['system']['hostname']} on {data['system']['kernel']}")

if __name__ == '__main__':
    test_sparkline()
    test_config()
    test_system()
    test_monitor()
