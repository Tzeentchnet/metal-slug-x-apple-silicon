#!/usr/bin/env python3
"""Install and verify the pinned Apple Silicon build environment."""

import argparse
import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path


SETUP = Path(__file__).resolve().parent


def run(command, **kwargs):
    print("+", " ".join(str(x) for x in command), flush=True)
    return subprocess.run([str(x) for x in command], check=True, **kwargs)


def macos_major():
    version = platform.mac_ver()[0]
    try:
        return int(version.split(".", 1)[0])
    except (ValueError, IndexError):
        return 0


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(tool, downloads):
    spec = tool["download"]
    target = downloads / spec["file"]
    if target.exists() and sha256(target) == spec["sha256"]:
        return target
    target.unlink(missing_ok=True)
    print("Downloading {} {}...".format(tool["name"], tool["version"]), flush=True)
    with urllib.request.urlopen(spec["url"]) as response, target.open("wb") as output:
        shutil.copyfileobj(response, output)
    actual = sha256(target)
    if actual != spec["sha256"]:
        target.unlink(missing_ok=True)
        raise SystemExit(
            "{}: SHA-256 {} does not match versions.json ({})".format(
                tool["name"], actual, spec["sha256"]
            )
        )
    return target


def single_root(path):
    entries = [entry for entry in path.iterdir() if entry.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return path


def extract_archive(archive, temporary):
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as packed:
            packed.extractall(temporary)
    elif name.endswith(".tar.gz") or name.endswith(".tgz"):
        with tarfile.open(archive, "r:gz") as packed:
            packed.extractall(temporary)
    else:
        raise SystemExit("Unsupported archive: {}".format(archive))


def install_archive(tool, archive, tools):
    target = tools / tool["name"]
    with tempfile.TemporaryDirectory(prefix="pd-install-") as temporary_name:
        temporary = Path(temporary_name)
        extract_archive(archive, temporary)
        source = single_root(temporary) if tool.get("strip_single_root", True) else temporary
        replacement = tools / (tool["name"] + ".new")
        shutil.rmtree(replacement, ignore_errors=True)
        shutil.copytree(source, replacement, symlinks=True)
        shutil.rmtree(target, ignore_errors=True)
        replacement.rename(target)


def install_dmg(tool, archive, tools):
    target = tools / tool["name"]
    with tempfile.TemporaryDirectory(prefix="pd-dmg-") as mount_name:
        mount = Path(mount_name)
        run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", mount, archive],
            stdout=subprocess.DEVNULL)
        try:
            replacement = tools / (tool["name"] + ".new")
            shutil.rmtree(replacement, ignore_errors=True)
            replacement.mkdir()
            for item in tool["copy"]:
                source = mount / item
                destination = replacement / source.name
                if source.is_dir():
                    shutil.copytree(source, destination, symlinks=True)
                else:
                    shutil.copy2(source, destination)
            shutil.rmtree(target, ignore_errors=True)
            replacement.rename(target)
        finally:
            run(["hdiutil", "detach", mount], stdout=subprocess.DEVNULL)


def tool_ok(tool, tools):
    return (tools / tool["name"] / tool["check"]).exists()


def restore_executable_bits(tool, tools):
    root = tools / tool["name"]
    for relative in tool.get("executables", []):
        path = root / relative
        if path.exists():
            path.chmod(path.stat().st_mode | 0o755)


def install_tool(tool, tools, downloads):
    if tool_ok(tool, tools):
        restore_executable_bits(tool, tools)
        print("{} {}: already installed".format(tool["name"], tool["version"]))
        return
    archive = download(tool, downloads)
    if tool["kind"] == "dmg":
        install_dmg(tool, archive, tools)
    else:
        install_archive(tool, archive, tools)
    restore_executable_bits(tool, tools)
    if not tool_ok(tool, tools):
        raise SystemExit("{}: {} missing after installation".format(tool["name"], tool["check"]))


