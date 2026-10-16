# Project Guidelines

## Scope

- This is a macOS 13+ Apple Silicon-only port.
- Never add ROMs, BIOS files, generated game code, captures, or other game-derived content.
- Keep clean (`PD_RECOMPILED=OFF`) and private personal builds strictly separated.
- MAME is an oracle and hardware reference, not a source of copied implementation code.

## Architecture

- `src/neogeo/` is deterministic emulated hardware.
- `src/cpu/` dispatches private generated regions with Musashi fallback.
- `src/port/` owns SDL3 lifecycle/input/audio and direct Metal presentation.
- Revision-specific addresses belong in the verified `GameProfile`.
- See `docs/ARCHITECTURE.md` and `docs/TRANSLATION_FINDINGS.md`.

## Build and test

```sh
./setup/bootstrap.sh
source setup/env.sh
cmake -S . -B build-personal -DPD_RECOMPILED=ON -DPD_GAME="$PWD/game"
cmake --build build-personal -j 8
ctest --test-dir build-personal --output-on-failure
```

Use `build-dist` with `-DPD_RECOMPILED=OFF` for distributable artifacts. Run the smallest relevant
test first, preserve exact 68000 cycles and 59.185606 Hz timing, and record conversion discoveries
in `docs/TRANSLATION_FINDINGS.md`.
