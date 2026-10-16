# Verification

## Current arcade analysis

The pinned MAME 0.289 oracle ran 180 emulated seconds with debugger trace rotation:

| Measure | Result |
|---|---:|
| Traced instructions | 179,746,835 |
| Unique P1 PCs | 26,224 |
| Unique BIOS PCs | 1,559 |
| Observed indirect targets | 1,112 |
| P1 bytes classified as code | 483,814 (46.1%) |
| Dynamic P1 code bytes | 95,552 (9.1%) |
| Static misses for executed addresses | 0 |

The regenerated native program has 119,262 instructions, 3,031 regions, 5,012 analysis entries,
and zero unsupported instructions.

## Automated matrix

The personal build provides:

- `mac_capabilities`: mocked M1/M3/M5 diagnostic classification;
- `arcade_profile`: exact feature-window selection for 250-P1;
- `roms_mame_folder` and `roms_mame_zip`: loose/zip loader parity;
- `cpu_differential`: thousands of instruction cases against Musashi;
- `lockstep_reset`: whole-program native/interpreter reset lockstep;
- `savestate_roundtrip`: RAM, image, and audio after restore;
- `sound_menu`: isolated audio playback and exact state restoration.

The current personal configuration runs nine tests; the clean interpreter configuration runs
seven. Both suites pass natively on arm64.

Run:

```sh
ctest --test-dir build-personal --output-on-failure -j 3
```

An AppleClang AddressSanitizer plus UndefinedBehaviorSanitizer build also passes all nine personal
tests. LeakSanitizer is not available on this macOS platform, so `ASAN_OPTIONS=detect_leaks=0` is
required; address and undefined-behavior checks remain enabled.

## Focused MAME replay

A fresh 3,023-frame Mission 1 developer-mode capture was replayed through both CPU paths. Native
and interpreter results matched exactly across 2,825 VBlank RAM/palette hashes and all 3,023 frame
hashes. Against MAME, the shared emulator baseline matched the first 63 VBlanks and first 276
images, then retained known RAM/video differences. This establishes that recompilation introduces
no new divergence in the captured window; it does not establish full MAME or all-mission parity.

## Metal validation

`PD_WINDOW_TEST=N,path.png[,menu|settings|cheats|debug|sounds]` captures the actual CAMetalLayer
output after N frames. Coverage includes the game image, sharp/smooth/nearest filters, scanlines,
cartridge font, logo, menu panels, sound browser, palette view, notices, and ROM chooser.

`PD_FIND_TEST=path.png` renders the no-ROM path once and exits.

## Timing criteria

Window traces report display loops, emulated frames per second, mean audio queue, underruns, and
drops. The sustained target is 59.185606 Hz within 0.02%, zero steady-state underruns, and no queue
growth. Short runs are quantized by whole frames; use at least ten minutes for release evidence.

```sh
PD_QUIT_AFTER=600 \
build-personal/src/mslugx.app/Contents/MacOS/mslugx \
  --roms game --trace build-personal/timing.log
```

The verified 600.020-second 60 Hz run produced 35,511 emulated frames at 59.182988 Hz, an error of
0.004424%. It presented 36,001 frames with zero drawable misses and zero host-clock resets. The
audio queue averaged 45.3 ms with zero empty-queue events and zero drops.

## Release checks

The clean packager:

- rejects `PD_HAVE_PROGRAM=ON`;
- thins the app and SDL3.framework to arm64;
- signs and verifies nested code;
- includes a machine-readable ROM-free build manifest;
- audits expected bundle contents and searches recursively for copied ROM byte runs.

The generated ZIP and DMG have also been checked by mounting the DMG read-only, verifying strict
nested signatures, confirming both Mach-O binaries are arm64-only, checking the SDL install name,
launching the packaged executable, and running two clean interpreter frames from the mounted app.
The ZIP contains no `__MACOSX` or AppleDouble entries and no local build path.

No claim of full-game or exact MAME parity should be made until the shared hardware baseline is
reconciled and deterministic arcade recordings cover every mission. The current evidence
establishes boot, attract/gameplay bot coverage, native/interpreter stage parity, feature-profile
behavior, CPU differential and reset parity, loader parity, save states, sound isolation, Metal
output, and timing.
