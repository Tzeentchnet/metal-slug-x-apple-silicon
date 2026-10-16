# Translation and conversion findings

This document records findings specific to converting the existing port and the verified arcade
ROM set to a native Apple Silicon application. It contains addresses, hashes, and aggregate
analysis results, but no ROM bytes.

## Host and toolchain

- Development host: Apple M5, 24 GiB, arm64.
- Minimum deployment target: macOS 13.0.
- The installed macOS 27 SDK contains `arm64e.x1` TAPI stubs that the installed linker cannot
  parse. The bootstrap therefore tests SDKs by compiling and linking arm64 code instead of trusting
  version order; the current coherent selection resolves to MacOSX26.5.sdk.
- The official SDL3 3.4.18 xcframework supplies an arm64+x86_64 macOS framework. Clean packaging
  thins it to arm64.
- Command Line Tools do not supply `xcrun metal`. The renderer uses runtime Metal shader
  compilation; this is explicit and fails with the compiler's diagnostic rather than falling back
  to another API.

## Verified arcade inputs

| Input | SHA-1 |
|---|---|
| 250-P1 | `4c19f2e9824e606178ac1c9d4b0516fbaa625035` |
| 250-P2 | `18aaa7a3ba8da99f78c430e9be69ccde04bc04d9` |
| US MVS BIOS | `5c6bba07d2ec8ac95776aa3511109f5e1e2e92eb` |

The normalized combined program is 5,242,880 bytes with SHA-256
`a1aa8647257a60888199ff4159beb4e6f797d57bbf5dfbd9d8c6b85c58489e4d`. The normalized BIOS
SHA-256 is `01ff1db85c5b209d4f5879ea8348e3b39a237532c37232f14c2b48945e9aa7d8`.

The runtime loader stores P and BIOS words in 68000 byte order. Existing analysis tools consume
file order, so `prepare_recomp` swaps each pair back when writing private inputs. This boundary is
lossless and is covered by loader parity tests.

## Static and dynamic recompilation

Initial static analysis classified 423,860 P1 code bytes and generated 100,634 instructions in
2,650 regions. A focused native MAME 0.289 trace then added:

- 179,746,835 executed instructions;
- 26,224 unique P1 PCs;
- 1,559 BIOS PCs;
- 1,112 observed indirect targets.

The combined analysis classifies 483,814 P1 code bytes and generates 119,262 instructions in 3,031
regions. No dynamically executed address is missed, and the generator reports zero unsupported
instructions. Ninety-nine indirect sites remain unresolved because the trace did not observe a
target; they safely use interpreter fallback.

## Reset-state parity

Musashi reset intentionally leaves undefined CCR bits and general registers untouched. Reusing a
Musashi instance after fallback execution leaked old CCR state into the lockstep oracle, causing a
cycle-zero mismatch. The deterministic harness now explicitly chooses SR `0x2700` for both sides.
This is a test-state definition, not a change to emulated reset behavior.

## C shift portability

AppleClang's undefined-behavior sanitizer found several upstream Musashi expressions that relied
on de facto machine behavior: signed `1 << 31`, left-shifting a negative division remainder,
register-selected shifts of 32 or more, and rotate-through-extend masks evaluated for a zero
shift. The opcode template now uses unsigned masks, masks signed remainders before packing them,
guards oversized shifts, and computes rotate masks only for nonzero shifts. Differential results
are unchanged, and the full nine-test AddressSanitizer/UndefinedBehaviorSanitizer matrix passes.

## Arcade enhancement profile

The arcade 250-P1 differs from the earlier PC-derived P1 hash, but disassembly and dynamic traces
show that every enhancement-bearing routine and RAM/table location retained its address. The
profile is now a structured `GameProfile` selected by both the loader's arcade revision and a hash
over eleven behavior-bearing windows:

`f4098e70cb8b86527645e878561c0cc0111bc4653df3e68509f8eabf0239031d`

Key mappings:

