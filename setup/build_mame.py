#!/usr/bin/env python3
"""Build a focused arm64 MAME oracle from the pinned source."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1))
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    tools = Path(os.environ.get("PD_TOOLS", repo / ".tools"))
    source = tools / "mame-source"
    output = tools / "mame-build"
    if not (source / "makefile").exists():
        sys.exit("MAME source is missing; run ./setup/bootstrap.sh --analysis-tools")
    sdk_file = tools / "sdk-path"
    if not sdk_file.exists():
        sys.exit("SDK preflight is missing; run ./setup/bootstrap.sh")
    env = dict(os.environ)
    env["MACOSX_DEPLOYMENT_TARGET"] = "13.0"
    env["SDKROOT"] = sdk_file.read_text(encoding="utf-8").strip()
    framework_path = tools / "sdl3/SDL3.xcframework/macos-arm64_x86_64"
    if not (framework_path / "SDL3.framework/SDL3").exists():
        sys.exit("SDL3 framework is missing; run ./setup/bootstrap.sh")
    command = [
        "make", "-C", str(source), "-j{}".format(args.jobs),
        "SUBTARGET=mslugx", "SOURCES=src/mame/snk/neogeo.cpp",
        "OSD=sdl3", "REGENIE=1", "USE_QTDEBUG=0", "NO_X11=1", "NO_OPENGL=1",
        "SDL_FRAMEWORK_PATH={}".format(framework_path),
        "ARCHOPTS=-arch arm64", "OVERRIDE_CC=/usr/bin/clang",
        "OVERRIDE_CXX=/usr/bin/clang++", "OVERRIDE_LD=/usr/bin/clang++",
    ]
    subprocess.run(command, env=env, check=True)
    candidates = [source / "mslugx", source / "mamemslugx", source / "mame", source / "build/mame"]
    executable = next((path for path in candidates if path.is_file()), None)
    if not executable:
        sys.exit("MAME build completed but its executable was not found")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, output / "mame")
    subprocess.run([output / "mame", "-help"], env=env, check=True,
                   stdout=subprocess.DEVNULL)
    print(output / "mame")
    return 0


if __name__ == "__main__":
    sys.exit(main())
