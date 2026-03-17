from pathlib import Path

from scripts.build_client_release import (
    build_pyinstaller_command,
    get_release_targets,
    render_release_readme,
    write_script_bundle,
)


def test_get_release_targets_includes_personal_pc_and_mobile():
    targets = get_release_targets()

    assert "personal_pc" in targets
    assert "mobile_device" in targets
    assert targets["personal_pc"].script_path.name == "personal_pc_client_app.py"
    assert targets["mobile_device"].script_path.name == "mobile_device_client.py"


def test_render_release_readme_mentions_script_and_exe():
    target = get_release_targets()["personal_pc"]

    readme = render_release_readme(target)

    assert "个人 PC 客户端 Release" in readme
    assert "EXE" in readme
    assert "run_personal_pc_gui.bat" in readme
    assert "run_personal_pc_headless.bat" in readme
    assert "run_personal_pc_minimized.bat" in readme
    assert target.sample_command in readme


def test_build_pyinstaller_command_targets_onefile_binary(tmp_path: Path):
    target = get_release_targets()["personal_pc"]

    command = build_pyinstaller_command(
        target=target,
        dist_dir=tmp_path / "dist",
        work_dir=tmp_path / "build",
        spec_dir=tmp_path / "spec",
    )

    assert command[0].endswith("python.exe") or command[0].endswith("python")
    assert "--onefile" in command
    assert "--windowed" in command
    assert "--name" in command
    assert target.executable_name in command
    assert str(target.script_path) == command[-1]


def test_write_script_bundle_copies_runtime_dependencies(tmp_path: Path):
    target = get_release_targets()["personal_pc"]

    target_root = write_script_bundle(target, tmp_path)

    assert target_root == tmp_path / "personal_pc"
    assert (target_root / "script" / "scripts" / "personal_pc_client_app.py").exists()
    assert (target_root / "script" / "scripts" / "personal_pc_client.py").exists()
    assert (target_root / "script" / "app" / "services" / "telemetry_client.py").exists()
    assert (target_root / "script" / "run_personal_pc_gui.bat").exists()
    assert (target_root / "script" / "run_personal_pc_headless.bat").exists()
    assert (target_root / "script" / "run_personal_pc_minimized.bat").exists()
