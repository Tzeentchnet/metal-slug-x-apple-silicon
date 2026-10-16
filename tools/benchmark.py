#!/usr/bin/env python3
"""Run machine-readable Apple Silicon CPU, hardware, and Metal benchmarks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def run(command: list[str], env: dict[str, str], report: Path) -> dict:
    child_env = dict(os.environ, **env, PD_BENCHMARK="1", PD_BENCHMARK_JSON=str(report))
    result = subprocess.run(command, env=child_env, text=True, capture_output=True)
    if result.returncode != 0:
        raise SystemExit(
            f"Benchmark failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stdout}{result.stderr}"
        )
    try:
        return json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Invalid benchmark report {report}: {error}") from error


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path,
                        default=repo / "build-personal/src/mslugx.app/Contents/MacOS/mslugx")
    parser.add_argument("--roms", type=Path,
                        default=Path(os.environ.get("PD_GAME", repo / "game")))
    parser.add_argument("--frames", type=int, default=1800)
    parser.add_argument("--window-seconds", type=float, default=5.0)
    parser.add_argument("--output", type=Path, default=repo / "build-personal/benchmark.json")
    args = parser.parse_args()
    if not args.app.is_file():
        parser.error(f"app executable does not exist: {args.app}")
    if not args.roms.exists():
        parser.error(f"ROM path does not exist: {args.roms}")
    if args.frames <= 0 or args.window_seconds <= 0:
        parser.error("--frames and --window-seconds must be positive")

    app = str(args.app.resolve())
    roms = str(args.roms.resolve())
    headless = [app, "--roms", roms, "--headless", "--frames", str(args.frames)]
    with tempfile.TemporaryDirectory(prefix="mslugx-benchmark-") as temporary:
        work = Path(temporary)
        interpreter = run(headless, {"PD_INTERPRETER": "1"}, work / "interpreter.json")
        native = run(headless, {}, work / "native.json")
        window = run(
            [app, "--roms", roms],
            {
                "PD_QUIT_AFTER": str(args.window_seconds),
                "PD_PREF": str(work) + "/",
            },
            work / "window.json",
        )

    result = {
        "schema": 1,
        "interpreter": interpreter,
        "native": native,
        "window": window,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
