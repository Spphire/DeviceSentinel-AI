"""Run a local command line demo of the monitoring workflow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.demo_service import run_local_demo


def main() -> None:
    result = run_local_demo()
    print("=== 模拟设备数据 ===")
    print(json.dumps(result["reading"], ensure_ascii=False, indent=2))
    print("\n=== 分析结果 ===")
    print(json.dumps(result["analysis"], ensure_ascii=False, indent=2))
    print("\n=== AI 总结报告 ===")
    print(result["report"])


if __name__ == "__main__":
    main()
