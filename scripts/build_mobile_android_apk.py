"""Build the Android mobile client APK and copy it into dist/clients."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANDROID_PROJECT_ROOT = PROJECT_ROOT / "android" / "mobile-client"
DIST_APK_PATH = PROJECT_ROOT / "dist" / "clients" / "mobile_android" / "device_sentinel_mobile_client-debug.apk"


def resolve_android_sdk_root() -> Path:
    candidates = [
        os.getenv("ANDROID_HOME"),
        os.getenv("ANDROID_SDK_ROOT"),
        str(Path(os.getenv("LOCALAPPDATA", "")) / "Android" / "Sdk") if os.getenv("LOCALAPPDATA") else None,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    raise FileNotFoundError("未找到 Android SDK。请先安装 Android SDK，或设置 ANDROID_HOME / ANDROID_SDK_ROOT。")


def format_local_properties_sdk_dir(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\")


def ensure_local_properties(project_dir: Path, sdk_root: Path) -> Path:
    local_properties_path = project_dir / "local.properties"
    local_properties_path.write_text(
        f"sdk.dir={format_local_properties_sdk_dir(sdk_root)}\n",
        encoding="utf-8",
    )
    return local_properties_path


def get_gradle_wrapper(project_dir: Path) -> Path:
    wrapper_name = "gradlew.bat" if os.name == "nt" else "gradlew"
    wrapper_path = project_dir / wrapper_name
    if not wrapper_path.exists():
        raise FileNotFoundError(
            f"未找到 {wrapper_name}。请先在 Android 工程目录生成 Gradle wrapper。"
        )
    return wrapper_path


def get_debug_apk_path(project_dir: Path) -> Path:
    return project_dir / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"


def build_apk(
    *,
    project_dir: Path,
    output_path: Path,
    gradle_task: str = "assembleDebug",
) -> Path:
    sdk_root = resolve_android_sdk_root()
    ensure_local_properties(project_dir, sdk_root)
    gradle_wrapper = get_gradle_wrapper(project_dir)

    env = os.environ.copy()
    env.setdefault("ANDROID_HOME", str(sdk_root))
    env.setdefault("ANDROID_SDK_ROOT", str(sdk_root))

    subprocess.run(
        [str(gradle_wrapper), gradle_task],
        cwd=project_dir,
        env=env,
        check=True,
    )

    apk_path = get_debug_apk_path(project_dir)
    if not apk_path.exists():
        raise FileNotFoundError(f"Gradle 已执行，但未找到 APK：{apk_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(apk_path, output_path)
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Android mobile client APK.")
    parser.add_argument("--project-dir", default=str(ANDROID_PROJECT_ROOT))
    parser.add_argument("--output-path", default=str(DIST_APK_PATH))
    parser.add_argument("--gradle-task", default="assembleDebug")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    apk_path = build_apk(
        project_dir=Path(args.project_dir).resolve(),
        output_path=Path(args.output_path).resolve(),
        gradle_task=args.gradle_task,
    )
    print(apk_path)


if __name__ == "__main__":
    main()
