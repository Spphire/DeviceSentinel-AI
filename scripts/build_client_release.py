"""Build distributable client bundles for telemetry scripts."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = PROJECT_ROOT / "dist" / "clients"


@dataclass(frozen=True)
class ReleaseTarget:
    target_id: str
    display_name: str
    script_path: Path
    executable_name: str
    sample_command: str
    description: str
    bundle_files: tuple[Path, ...]
    launchers: tuple["ReleaseLauncher", ...]
    pyinstaller_windowed: bool = False


@dataclass(frozen=True)
class ReleaseLauncher:
    filename: str
    script_relative_path: str
    default_args: str = ""


def get_release_targets(project_root: Path | None = None) -> dict[str, ReleaseTarget]:
    root = project_root or PROJECT_ROOT
    return {
        "personal_pc": ReleaseTarget(
            target_id="personal_pc",
            display_name="个人 PC 客户端",
            script_path=root / "scripts" / "personal_pc_client_app.py",
            executable_name="personal_pc_client",
            sample_command=(
                "python scripts/personal_pc_client_app.py --instance-id personal_pc_real-demo "
                "--gateway-host 192.168.1.10 --gateway-port 10570 --gateway-path /telemetry"
            ),
            description="默认打开图形界面，支持填写网关地址、查看资源曲线，并可追加 --headless 无界面运行。",
            bundle_files=(
                root / "scripts" / "personal_pc_client_app.py",
                root / "scripts" / "personal_pc_client.py",
                root / "app" / "services" / "telemetry_client.py",
            ),
            launchers=(
                ReleaseLauncher(
                    filename="run_personal_pc_gui.bat",
                    script_relative_path=r"scripts\personal_pc_client_app.py",
                ),
                ReleaseLauncher(
                    filename="run_personal_pc_headless.bat",
                    script_relative_path=r"scripts\personal_pc_client_app.py",
                    default_args="--headless",
                ),
            ),
            pyinstaller_windowed=True,
        ),
        "temp_humidity": ReleaseTarget(
            target_id="temp_humidity",
            display_name="温湿度客户端",
            script_path=root / "scripts" / "temp_humidity_client.py",
            executable_name="temp_humidity_client",
            sample_command=(
                "python temp_humidity_client.py --instance-id temp_humidity_real-demo "
                "--gateway-host 192.168.1.10 --gateway-port 10570 --gateway-path /telemetry --simulate"
            ),
            description="上报温湿度设备指标，支持固定值和模拟模式。",
            bundle_files=(
                root / "scripts" / "temp_humidity_client.py",
                root / "app" / "services" / "telemetry_client.py",
            ),
            launchers=(
                ReleaseLauncher(
                    filename="run_temp_humidity_client.bat",
                    script_relative_path=r"scripts\temp_humidity_client.py",
                ),
            ),
        ),
        "mobile_device": ReleaseTarget(
            target_id="mobile_device",
            display_name="手机端客户端",
            script_path=root / "scripts" / "mobile_device_client.py",
            executable_name="mobile_device_client",
            sample_command=(
                "python mobile_device_client.py --instance-id mobile_device_real-demo "
                "--gateway-host 192.168.1.10 --gateway-port 10570 --gateway-path /telemetry --simulate"
            ),
            description="支持 Android/Termux 实机采集，也支持桌面模拟手机指标。",
            bundle_files=(
                root / "scripts" / "mobile_device_client.py",
                root / "app" / "services" / "telemetry_client.py",
            ),
            launchers=(
                ReleaseLauncher(
                    filename="run_mobile_device_client.bat",
                    script_relative_path=r"scripts\mobile_device_client.py",
                ),
            ),
        ),
    }


def build_pyinstaller_command(
    *,
    target: ReleaseTarget,
    dist_dir: Path,
    work_dir: Path,
    spec_dir: Path,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        target.executable_name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
    ]
    if target.pyinstaller_windowed:
        command.append("--windowed")
    command.append(str(target.script_path))
    return command


def render_release_readme(target: ReleaseTarget) -> str:
    launcher_lines = "\n".join(f"- {launcher.filename}" for launcher in target.launchers) or "- 无"
    return textwrap.dedent(
        f"""\
        {target.display_name} Release
        ============================

        说明：
        - {target.description}
        - 脚本版可直接使用当前目录中的 `.py` 文件运行
        - EXE 版仅在 Windows 且已安装 `PyInstaller` 时生成
        - 脚本包会一并携带运行所需的共享上报辅助层

        脚本示例：
        {target.sample_command}

        内置启动器：
        {launcher_lines}

        如果生成了 EXE，可改为：
        .\\{target.executable_name}.exe --instance-id <设备ID> --gateway-host <仪表盘IP> --gateway-port 10570 --gateway-path /telemetry
        """
    )


def _copy_bundle_files(target: ReleaseTarget, bundle_dir: Path) -> None:
    for file_path in target.bundle_files:
        relative_path = file_path.relative_to(PROJECT_ROOT)
        destination = bundle_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, destination)


def _write_launchers(target: ReleaseTarget, bundle_dir: Path) -> None:
    for launcher in target.launchers:
        launcher_path = bundle_dir / launcher.filename
        default_args = f" {launcher.default_args}" if launcher.default_args else ""
        launcher_path.write_text(
            (
                "@echo off\r\n"
                f'python "%~dp0{launcher.script_relative_path}"{default_args} %*\r\n'
            ),
            encoding="utf-8",
        )


def write_script_bundle(target: ReleaseTarget, output_dir: Path) -> Path:
    target_root = output_dir / target.target_id
    bundle_dir = target_root / "script"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    _copy_bundle_files(target, bundle_dir)
    _write_launchers(target, bundle_dir)

    readme_path = target_root / "README.txt"
    readme_path.write_text(render_release_readme(target), encoding="utf-8")
    return target_root


def build_release(
    *,
    target: ReleaseTarget,
    output_dir: Path,
    include_script: bool,
    include_exe: bool,
) -> dict[str, str]:
    result: dict[str, str] = {}
    target_root = output_dir / target.target_id
    target_root.mkdir(parents=True, exist_ok=True)

    if include_script:
        result["script_bundle"] = str(write_script_bundle(target, output_dir))

    if include_exe:
        exe_dir = target_root / "exe"
        work_dir = target_root / "build"
        spec_dir = target_root / "spec"
        exe_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        spec_dir.mkdir(parents=True, exist_ok=True)

        command = build_pyinstaller_command(
            target=target,
            dist_dir=exe_dir,
            work_dir=work_dir,
            spec_dir=spec_dir,
        )
        subprocess.run(command, check=True, cwd=PROJECT_ROOT)
        result["exe_bundle"] = str(exe_dir / f"{target.executable_name}.exe")

    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build script/exe release bundles for telemetry clients.")
    parser.add_argument("--target", choices=sorted(get_release_targets().keys()) + ["all"], default="personal_pc")
    parser.add_argument("--output-dir", default=str(RELEASE_ROOT))
    parser.add_argument(
        "--format",
        choices=["script", "exe", "both"],
        default="both",
        help="Whether to output the Python script bundle, an EXE, or both.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    targets = get_release_targets()
    selected_targets = targets.values() if args.target == "all" else [targets[args.target]]
    include_script = args.format in {"script", "both"}
    include_exe = args.format in {"exe", "both"}

    for target in selected_targets:
        result = build_release(
            target=target,
            output_dir=output_dir,
            include_script=include_script,
            include_exe=include_exe,
        )
        print(f"[{target.target_id}] {result}")


if __name__ == "__main__":
    main()
