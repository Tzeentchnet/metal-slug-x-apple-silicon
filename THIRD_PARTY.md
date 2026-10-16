# Third-party software

This document inventories third-party software used by the Metal Slug X Apple Silicon port. It
distinguishes code included in the app from tools used only to build, analyze, or verify it. Both
the private recompiled app and the clean interpreter app use the same third-party runtime.

## Software included in the app

| Component | Pinned source | License | Project use and distribution |
|---|---|---|---|
| [SDL3](https://github.com/libsdl-org/SDL/releases/tag/release-3.4.18) | 3.4.18 official xcframework | zlib | Embedded as `SDL3.framework` for macOS lifecycle, input, gamepads, audio devices, paths, and dialogs |
| [Musashi](https://github.com/kstenerud/Musashi/commit/313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd) | 4.60, commit `313ebf1bd9f4d0d93341eb5ce21fd8a119e9dbdd` | MIT | Statically linked 68000 interpreter fallback and differential-test reference |
| [ymfm](https://github.com/aaronsgiles/ymfm/commit/81aec25ccbb98f4873a255f7551ac4dadac59b4a) | commit `81aec25ccbb98f4873a255f7551ac4dadac59b4a` | BSD-3-Clause | Statically linked YM2610 FM, SSG, and ADPCM emulation |
| [floooh/chips `z80.h`](https://github.com/floooh/chips/commit/9e88298ce56319953ac7a43213a1120359f7a3a6) | commit `9e88298ce56319953ac7a43213a1120359f7a3a6` | zlib/libpng | Statically linked, cycle-stepped Neo Geo sound CPU |

### Project-specific integration and changes

- **SDL3:** the official macOS framework is copied with its versioned symlinks intact. Release
  packaging thins the universal binary to arm64, strips nonessential symbols, and re-signs the
  framework. SDL source is not modified.
- **Musashi:** only the plain 68000 configuration is enabled. 68010/020/030/040, PMMU, and FPU
  emulation are disabled; no upstream SoftFloat code is included. The build generates opcode
  handlers from `m68k_in.c`. Local portability fixes use defined unsigned bit operations, guard
  oversized shifts, and avoid evaluating zero-shift rotate masks. These fixes do not change
  defined CPU results and pass the instruction differential suite.
- **ymfm:** only the OPN/YM2610, ADPCM, and SSG files are vendored and compiled; those upstream
  files are otherwise unmodified.
- **floooh/chips:** only `z80.h` is vendored. The project instantiates the header implementation
  in one runtime translation unit without modifying the upstream header.

MAME is not linked into the app, and no MAME implementation code is copied into the runtime.

## Notices included in release artifacts

The clean app contains this inventory at `Contents/Resources/THIRD_PARTY.md` and the following
upstream notices under `Contents/Resources/licenses/`:

| Packaged file | Source notice |
|---|---|
| `SDL3.txt` | SDL3 distribution `LICENSE.txt` |
| `Musashi.txt` | [`external/musashi/readme.txt`](external/musashi/readme.txt) |
| `ymfm.txt` | [`external/ymfm/LICENSE`](external/ymfm/LICENSE) |
| `chips-z80.txt` | [`external/chips/LICENSE`](external/chips/LICENSE) |

The app also includes the port's own MIT license as `Contents/Resources/LICENSE.txt`. The release
packager and publication audit require these files.

## Build and analysis tools not included in the app

| Component | Pinned version or source | License | Project use |
|---|---|---|---|
| [CMake](https://github.com/Kitware/CMake) | 4.4.4 official universal archive | BSD-3-Clause | Build generation |
| [Ninja](https://github.com/ninja-build/ninja) | 1.13.2 official macOS archive | Apache-2.0 | Local and CI builds |
| [CPython](https://www.python.org/) via [python-build-standalone](https://github.com/astral-sh/python-build-standalone) | 3.14.8, standalone build `20261013` | PSF-2.0 plus notices for software bundled by the standalone distribution | Bootstrap, analysis, tests, audit, and packaging |
| [Capstone](https://github.com/capstone-engine/capstone) | 5.0.7 | BSD-3-Clause | Private 68000 disassembly and static analysis |
| [NumPy](https://github.com/numpy/numpy) | 2.5.4 | BSD-3-Clause | Private analysis and recursive ROM-byte publication audit |
| [MAME](https://github.com/mamedev/mame/tree/mame0289) | 0.289 source tag | GPL-2.0-or-later overall; individual files may use compatible licenses | Optional, separately built `mslugx` verification oracle |

MAME, Capstone, NumPy, CMake, Ninja, and Python are development dependencies only. They are not
copied into the app, ZIP, or DMG.

## Apple platform dependencies

AppleClang, the macOS SDK, and the Metal, QuartzCore, CoreGraphics, CoreText, and Foundation
frameworks are supplied by Apple through the operating system or Command Line Tools. They are
referenced at build or runtime but are not redistributed in this project. SDL3 provides the
runtime CoreAudio integration.

## Game-content boundary

No Metal Slug X ROMs, BIOS files, graphics, audio, or other proprietary SNK game assets are
distributed by this project. Users supply their own verified arcade set. Metal Slug X names and
trademarks remain the property of SNK CORPORATION. Normalized inputs, analysis listings, traces,
and generated native game code remain in private build directories and are excluded from clean
releases.

## Reproducibility records

- Download URLs, versions, and SHA-256 values for CMake, Ninja, Python, SDL3, and optional MAME
  source are pinned in [`setup/versions.json`](setup/versions.json).
- Capstone and NumPy are exact-version pinned in
  [`tools/requirements.txt`](tools/requirements.txt).
- Vendored runtime revisions are identified above and in their local build metadata.
- [`tools/audit.py`](tools/audit.py) verifies the clean ZIP's file allowlist, clean-build manifest,
  and absence of copied ROM byte runs.

License names in this document are identifiers for the corresponding upstream terms; the bundled
notice text remains authoritative.