| Feature | Arcade mapping |
|---|---|
| Main VBlank wait | `0x0039B0`-`0x003A42` |
| Logic-cycle byte | RAM `0x10008A` |
| Debug dips / development flags | `0x10F000`, `0x10FE80`, `0x10C2BE` |
| In-mission state | `0x100088 == 2` |
| Player table | `0x10C718` |
| Player objects | `0x1014C4`, `0x101574` |
| Soldier / lives | `0x101287/0x101337`, `0x101288/0x101338` |
| Weapon subtype / ammo / form tables | `0x0C08A8`, `0x0C08B8`, `0x0C0918` |
| Fat-form stage check | `0x0C0BAE`-`0x0C0BF2`, stage `0x10C2F6` |
| Stage-object spawn routine | `0x01A0A6`, parent `0x101414` |
| BLOOD soft-dip read | word `0x10FD8E`, low-byte mask |
| Title logo sprites | 41-124 plus TM sprite 380, tile `0x309CA` |

Unknown or modified P1 revisions do not receive these writes even if a filename matches.

## Metal conversion

- Neo Geo frames are CPU-side ARGB8888 values. On little-endian arm64 their bytes match Metal's
  BGRA8Unorm layout, so upload requires no channel conversion.
- All SDL renderer paths were moved to a renderer-neutral API: game frame, cartridge font, title
  logo, menus, sound browser, debug overlays, palette, scanlines, notices, chooser, and readback.
- Sharp filtering reproduces nearest integer expansion followed by linear fitting directly in the
  fragment shader, avoiding an intermediate render target.
- CAMetalLayer does not itself provide a blocking producer cadence. An explicit display-period
  producer wait prevents the CPU from running ahead, while `displaySyncEnabled` retains tear-free
  presentation.
- Hidden and occluded windows pause CoreAudio and reset the host accumulator when restored.

## Exact timing

The old display-synchronized path accelerated emulation by about 1.4% on a 60 Hz display. The
native port always uses 16.896 ms emulated frames and treats presentation as an independent
consumer. At 60 Hz the renderer duplicates frames; at ProMotion rates it presents the newest
complete frame more often. Audio stays centered on a 1.0 frequency ratio with at most a small
queue-jitter correction.

An unattended timing run exposed a lifecycle edge case: macOS can emit `WINDOW_EXPOSED` without a
preceding suspension. Resetting the host accumulator on every exposed event discarded fractional
board time and caused measurable drift. The clock now resets only when a genuinely hidden,
minimized, or occluded window resumes. Automated `PD_QUIT_AFTER` pacing runs ignore occlusion so
they remain measurable when a terminal regains focus; normal gameplay still suspends while
occluded.

A fresh 600.020-second verification run produced 35,511 board frames, or 59.182988 Hz. The
0.004424% error is inside the 0.02% release criterion. It also recorded 36,001 presentations,
zero drawable misses, a 45.3 ms mean audio queue, zero empty-queue events, and zero audio drops.

## Apple Silicon measurements

Live M5 capabilities:

- Apple GPU family 10;
- unified memory;
- 10 CPU cores, 4 performance cores;
- 24 GiB memory;
- three bounded drawables.

A final 1,800-frame instrumented run measured:

| Mode | Wall time | CPU dispatch | Video | Audio |
|---|---:|---:|---:|---:|
| Interpreter | 9.750 s | 8.718 s | 420 ms | 611 ms |
| Recompiled | 1.117 s | 105 ms | 412 ms | 599 ms |

The sustained 60 Hz Metal run presented 36,001 frames with zero drawable misses. These results
justify the coverage-guided CPU path but not an M3/M5-only renderer, NEON conversion, MetalFX,
mesh, or ray-tracing branch. The shipped binary therefore keeps one conservative M1-compatible
implementation and capability diagnostics.

## Distribution boundary

Generated listings, normalized programs, MAME traces, and native C remain under ignored private
build paths. The release build contains only the interpreter, hardware runtime, frontend, and
arm64 SDL3 framework. Packaging rejects the personal target and audits the final ZIP recursively
against the owner's ROM set when available.

The SDL xcframework uses a standard versioned framework with symlinks. CMake's generic directory
copy expands those links and leaves a layout that cannot be re-signed after thinning. The app
embedding step therefore preserves links with `cp -R`; packaging then thins the real binary,
re-signs the framework before the app, and uses `ditto --norsrc` so ZIPs contain no resource-fork
sidecar entries. `BUILD-INFO.json` deliberately records no local source or build path.
