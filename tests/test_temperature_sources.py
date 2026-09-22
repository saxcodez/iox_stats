"""Temperature source chain: helper -> IOHID fallback, logging of failures, launch info, LaunchAgent workdir."""

import json
import plistlib
import time

from iox_stats import iohid_temp
from iox_stats.autostart import Autostart
from iox_stats.share import write_launch_info
from iox_stats.temperature import MacTempProvider


def test_cpu_temperature_prefers_die_sensors():
    sensors = {"PMU tdie1": 50.0, "PMU tdie2": 54.0, "PMU tdev1": 40.0, "gas gauge battery": 30.0}
    assert iohid_temp.cpu_temperature(sensors) == 52.0
    assert iohid_temp.cpu_temperature({"SOC MTR Temp Sensor0": 45.0, "NAND CH0 temp": 35.0}) == 45.0
    assert iohid_temp.cpu_temperature({"pACC MTR Temp Sensor2": 60.0, "eACC MTR Temp Sensor0": 50.0}) == 55.0
    assert iohid_temp.cpu_temperature({}) is None


def test_iohid_is_inert_off_macos():
    assert iohid_temp.read_sensors() == {}          # tests run on Linux
    assert iohid_temp.probe() is None


def _provider(monkeypatch, probe_value, read_value=48.5):
    monkeypatch.setattr("iox_stats.temperature.MacTempProvider.supported", staticmethod(lambda: True))
    monkeypatch.setattr("iox_stats.temperature.platform.machine", lambda: "arm64")
    return MacTempProvider(interval_ms=50, iohid_probe=lambda: probe_value, iohid_read=lambda: read_value)


def _wait(cond, seconds=3.0):
    end = time.time() + seconds
    while time.time() < end and not cond():
        time.sleep(0.02)
    return cond()


def test_no_helper_uses_iohid_when_probe_works(monkeypatch):
    prov = _provider(monkeypatch, probe_value=47.0)
    monkeypatch.setattr(prov, "detect", lambda: None)
    prov.start()
    try:
        assert _wait(lambda: prov.value == 48.5) and prov.tool == "iohid"
    finally:
        prov.stop()


def test_no_helper_and_no_iohid_reports_the_reason(monkeypatch):
    prov = _provider(monkeypatch, probe_value=None)
    monkeypatch.setattr(prov, "detect", lambda: None)
    prov.start()
    try:
        assert _wait(lambda: prov.last_error is not None)
        assert prov.value is None and "no temperature helper" in prov.last_error
    finally:
        prov.stop()


def test_broken_macmon_falls_back_to_iohid(monkeypatch, tmp_path):
    fake = tmp_path / "macmon"
    fake.write_text('#!/bin/sh\necho \'{"temp":{"cpu_temp_avg":0}}\'\necho "sensor error" >&2\nexit 3\n')
    fake.chmod(0o755)
    prov = _provider(monkeypatch, probe_value=50.0)

    def detect():
        prov.path = str(fake)
        return "macmon"

    monkeypatch.setattr(prov, "detect", detect)
    prov.start()
    try:
        assert _wait(lambda: prov.tool == "iohid" and prov.value == 48.5)
        assert "exit code 3" in prov.last_error and "sensor error" in prov.last_error
    finally:
        prov.stop()


def test_working_macmon_is_used(monkeypatch, tmp_path):
    fake = tmp_path / "macmon"
    fake.write_text('#!/bin/sh\nwhile true; do echo \'{"temp":{"cpu_temp_avg":61.5}}\'; sleep 0.05; done\n')
    fake.chmod(0o755)
    prov = _provider(monkeypatch, probe_value=50.0)

    def detect():
        prov.path = str(fake)
        return "macmon"

    monkeypatch.setattr(prov, "detect", detect)
    prov.start()
    try:
        assert _wait(lambda: prov.value == 61.5) and prov.tool == "macmon"
    finally:
        prov.stop()


def test_launch_info_has_a_runnable_command(tmp_path):
    target = tmp_path / "launch.json"
    assert write_launch_info(target)
    data = json.loads(target.read_text())
    assert "-m iox_stats" in data["command"] and data["project_dir"]


def test_launch_agent_sets_working_directory(tmp_path):
    auto = Autostart(platform="darwin", home=tmp_path, command=["/venv/bin/python", "-m", "iox_stats", "--background"],
                     workdir=tmp_path / "proj")
    assert auto.enable()
    agent = plistlib.loads(auto.path.read_bytes())
    assert agent["WorkingDirectory"] == str(tmp_path / "proj")
    assert agent["EnvironmentVariables"]["PYTHONPATH"] == str(tmp_path / "proj")


def test_diagnose_cli_runs(capsys):
    from iox_stats.app import main

    assert main(["--diagnose"]) == 0
    out = capsys.readouterr().out
    assert "[what the app uses]" in out and "[widget hand-over]" in out
