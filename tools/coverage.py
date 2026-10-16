"""Dynamic coverage of the mslugx 68000 using MAME as the oracle.

Launches MAME with the debugger (no UI) and tools/mame/coverage.lua, consumes the
traces in parts as they are produced and deletes them, and saves a JSON with:
  - executed addresses per region (P1, P2 window per bank, BIOS, RAM),
  - observed targets of indirect jumps (jmp/jsr with a parenthesized operand).

Usage:
    python tools/coverage.py --mame MAME --rompath game --seconds 180 [--output FILE] [--no-bot]

The result contains addresses and aggregate counts, never ROM bytes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

LINE = re.compile(r"^([0-9A-F]{6}): (\S+)\s*(.*)$")


# Region names are JSON keys of the coverage file: keep them.
def region(pc: int) -> str:
    if pc < 0x100000:
        return "p1"
    if 0x200000 <= pc < 0x300000:
        return "p2_ventana"
    if 0xC00000 <= pc < 0xD00000:
        return "bios"
    if 0x100000 <= pc < 0x200000:
        return "ram"
    return "otro"


class Accumulator:
    def __init__(self) -> None:
        self.pcs: dict[str, set] = defaultdict(set)
        self.indirect: set[tuple[int, int, int]] = set()   # (source, target, bank)
        self.bank = 0
        self.instructions = 0

    def process(self, path: Path) -> None:
        pending = None
        with path.open("r", encoding="ascii", errors="replace") as f:
            for line in f:
                if line.startswith("BANK "):
                    self.bank = int(line[5:])
                    continue
                m = LINE.match(line)
                if not m:
                    continue
                pc = int(m.group(1), 16)
                self.instructions += 1
                r = region(pc)
                self.pcs[r if r != "p2_ventana" else f"p2_banco{self.bank}"].add(pc)
                if pending is not None:
                    self.indirect.add((pending, pc, self.bank))
                    pending = None
                if m.group(2) in ("jmp", "jsr") and "(" in m.group(3):
                    pending = pc

    def result(self) -> dict:
        return {
            "instrucciones_trazadas": self.instructions,
            "pcs": {k: sorted(v) for k, v in sorted(self.pcs.items())},
            "indirectos": sorted(self.indirect),
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    repo = Path(__file__).resolve().parents[1]
    private = Path(os.environ.get("PD_PRIVATE", repo / ".private"))
    mame_env = os.environ.get("PD_MAME")
    game_env = os.environ.get("PD_GAME")
    ap.add_argument("--mame", type=Path, default=Path(mame_env) if mame_env else None)
    ap.add_argument("--rompath", type=Path, default=Path(game_env) if game_env else repo / "game")
    ap.add_argument("--bios", default="us")
    ap.add_argument("--work", type=Path, default=private / "mame-coverage")
    ap.add_argument("--seconds", type=int, default=180, help="emulated seconds")
    ap.add_argument("--frames-per-part", type=int, default=300)
    ap.add_argument("--output", type=Path, default=private / "analysis" / "coverage.json")
    ap.add_argument("--no-bot", action="store_true")
    ap.add_argument("--playback", type=Path,
                    help="plays back a MAME .inp recording (ignores --seconds and disables the bot)")
    a = ap.parse_args()
    if not a.mame or not a.mame.is_file():
        ap.error("pass --mame or set PD_MAME to the focused MAME executable")
    if not a.rompath.is_dir():
        ap.error(f"ROM path does not exist: {a.rompath}")
    if a.seconds <= 0 or a.frames_per_part <= 0:
        ap.error("--seconds and --frames-per-part must be positive")

    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    for old in list(work.glob("trace_*.txt")) + [work / "DONE", work / "p1_reads.txt"]:
        old.unlink(missing_ok=True)

    lua = Path(__file__).resolve().parent / "mame" / "coverage.lua"
    # A playback requires the same initial state as the recording: empty nvram.
    nvram = work / "nvram"
    if nvram.exists():
        for f in sorted(nvram.rglob("*"), reverse=True):
            f.unlink() if f.is_file() else f.rmdir()
    play = not (a.no_bot or a.playback)
    env = dict(os.environ, PD_TRACE_DIR=str(work), PD_PLAY="1" if play else "0",
               PD_FRAMES=str(a.frames_per_part))
    cmd = [str(a.mame.resolve()), "mslugx", "-bios", a.bios, "-rompath", str(a.rompath.resolve()),
           "-video", "none", "-sound", "none", "-nothrottle",
           "-debug", "-debugger", "none", "-autoboot_script", str(lua),
           "-cfg_directory", str(work / "cfg"), "-nvram_directory", str(nvram)]
    if a.playback:
        cmd += ["-playback", a.playback.name, "-input_directory", str(a.playback.parent),
                "-exit_after_playback"]
    else:
        cmd += ["-seconds_to_run", str(a.seconds)]
    stdout_path, stderr_path = work / "mame.stdout.txt", work / "mame.stderr.txt"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.Popen(cmd, cwd=work, env=env, stdout=stdout, stderr=stderr)

        acc = Accumulator()
        done = 0
        start = time.time()

        def process_ready(final: bool) -> None:
            nonlocal done
            while True:
                current = work / f"trace_{done:04d}.txt"
                following = work / f"trace_{done + 1:04d}.txt"
                if not current.exists() or not (final or following.exists()):
                    return
                acc.process(current)
                current.unlink()
                done += 1
                print(f"  part {done:3d}  {time.time() - start:6.0f} s  "
                      f"p1={len(acc.pcs['p1'])} bios={len(acc.pcs['bios'])} "
                      f"indirect={len(acc.indirect)}", flush=True)

        while proc.poll() is None:
            process_ready(False)
            time.sleep(2)
        process_ready(True)

    res = acc.result()
    reads = work / "p1_reads.txt"
    if reads.exists():
        # (Even) P1 addresses read by the 68000, including opcode fetches.
        res["lecturas_p1"] = sorted(int(x, 16) for x in reads.read_text().split())
        reads.unlink()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(res), encoding="utf-8")
    print(f"MAME exited with code {proc.returncode}; {acc.instructions} instructions; output: {a.output}")
    if proc.returncode != 0:
        lines = stderr_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if lines:
            print("\n".join(lines[-20:]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
