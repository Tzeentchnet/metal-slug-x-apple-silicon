"""Pre-commit hook: enforces rule 1 (the repo never contains ROMs or extracted data).

Rejects the commit if any staged file:
  - is binary, except for exact hash-allowlisted ROM-free documentation screenshots;
  - is larger than 1 MB;
  - has the same SHA256 as any file under the user's ROM folder
    (including the rebuilt set in roms/mame).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

LIMIT = 1 << 20
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DOCUMENTATION_SCREENSHOTS = {
    "docs/screenshots/rom-setup.png": {
        "04f08026d205647092072f9d558ed9d4d26e0049405dfd5a9497fe86abc34bf0",
    },
    "docs/screenshots/rom-validation.png": {
        "5fe2f9e72fd31c0ce4d71d2256917fb40dd87ac2d0dd88b360baaf95f89e72fa",
    },
}


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def rom_hashes(folder: Path) -> dict[str, str]:
    h = {}
    if folder.is_dir():
        for f in folder.rglob("*"):
            if f.is_file():
                h[hashlib.sha256(f.read_bytes()).hexdigest()] = str(f.relative_to(folder))
    return h


def main() -> int:
    repo_root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    roms = Path(os.environ.get("PD_GAME") or repo_root / "game")
    forbidden = rom_hashes(roms)

    names = [n for n in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0") if n]
    problems = []
    for n in names:
        data = git("show", f":{n}")
        approved_hashes = DOCUMENTATION_SCREENSHOTS.get(n)
        digest = hashlib.sha256(data).hexdigest()
        if approved_hashes and (not data.startswith(PNG_SIGNATURE) or digest not in approved_hashes):
            problems.append(f"{n}: is not an approved ROM-free documentation screenshot")
        if b"\0" in data and not approved_hashes:
            problems.append(f"{n}: is binary")
        if len(data) > LIMIT:
            problems.append(f"{n}: is {len(data)} bytes (limit {LIMIT})")
        match = forbidden.get(digest)
        if match:
            problems.append(f"{n}: identical to roms/{match}")

    if problems:
        print("pre-commit: REJECTED (rule 1: the repo never contains ROMs or extracted data)")
        for p in problems:
            print("   " + p)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
