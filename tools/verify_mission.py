"""Replay a MAME recording in the port and require zero fingerprint divergences.

Runs the port without a window using the recorded inputs (tools/mame/inputs.lua) and the clock
date of the recording, writes its fingerprints and compares them with MAME's
(tools/mame/fingerprints.lua) through compare_fingerprints.py.

Usage:
  python verify_mission.py --app build-personal/src/mslugx.app/Contents/MacOS/mslugx \
                             --roms FOLDER --inputs INPUTS.txt
                             --reference MAME_FINGERPRINTS.txt --frames N --date YYYY-MM-DD-hh-mm-ss-D
                             --output PORT_FINGERPRINTS.txt

How references are produced (MAME 0.289, empty NVRAM):
  PD_PIXELS=1 PD_FINGERPRINTS=<ref> PD_INPUTS=<inputs> \
  PD_INPUTS_SCRIPT=<repo>/tools/mame/inputs.lua \
  mame mslugx -bios us -rompath <roms> -playback mission1.inp -input_directory <inp> \
       -exit_after_playback -nvram_directory <empty> -video none -sound none -nothrottle
       -autoboot_script <repo>/tools/mame/fingerprints.lua
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", type=Path, required=True)
    ap.add_argument("--roms", type=Path, required=True)
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--devmode", action="store_true", help="BIOS development mode")
    ap.add_argument("--dips", help="debug dips forced on, hex")
    a = ap.parse_args()

    env = dict(os.environ)
    if a.devmode:
        env["PD_DEVMODE"] = "1"
    if a.dips:
        env["PD_DIPS"] = a.dips
    r = subprocess.run([str(a.app), "--roms", str(a.roms), "--headless", "--frames", str(a.frames),
                        "--inputs", str(a.inputs), "--fingerprints", str(a.output), "--date", a.date],
                       capture_output=True, text=True, env=env)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr)
        return 1
    comparator = Path(__file__).resolve().parent / "compare_fingerprints.py"
    return subprocess.run([sys.executable, str(comparator), str(a.reference), str(a.output)]).returncode


if __name__ == "__main__":
    sys.exit(main())
