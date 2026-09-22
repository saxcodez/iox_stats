"""CPU temperature helper: finding, status, install command, install runner (all without touching a real system)."""

import subprocess
import types

from iox_stats import helpers


def test_find_tool_falls_back_to_homebrew_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")                        # like an app started at login
    tool = tmp_path / "macmon"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)
    assert helpers.find_tool("macmon", [str(tmp_path)]) == str(tool)
    assert helpers.find_tool("nope", [str(tmp_path)]) is None


def test_find_tool_ignores_non_executable_files(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    (tmp_path / "macmon").write_text("x")
    assert helpers.find_tool("macmon", [str(tmp_path)]) is None


def test_recommended_tool_per_cpu():
    assert helpers.recommended_tool("arm64") == "macmon"
    assert helpers.recommended_tool("x86_64") == "osx-cpu-temp"


def _finder(installed):
    return lambda name: f"/opt/homebrew/bin/{name}" if name in installed else None


def test_status_needs_nothing_outside_macos():
    st = helpers.status("linux", "x86_64", _finder([]))
    assert not st.supported and st.ready and not st.can_install and not st.needs_homebrew


def test_status_macos_variants():
    missing = helpers.status("darwin", "arm64", _finder(["brew"]))
    assert missing.supported and not missing.ready and missing.can_install and missing.recommended == "macmon"
    assert "not set up" in missing.summary()

    no_brew = helpers.status("darwin", "arm64", _finder([]))
    assert no_brew.needs_homebrew and not no_brew.can_install and "Homebrew" in no_brew.summary()

    ready = helpers.status("darwin", "arm64", _finder(["macmon", "brew"]))
    assert ready.ready and ready.tool == "macmon" and "macmon active" in ready.summary()

    other = helpers.status("darwin", "arm64", _finder(["osx-cpu-temp"]))      # only the other tool is present
    assert other.tool == "osx-cpu-temp"


def test_install_command_and_environment():
    st = helpers.status("darwin", "x86_64", _finder(["brew"]))
    assert helpers.install_command(st) == ["/opt/homebrew/bin/brew", "install", "osx-cpu-temp"]
    assert helpers.install_command(helpers.status("darwin", "arm64", _finder([]))) == []
    env = helpers.install_environment()
    assert env["HOMEBREW_NO_AUTO_UPDATE"] == "1" and "/opt/homebrew/bin" in env["PATH"]


def test_run_install_success_and_failure():
    st = helpers.status("darwin", "arm64", _finder(["brew"]))
    calls = []

    def ok(cmd, **kw):
        calls.append((cmd, kw))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    assert helpers.run_install(st, ok) == (True, "macmon installed.")
    assert calls[0][0][1:] == ["install", "macmon"] and "sudo" not in calls[0][0]

    def fail(cmd, **kw):
        return types.SimpleNamespace(returncode=1, stdout="", stderr="line1\nline2\nError: no such formula")

    ok_, msg = helpers.run_install(st, fail)
    assert not ok_ and "no such formula" in msg

    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    assert helpers.run_install(st, boom)[0] is False
    ok_, msg = helpers.run_install(helpers.status("darwin", "arm64", _finder([])))
    assert not ok_ and "Homebrew" in msg


def test_install_async_reports_from_thread():
    st = helpers.status("darwin", "arm64", _finder(["brew"]))
    got = []
    runner = lambda cmd, **kw: types.SimpleNamespace(returncode=0, stdout="", stderr="")  # noqa: E731
    helpers.install_async(st, lambda ok, msg: got.append((ok, msg)), runner).join(timeout=5)
    assert got == [(True, "macmon installed.")]