def sdk_candidates():
    result = []
    try:
        selected = subprocess.check_output(
            ["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True
        ).strip()
        if selected:
            result.append(Path(selected))
    except (OSError, subprocess.CalledProcessError):
        pass
    roots = [
        Path("/Library/Developer/CommandLineTools/SDKs"),
        Path("/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs"),
    ]
    for root in roots:
        if root.is_dir():
            result.extend(sorted(root.glob("MacOSX*.sdk"), reverse=True))
    unique = []
    seen = set()
    for candidate in result:
        resolved = str(candidate.resolve())
        if resolved not in seen:
            seen.add(resolved)
            unique.append(candidate)
    return unique


def sdk_version(path):
    settings = path / "SDKSettings.plist"
    try:
        with settings.open("rb") as stream:
            data = plistlib.load(stream)
        return tuple(int(part) for part in str(data.get("Version", "0")).split("."))
    except (OSError, ValueError, plistlib.InvalidFileException):
        name = path.stem.replace("MacOSX", "")
        try:
            return tuple(int(part) for part in name.split("."))
        except ValueError:
            return (0,)


def probe_sdk(tools):
    clang = Path("/usr/bin/clang")
    if not clang.exists():
        raise SystemExit("AppleClang is missing. Install Xcode Command Line Tools.")
    candidates = sorted(sdk_candidates(), key=sdk_version, reverse=True)
    if not candidates:
        raise SystemExit("No macOS SDK found. Install Xcode Command Line Tools.")
    with tempfile.TemporaryDirectory(prefix="pd-sdk-") as temporary_name:
        temporary = Path(temporary_name)
        source = temporary / "probe.c"
        output = temporary / "probe"
        source.write_text("int main(void) { return 0; }\n", encoding="ascii")
        failures = []
        for sdk in candidates:
            command = [
                clang, "-arch", "arm64", "-mmacosx-version-min=13.0",
                "-isysroot", sdk, source, "-o", output,
            ]
            attempt = subprocess.run(command, capture_output=True, text=True)
            if attempt.returncode == 0:
                architecture = subprocess.check_output(["file", output], text=True)
                if "arm64" not in architecture:
                    failures.append("{}: output is not arm64".format(sdk))
                    continue
                (tools / "sdk-path").write_text(str(sdk.resolve()) + "\n", encoding="utf-8")
                print("SDK/linker preflight: {} (arm64, deployment target 13.0)".format(sdk))
                return sdk
            tail = (attempt.stderr or attempt.stdout).strip().splitlines()
            failures.append("{}: {}".format(sdk, tail[-1] if tail else "link failed"))
    raise SystemExit(
        "No coherent macOS SDK/linker pair could link arm64 code.\n"
        + "\n".join("  " + failure for failure in failures)
        + "\nInstall or select a matching Xcode/Command Line Tools release."
    )


def verify_environment(tools, selected):
    failures = []
    for tool in selected:
        restore_executable_bits(tool, tools)
        check = tools / tool["name"] / tool["check"]
        if not check.exists():
            failures.append("{}: missing {}".format(tool["name"], check))
    if failures:
        raise SystemExit("\n".join(failures))
    python = tools / "python/bin/python3"
    version = subprocess.check_output([python, "--version"], text=True).strip()
    cmake = tools / "cmake/CMake.app/Contents/bin/cmake"
    ninja = tools / "ninja/ninja"
    print(subprocess.check_output([cmake, "--version"], text=True).splitlines()[0])
    print(subprocess.check_output([ninja, "--version"], text=True).strip())
    print(version)
    framework = tools / "sdl3/SDL3.xcframework/macos-arm64_x86_64/SDL3.framework/SDL3"
    info = subprocess.check_output(["file", framework], text=True)
    if "arm64" not in info:
        raise SystemExit("SDL3 framework does not contain arm64 code")
    print("SDL3 framework: arm64 present")


def install_python_packages(repo, tools):
    requirements = repo / "tools/requirements.txt"
    stamp = tools / "python/.pd-requirements"
    wanted = sha256(requirements)
    if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == wanted:
        return
    python = tools / "python/bin/python3"
    run([
        python, "-m", "pip", "install", "--disable-pip-version-check",
        "--requirement", requirements,
    ])
    stamp.write_text(wanted + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--analysis-tools", action="store_true")
    args = parser.parse_args()

    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("This environment requires an Apple Silicon Mac (arm64).")
    if macos_major() < 13:
        raise SystemExit("macOS 13 or newer is required.")

    tools = args.repo / ".tools"
    downloads = tools / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    config = json.loads((SETUP / "versions.json").read_text(encoding="utf-8"))
    selected = [
        tool for tool in config["tools"]
        if not tool.get("analysis_only") or args.analysis_tools
    ]
    if not args.verify_only:
        for tool in selected:
            install_tool(tool, tools, downloads)
        install_python_packages(args.repo, tools)
    probe_sdk(tools)
    verify_environment(tools, selected)
    print("\nEnvironment ready. Run: source setup/env.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
