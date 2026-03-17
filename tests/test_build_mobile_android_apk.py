from pathlib import Path

from scripts.build_mobile_android_apk import (
    format_local_properties_sdk_dir,
    get_debug_apk_path,
    resolve_android_sdk_root,
)


def test_format_local_properties_sdk_dir_escapes_backslashes():
    formatted = format_local_properties_sdk_dir(Path(r"C:\Android\Sdk"))

    assert formatted == r"C:\\Android\\Sdk"


def test_get_debug_apk_path_points_to_default_debug_output(tmp_path: Path):
    apk_path = get_debug_apk_path(tmp_path)

    assert apk_path == tmp_path / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"


def test_resolve_android_sdk_root_prefers_environment(monkeypatch, tmp_path: Path):
    sdk_dir = tmp_path / "Sdk"
    sdk_dir.mkdir()
    monkeypatch.setenv("ANDROID_HOME", str(sdk_dir))
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    resolved = resolve_android_sdk_root()

    assert resolved == sdk_dir
