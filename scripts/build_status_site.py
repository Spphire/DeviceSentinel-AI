"""Build a static status site from a live or dispatched monitoring snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.status_publisher import (
    build_status_snapshot,
    extract_snapshot_from_event_payload,
    render_status_site,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the static monitoring status site.")
    parser.add_argument("--output-dir", default="site")
    parser.add_argument("--event-path")
    parser.add_argument("--snapshot-file")
    parser.add_argument("--history-window", type=int)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()

    snapshot: dict | None = None
    if args.snapshot_file:
        snapshot = json.loads(Path(args.snapshot_file).read_text(encoding="utf-8"))
    elif args.event_path:
        event_payload = json.loads(Path(args.event_path).read_text(encoding="utf-8"))
        snapshot = extract_snapshot_from_event_payload(event_payload)

    if snapshot is None:
        snapshot = build_status_snapshot(history_window=args.history_window, seed=args.seed)

    target_dir = render_status_site(snapshot, args.output_dir)
    print(f"Status site generated at {target_dir.resolve()}")


if __name__ == "__main__":
    main()
