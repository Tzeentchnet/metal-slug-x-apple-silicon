# Architecture

## Platform and execution envelope

The port targets Apple Silicon macOS only. CMake enforces:

- the `arm64` architecture;
- macOS 13.0 or newer;
- C17, C++17, and Objective-C++17;
- an SDL3 application bundle with a native Metal renderer.

Emulation, input polling, frontend updates, audio production, and Metal command encoding run
serially in the application loop. Emulator state therefore does not require locks. SDL's CoreAudio
backend consumes the pushed audio stream asynchronously, and the GPU executes committed Metal
command buffers asynchronously. Drawable availability bounds graphics work in flight.

## Build boundary

There are two intentionally different products:

1. **Personal build (`PD_RECOMPILED=ON`)**
   - reads the owner's verified arcade set;
   - normalizes P1/P2 and the US BIOS under `build-*/private/`;
   - runs static and optional MAME-guided analysis;
   - emits game-derived C only under the ignored build directory.
2. **Clean build (`PD_RECOMPILED=OFF`)**
   - contains no generated game code or game data;
   - executes the supplied P ROM through Musashi;
   - is the only input accepted by the release packager.

The ROM loader validates the runtime program, BIOS, graphics, Z80, and sample components before the
machine starts. A personal native program is selected only when both its P1 and BIOS SHA-256 values
match the loaded copy exactly. A clean build registers no native regions and always uses Musashi.

## Runtime data flow

The main runtime path is:

```text
verified ROM set
  -> Neo Geo bus and machine state
  -> native 68000 regions or Musashi fallback
  -> line-based 320x224 video and Z80/YM2610 audio
  -> BGRA Metal texture and SDL audio stream
  -> CAMetalLayer presentation and CoreAudio consumption
```

ROM data is loaded once and then treated as immutable. The shared `NgMachine` and `Cpu68k` state
contains the mutable machine and processor state. Windowed input is sampled immediately before each
due board frame, not once per display refresh.

## CPU, clocks, and scheduler

The 68000 state is shared by the native dispatcher and interpreter. Generated regions return to a
dispatcher at control-flow or hardware-event boundaries; missing regions fall back to one Musashi
instruction at a time. Both paths use the same bus and cycle-adjustment rules.

The outer machine scheduler uses the 12 MHz 68000 timeline for Neo Geo line starts, VBlank, raster
IRQ, watchdog, and synchronization boundaries. The sound subsystem uses a 24 MHz master-clock
domain internally:

- 68000: 12 MHz, or two master cycles;
- Z80: 4 MHz, or six master cycles;
- YM2610: 8 MHz, or three master cycles.

Z80 execution, YM2610 timers, and sample generation advance to each machine-event boundary. The
uPD4990A RTC derives its pulses and calendar advancement from the current 68000 cycle.

One board frame is exactly 202,752 cycles:

```text
202752 / 12000000 = 0.016896 seconds = 59.1856060606 Hz
```

Headless mode is unpaced. It is deterministic when the ROMs, inputs, initial state, relevant
environment, and RTC date are fixed; verification runs supply `--date` explicitly. Without a
supplied date, the emulated RTC starts from host local time.

Windowed mode keeps the board clock independent from `CAMetalLayer` presentation. The optional
turbo setting reduces 68000 instruction costs by 2x or 4x to remove original-game slowdown while
leaving the video, audio, and hardware-event cadence unchanged.

## Native application

SDL3 owns:

- application and window lifecycle;
- keyboard, gamepad, text input, rumble, and native folder dialogs;
- CoreAudio device opening and sample-rate conversion;
- platform and preference paths;
- surface and PNG helpers.

The window loop owns the frontend state, processes SDL events, advances every due board frame,
queues generated audio, encodes one Metal presentation, and then applies producer pacing.

## Video and presentation

The Neo Geo software renderer produces a 320x224 final frame. The original monitor stretches that
image to 4:3, so square-pixel and monitor-aspect presentation are separate options. CPU-side pixels
are ARGB8888 values whose little-endian byte layout matches `MTLPixelFormatBGRA8Unorm`, avoiding a
channel-conversion pass.

