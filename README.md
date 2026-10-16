# Metal Slug X Apple Silicon recompilation

A native macOS 13+ port of **Metal Slug X** for Apple Silicon. The Neo Geo 68000 program can be
privately recompiled to arm64 C from a ROM set you own, while SDL3 provides lifecycle, input, and
CoreAudio integration and a dedicated Metal backend renders the full frontend.

This repository and its releases contain no ROM, BIOS, graphics, audio, or generated game code.
Metal Slug X is copyright SNK CORPORATION. This is an unofficial fan project and is not affiliated
with or endorsed by SNK.

This Apple Silicon port is inspired by
[AlmazProud/metal-slug-x-recomp](https://github.com/AlmazProud/metal-slug-x-recomp).

## Requirements

- Apple Silicon Mac (M1 or newer)
- macOS 13 Ventura or newer
- Apple Command Line Tools
- Your own verified Metal Slug X MAME set:
  - `game/mslugx/` and `game/neogeo/`, or
  - `mslugx.zip` and `neogeo.zip`

Compatibility with the GOG version of Metal Slug X has not been verified.

## Quick start

```sh
./setup/bootstrap.sh
source setup/env.sh
cmake -S . -B build-personal \
  -DPD_RECOMPILED=ON \
  -DPD_GAME="$PWD/game" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build-personal -j 8
open "build-personal/src/mslugx.app"
```

The personal build verifies and normalizes your P1/P2 and US BIOS in the ignored build directory,
runs static analysis, and generates native code there. Unknown program or BIOS revisions continue
through the cycle-accurate interpreter.

For a ROM-free distributable build:

```sh
cmake -S . -B build-dist -DPD_RECOMPILED=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build-dist -j 8
python3 -I tools/package_release.py --build build-dist --out release
```

The packager refuses a build containing generated game code and creates an arm64-only `.app`, ZIP,
and DMG. Developer ID signing and notarization are optional; see
[Releasing](docs/RELEASING.md).

## Native features

- Exact Neo Geo cadence: 202,752 cycles at 12 MHz, or **59.185606 Hz**
- Display-independent 60 Hz and ProMotion presentation without changing game speed
- Direct CAMetalLayer renderer for game pixels, menus, filters, scanlines, overlays, and captures
- Retina output with square-pixel, 4:3, nearest, smooth, and sharp scaling
- SDL3 keyboard, two-player gamepad, rumble, and CoreAudio device support
- Save states, autofire, sound browser, red blood, developer tools, and optional cheats
- One M1-compatible arm64 binary with runtime Metal and hardware capability reporting
- Private coverage-guided recompilation with interpreter fallback at ungenerated addresses

No M3- or M5-only graphics path is enabled: measured Metal upload and encoding costs do not justify
one for this 2D workload.

## Controls

| Action | Keyboard | Gamepad |
|---|---|---|
| Move | Arrow keys | D-pad / left stick |
| Shoot / jump / grenade | Z / X / C | West / South / East |
| Start / coin | 1 / 5 | Start / Back |
| Menu | Esc | Guide or Back+Start |
| Save / load | F5 / F9 | Menu |
| Fullscreen | F11 or Control-Command-F | Menu setting |
| Pause | P | Menu |
| Service button | F2 | - |
| Debug panel / developer menu | F3 / F4 | - |

Controls are remappable in the app. Settings and personal data are stored under
`~/Library/Application Support/mslugx/Metal Slug X/`.

## Verification

The focused MAME 0.289 oracle produced a 179,746,835-instruction dynamic trace. The generated
program currently contains 119,262 instructions in 3,031 native regions with zero unsupported
instructions. Instruction differential tests, whole-program reset lockstep, save-state, sound,
loader, profile, Metal screenshot, and pacing checks run natively on arm64.

See:

- [Architecture](docs/ARCHITECTURE.md)
- [Building](docs/BUILDING.md)
- [Verification](docs/VERIFICATION.md)
- [Translation and conversion findings](docs/TRANSLATION_FINDINGS.md)
- [Releasing](docs/RELEASING.md)

## Repository layout

| Path | Purpose |
|---|---|
| `src/cpu/` | generated-code dispatcher and Musashi fallback |
| `src/neogeo/` | Neo Geo bus, video, sound, RTC, scheduler, ROM loader |
| `src/port/` | SDL3 app lifecycle and direct Metal frontend |
| `tools/recomp68k/` | private 68000-to-C generator |
| `tools/mame/` | MAME debugger automation used as an oracle |
| `tests/` | instruction differential, lockstep, loader, and capability tests |
| `setup/` | pinned, hash-verified Apple Silicon toolchain |

## License

The port code is MIT licensed under [LICENSE](LICENSE). Third-party components retain their own
licenses; see [THIRD_PARTY.md](THIRD_PARTY.md).
