import sys
import types

from iox_stats.autostart import APP_ID, BACKGROUND_FLAG, Autostart, launch_command


def test_launch_command_source_and_frozen():
    assert launch_command(frozen=False, executable="/usr/bin/python3") == [
        "/usr/bin/python3", "-m", "iox_stats", BACKGROUND_FLAG]
    assert launch_command(frozen=True, executable="/Apps/IOX Stats") == ["/Apps/IOX Stats", BACKGROUND_FLAG]


def test_macos_launch_agent_roundtrip(tmp_path):
    import plistlib

    a = Autostart(platform="darwin", home=tmp_path, command=["/x/python", "-m", "iox_stats", BACKGROUND_FLAG])
    assert not a.is_enabled()                       # nothing installed by default
    assert a.enable() and a.is_enabled()
    plist = tmp_path / "Library" / "LaunchAgents" / f"{APP_ID}.plist"
    data = plistlib.loads(plist.read_bytes())
    assert data["RunAtLoad"] is True and data["ProgramArguments"][-1] == BACKGROUND_FLAG
    assert a.disable() and not a.is_enabled() and not plist.exists()
    assert a.disable()                              # idempotent


def test_linux_desktop_entry_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    a = Autostart(platform="linux", home=tmp_path, command=["/usr/bin/python3", "-m", "iox_stats", BACKGROUND_FLAG])
    assert a.enable()
    text = (tmp_path / ".config" / "autostart" / "iox-stats.desktop").read_text()
    assert "Exec=/usr/bin/python3 -m iox_stats --background" in text and "Type=Application" in text
    assert a.disable() and not a.is_enabled()


def test_windows_registry_roundtrip(monkeypatch):
    store = {}

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def query(key, name):
        if name not in store:
            raise FileNotFoundError(name)
        return store[name], 1

    fake = types.SimpleNamespace(
        HKEY_CURRENT_USER=1, REG_SZ=1, KEY_SET_VALUE=2,
        OpenKey=lambda root, path, *a: Key(),
        CreateKey=lambda root, path: Key(),
        SetValueEx=lambda key, name, r, t, value: store.__setitem__(name, value),
        QueryValueEx=query,
        DeleteValue=lambda key, name: store.pop(name),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake)
    exe = "C:\\Program Files\\IOX Stats\\IOX Stats.exe"
    a = Autostart(platform="win32", command=[exe, BACKGROUND_FLAG])
    assert not a.is_enabled()
    assert a.enable() and a.is_enabled()
    assert store["IOX Stats"] == f'"{exe}" {BACKGROUND_FLAG}'
    assert a.disable() and not a.is_enabled()


def test_enable_failure_is_reported_not_raised(tmp_path):
    blocker = tmp_path / "Library"
    blocker.write_text("a file, so the LaunchAgents folder cannot be created")
    a = Autostart(platform="darwin", home=tmp_path, command=["x"])
    assert a.enable() is False and not a.is_enabled()


def test_unsupported_platform():
    a = Autostart(platform="plan9", command=["x"])
    assert not a.supported and a.enable() is False