The dedicated Objective-C++ Metal renderer provides:

- `SDL_Metal_CreateView` and `CAMetalLayer`;
- one BGRA8 render pipeline with alpha blending;
- nearest, linear, and sharp integer-upscale sampling;
- texture-backed game frame, cartridge-font atlas, logo, and palette;
- rectangle and debug-text primitives for every frontend view;
- drawable readback for screenshots;
- Retina drawable sizes and a maximum of three drawables.

The normal path renders directly into the current drawable. Metal command buffers remain
asynchronous; screenshot readback and instrumented GPU timing wait for completion when their result
is needed.

Command Line Tools do not include `xcrun metal`, so the current build compiles its small, versioned
Metal shader source at startup. A full-Xcode release can replace that source with a bundled
metallib without changing the renderer API.

MetalFX is not part of the current renderer. Its suitability, required offscreen architecture, and
frame-interpolation tradeoffs are recorded in
[METALFX_INVESTIGATION.md](./METALFX_INVESTIGATION.md).

## Audio and pacing

The YM2610 produces stereo 16-bit samples at exactly 55,555 Hz. SDL3 converts this stream to the
CoreAudio device format and rate.

The queued stream targets about 50 ms. With V-sync enabled, a correction of at most 0.3 percent
absorbs host jitter without changing the long-term game clock. Additional latency safeguards:

- below about 10 ms queued, silence is inserted to avoid a device underrun;
- above about 150 ms queued, newly generated audio is discarded so latency cannot grow without
  bound;
- after window suspension, the queue is cleared and restarted with a 50 ms silence cushion.

At 60 Hz, a completed game frame is occasionally presented twice. Above the 59.185606 Hz board
rate, presentation duplicates the newest complete frame as needed; at lower display rates, more
than one board frame may complete between presentations and only the newest is shown. Display
refresh never changes average game or audio speed.

Hidden, minimized, or occluded windows suspend emulation and pause the audio device. Restoration
resets the host accumulator rather than attempting to catch up missed board time.

## State and persistence

The SDL preference directory stores:

- `mslugx.ini` configuration;
- battery-backed Neo Geo SRAM;
- numbered save-state slots;
- sound-browser metadata;
- the cached title-logo image.

Save states serialize the machine and 68000 state, RTC, Z80, YM2610 wrapper state, and ymfm state
between frames. They are intentionally same-format artifacts: a load is rejected unless its magic,
format version, and total serialized size match the current build. No cross-version compatibility
is promised. Loading a state discards pending generated audio so old samples are not replayed.

## Apple Silicon adaptation and observability

`mac_capabilities.mm` records the chip, model, GPU name, memory, core topology, Metal Apple family,
unified memory, argument-buffer tier, buffer limit, and recommended drawable count.
Marketing-name parsing exists only for diagnostics and mocked M1/M3/M5 tests. Correctness and
runtime selection never depend on a chip name.

The application exposes Instruments signpost regions for emulation, audio queuing, and Metal work.
Machine-readable benchmarks report:

- emulated and presented frame totals;
- wall, frame, CPU dispatch, video, and audio time;
- Metal encoding, GPU, and texture-upload time;
- drawable misses, display rate, memory, and Metal family.

Text traces additionally report pacing cadence, accumulator resets, mean audio queue depth,
underflow observations, and dropped-audio events.

## Verification and design records

Detailed evidence and procedures are kept outside this overview:

- [VERIFICATION.md](./VERIFICATION.md) describes deterministic, differential, screenshot, timing,
  and release checks.
- [TRANSLATION_FINDINGS.md](./TRANSLATION_FINDINGS.md) records implementation discoveries and
  measured decisions.
- [METALFX_INVESTIGATION.md](./METALFX_INVESTIGATION.md) evaluates MetalFX upscaling and frame
  interpolation.
