#!/usr/bin/env python3
"""Package a clean arm64 macOS app as ZIP and DMG artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

README = """Metal Slug X Apple Silicon port {version}

This package contains no game content. Supply your own verified Metal Slug X arcade set:

  1. Put mslugx.zip and neogeo.zip in the sibling game folder, or put their
     extracted mslugx/ and neogeo/ folders there.
  2. Open Metal Slug X.app.
  3. If the set is elsewhere, drop its folder or zip on the window or use
     the native folder chooser.

The distributable app uses the cycle-accurate 68000 interpreter. A personal source build can
privately generate native arm64 code from your own P1 and BIOS.

Controls: Esc menu; F5/F9 save/load; F11 or Control-Command-F fullscreen; F3 debug.
Metal Slug X is copyright SNK CORPORATION. This is an unofficial fan project and is not
affiliated with or endorsed by SNK.
"""

GAME_README = """Put your own Metal Slug X MAME set in this folder.

Supported layouts:
  mslugx.zip + neogeo.zip
  mslugx/ + neogeo/

The files are identified and verified by their hashes. No ROM or BIOS is included with this port.
"""


def run(*command: str, capture: bool = False) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else ""


def version() -> str:
    text = (REPO / "src/port/version.h").read_text(encoding="utf-8")
    match = re.search(r'#define PORT_VERSION "([^"]+)"', text)
    if not match:
        raise SystemExit("PORT_VERSION is missing from src/port/version.h")
    return match.group(1)


def require_clean_build(build: Path) -> Path:
    cache_path = build / "CMakeCache.txt"
    if not cache_path.is_file():
        raise SystemExit(f"CMake cache not found: {cache_path}")
    cache = cache_path.read_text(encoding="utf-8", errors="replace")
    if "PD_HAVE_PROGRAM:INTERNAL=OFF" not in cache:
        raise SystemExit(
            f"{build} contains code generated from the game; configure a separate build with "
            "-DPD_RECOMPILED=OFF"
        )
    app = build / "src/mslugx.app"
    executable = app / "Contents/MacOS/mslugx"
    if not executable.is_file():
        raise SystemExit(f"app bundle is missing: {app}")
    expected = version()
    reported = run(str(executable), "--version", capture=True)
    if not reported.endswith(expected):
        raise SystemExit(f"app reports '{reported}', expected version {expected}; rebuild first")
    return app


def thin_arm64(app: Path) -> None:
    binaries = [
        app / "Contents/MacOS/mslugx",
        app / "Contents/Frameworks/SDL3.framework/SDL3",
    ]
    for binary in binaries:
        real = binary.resolve()
        architectures = run("lipo", "-archs", str(real), capture=True).split()
        if "arm64" not in architectures:
            raise SystemExit(f"{binary} has no arm64 slice: {' '.join(architectures)}")
        if architectures != ["arm64"]:
            temporary = real.with_name(real.name + ".arm64")
            run("lipo", str(real), "-thin", "arm64", "-output", str(temporary))
            os.replace(temporary, real)
        run("strip", "-x", str(real))
        if run("lipo", "-archs", str(real), capture=True) != "arm64":
            raise SystemExit(f"failed to make {binary} arm64-only")


def add_resources(app: Path) -> None:
    resources = app / "Contents/Resources"
    licenses = resources / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / "LICENSE", resources / "LICENSE.txt")
    shutil.copy2(REPO / "THIRD_PARTY.md", resources / "THIRD_PARTY.md")
    shutil.copy2(REPO / ".tools/sdl3/LICENSE.txt", licenses / "SDL3.txt")
    shutil.copy2(REPO / "external/musashi/readme.txt", licenses / "Musashi.txt")
    shutil.copy2(REPO / "external/ymfm/LICENSE", licenses / "ymfm.txt")
    shutil.copy2(REPO / "external/chips/LICENSE", licenses / "chips-z80.txt")
    info = {
        "schema": 1,
        "version": version(),
        "platform": "macos",
        "architecture": "arm64",
        "minimum_macos": "13.0",
        "contains_game_content": False,
        "recompiled_program": False,
        "build_type": "interpreter-only",
    }
    (resources / "BUILD-INFO.json").write_text(
        json.dumps(info, indent=2) + "\n", encoding="utf-8"
    )


def sign_app(app: Path, identity: str | None) -> None:
    framework = app / "Contents/Frameworks/SDL3.framework"
    signing_identity = identity or "-"
    common = ["codesign", "--force", "--sign", signing_identity]
    if identity:
        common += ["--timestamp", "--options", "runtime"]
    run(*common, str(framework))
    run(*common, str(app))
    run("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app))


def make_zip(source: Path, destination: Path) -> None:
    destination.unlink(missing_ok=True)
    run("ditto", "-c", "-k", "--norsrc", "--keepParent",
        str(source), str(destination))


def notarize_app(app: Path, profile: str, temporary: Path) -> None:
    submission = temporary / "notarization.zip"
    make_zip(app, submission)
    run("xcrun", "notarytool", "submit", str(submission),
        "--keychain-profile", profile, "--wait")
    run("xcrun", "stapler", "staple", str(app))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=REPO / "build-dist")
    parser.add_argument("--out", type=Path, default=REPO / "release")
    parser.add_argument("--sign-identity", help="Developer ID Application identity")
    parser.add_argument("--notarize-profile", help="notarytool keychain profile")
    parser.add_argument("--skip-dmg", action="store_true")
    args = parser.parse_args()
    if args.notarize_profile and not args.sign_identity:
        parser.error("--notarize-profile requires --sign-identity")

    source_app = require_clean_build(args.build)
    args.out.mkdir(parents=True, exist_ok=True)
    release_name = f"metal-slug-x-recomp-v{version()}-macos-arm64"
    zip_path = args.out / f"{release_name}.zip"
    dmg_path = args.out / f"{release_name}.dmg"

    with tempfile.TemporaryDirectory(prefix="mslugx-release-") as temporary_name:
        temporary = Path(temporary_name)
        root = temporary / release_name
        app = root / "Metal Slug X.app"
        shutil.copytree(source_app, app, symlinks=True)
        (root / "game").mkdir(parents=True)
        (root / "README.txt").write_text(README.format(version=version()), encoding="utf-8")
        (root / "game/PUT_YOUR_ARCADE_SET_HERE.txt").write_text(
            GAME_README, encoding="utf-8"
        )
        add_resources(app)
        thin_arm64(app)
        sign_app(app, args.sign_identity)

        if args.notarize_profile:
            notarize_app(app, args.notarize_profile, temporary)

        make_zip(root, zip_path)
        if not args.skip_dmg:
            dmg_path.unlink(missing_ok=True)
            run("hdiutil", "create", "-volname", "Metal Slug X",
                "-srcfolder", str(root), "-ov", "-format", "UDZO", str(dmg_path))
            if args.notarize_profile:
                run("xcrun", "notarytool", "submit", str(dmg_path),
                    "--keychain-profile", args.notarize_profile, "--wait")
                run("xcrun", "stapler", "staple", str(dmg_path))

    print(f"{zip_path} ({zip_path.stat().st_size} bytes)")
    if not args.skip_dmg:
        print(f"{dmg_path} ({dmg_path.stat().st_size} bytes)")
    roms = Path(os.environ.get("PD_GAME", REPO / "game"))
    audit = [sys.executable, str(REPO / "tools/audit.py"), "release", str(zip_path)]
    if roms.exists():
        audit += ["--roms", str(roms)]
    return subprocess.run(audit).returncode


if __name__ == "__main__":
    raise SystemExit(main())
