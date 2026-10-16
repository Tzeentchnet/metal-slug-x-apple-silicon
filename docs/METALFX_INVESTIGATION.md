# MetalFX investigation

Investigation date: 2026-10-16

## Summary

MetalFX frame interpolation is technically compatible with the port's fixed Neo Geo simulation
clock. It could generate one intermediate image between each pair of native game frames, raising
the maximum unique visual rate from 59.185606 Hz to 118.371212 Hz without running emulation or
audio more often.

It is not suitable for the default renderer yet. MetalFX requires accurate motion vectors and
depth in addition to the previous and current color images. The port currently produces only a
fully composited 320x224 CPU framebuffer. Generating the missing data would require significant
changes to the Neo Geo software renderer, and generated frames would add about half a source frame
of visible input latency.

The recommended policy is:

- keep the existing pixel, sharp, and smooth scaling paths;
- do not add MetalFX temporal or denoised upscaling;
- consider frame interpolation only as an opt-in macOS 26+ experiment for 120 Hz or faster
  displays;
- require runtime capability checks and retain the current renderer as the fallback.

## Current rendering and timing model

The machine scheduler advances one board frame every 202,752 68000 cycles:

```text
202752 / 12000000 = 0.016896 seconds = 59.1856060606 Hz
```

Windowed emulation accumulates host time and runs only the number of board frames that are due.
Presentation runs independently at the display cadence. At 60 Hz the newest complete board frame
is occasionally repeated. At 120 Hz it is normally presented twice. This separation is already
the correct foundation for frame interpolation: generated images would be additional presentation
work and would never invoke `ng_run_frame()` themselves.

The current graphics path is:

1. `src/neogeo/video.c` renders sprites, the fix layer, palette effects, and the game HUD into the
   final `ng.screen` array.
2. `src/port/window.c` uploads that 320x224 BGRA-compatible array to a Metal texture.
3. `src/port/metal_renderer.mm` samples the texture with the selected pixel, linear, or sharp
   filter.
4. Scanlines, debug information, menus, notices, and other frontend elements are composited.
5. The render pass writes directly into the `CAMetalDrawable` and presents it.

MetalFX cannot be inserted into that path immediately because its effects write to output textures,
not directly to the existing drawable composition. Frame interpolation would require an offscreen
scene path and explicit presentation scheduling.

See [ARCHITECTURE.md](./ARCHITECTURE.md) and the Metal conversion notes in
[TRANSLATION_FINDINGS.md](./TRANSLATION_FINDINGS.md) for the existing design.

## Relevant MetalFX features

| Feature | Minimum macOS | Required inputs | Fit |
|---|---:|---|---|
| Spatial scaler | 13.0 | Color | Technically easy, but no performance benefit |
| Temporal scaler | 13.0 | Color, motion, depth, jitter, history | Poor |
| Frame interpolator | 26.0 | Previous/current color, motion, depth, timing | Potentially useful |
| Temporal denoised scaler | 26.0 | Scene and ray-tracing G-buffer data | Not applicable |

The macOS 26 frame interpolator has an ordinary `MTLCommandBuffer` interface as well as a Metal 4
variant. The port would not need to migrate to Metal 4 to test interpolation.

The framework does not publish a reliable chip-name table for frame interpolation. Support needs
to be queried with `MTLFXFrameInterpolatorDescriptor.supportsDevice` on the actual `MTLDevice`.
This matches the port's existing policy of selecting behavior by capabilities rather than by
marketing chip names.

## Frame interpolation

### Expected benefit

The interpolator examines source frames N-1 and N and generates an image representing a time
between them. With one generated image per pair:

```text
59.185606 native frames/s * 2 = 118.371212 unique visual frames/s
```

This is a good match for a 120 Hz ProMotion display. It does not produce 144 or 240 unique images
per second because the API generates one additional image between two native images.

Simulation, collision, input polling, YM2610 generation, and machine timing would remain at the
original cadence. The feature would improve perceived motion only.

### Required data

The frame interpolator requires:

- the current color texture;
- the previous color texture, unless the macOS 27 internal-history mode is used;
- a depth texture;
- a two-component motion-vector texture;
- the time between the current and previous frames;
- motion-vector scale;
- near and far planes, field of view, and aspect ratio;
- jitter and history-reset state;
- an output texture;
- optional UI input and UI-composition state.

Apple recommends interpolation after tone mapping. If temporal upscaling is also present, the
upscaler can share its motion and depth data with the interpolator. This port has no such data
because it starts presentation with an already composited arcade framebuffer.

### Motion and depth generation

Supplying zero motion and constant depth would not provide convincing frame generation. Moving
sprites would tend to cross-fade, trail, or ghost instead of moving smoothly.

A native prototype could augment the software LSPC renderer:

- use the hardware sprite index as the initial cross-frame identity;
- compare current and previous sprite positions to produce per-pixel motion;
- use sprite list and draw order to produce an approximate depth value;
- mark the fix layer and static background with zero motion;
- reset history when sprite identity or scene continuity is uncertain.

This becomes complicated for:

- chained sprite backgrounds and scrolling scenery;
- zoomed and wrapped sprites;
- sprite animation that changes tile contents;
- sprites reused for unrelated objects;
- overlap, disappearance, and newly exposed pixels;
- per-line VRAM or raster changes;
- palette flashes and full-frame transitions;
- the fix layer and the game's HUD;
- frontend menus and debug overlays.

The final game image includes its score, ammunition, life counters, and other HUD graphics. These
cannot use MetalFX's separate UI path without first separating them from the emulated framebuffer.
Rapidly changing HUD digits are therefore a notable artifact risk.

### UI and scanlines

Apple describes three UI strategies:

1. **Composited UI:** provide both the scene and a scene-plus-UI texture so MetalFX can estimate
   the UI contribution.
2. **Offscreen UI:** render UI into a separate texture for MetalFX to composite.
3. **Every-frame UI:** draw UI separately for both generated and native presentations.

The second or third strategy is appropriate for frontend notices, menus, debug text, and other
port-owned elements. Scanlines should also be applied after interpolation so that the interpolator
does not warp them or interpret them as moving scene content.

The in-game HUD remains part of the scene unless the emulated video renderer is substantially
restructured.

### Presentation order and latency

After native frame N is available, the generated image between N-1 and N needs to be presented
first. Native frame N is then presented one output interval later. At this game's cadence:

```text
16.896 ms / 2 = 8.448 ms
```

The newest real game state is therefore displayed about 8.448 ms later than it is without frame
interpolation, plus the interpolation and composition cost. Input and simulation are not more
responsive; visible input response is slightly slower.

This tradeoff is important for an arcade action game. Frame interpolation should be off by default
and described as a smoothness-versus-latency option.

Presentation also needs more precise scheduling than the current newest-frame loop. The generated
and native textures must be submitted in order and at even intervals. The native 118.371212 Hz
result does not exactly equal a fixed 120 Hz mode, so variable refresh or regular cadence
adjustments are needed. Apple's Metal HUD guidance is to produce either one stable frame interval
or a regular pattern with no more than two interval buckets.

### History resets

Interpolation history needs to be reset for:

- startup and shutdown;
- window or drawable-size changes;
- display-mode changes;
- pause and resume;
- hidden or occluded window recovery;
- entering or leaving menus that stop the game;
- save-state load and machine reset;
- skipped or dropped native frames;
- abrupt scene cuts or full-screen transitions.

Failure to reset on these boundaries can mix unrelated images and produce severe artifacts.

## Upscaling

### Spatial scaling

The spatial scaler is the only MetalFX upscaler that can consume the current color texture without
new emulator data. It is available on the existing macOS 13 deployment target.

It does not solve a performance problem:

- the Neo Geo frame is already only 320x224;
- rendering that frame is inexpensive;
- the current sharp filter performs integer expansion and final fitting in the direct drawable
  pass;
- MetalFX would add an offscreen output texture and another GPU pass;
- the model may soften pixel edges, ring around high-contrast art, or invent detail;
- default 4:3 presentation includes a nonuniform aspect correction that is better controlled by
  the existing final sampling pass.

Spatial scaling could be exposed as a subjective experimental filter, but it should not replace
the pixel or sharp modes and should not be described as a performance optimization.

### Temporal scaling

Temporal scaling expects a conventional 3D rendering pipeline with:

- linear scene color;
- depth;
- motion vectors;
- subpixel jitter;
- temporal history;
- correct exposure;
- optional reactive masks for particles or transparency.

Apple recommends placing it before post-processing and tone mapping. The port starts with final
BGRA8 arcade pixels and has no expensive lower-resolution 3D rendering workload to avoid. Adding
the required data would cost more than it could save.

### Temporal denoised scaling

The denoised scaler additionally expects inputs such as normals, diffuse and specular albedo,
roughness, and optional ray hit distances. It is intended for noisy ray-traced rendering and has
no useful role in this renderer.

## Runtime probe

A capability probe was compiled against the installed macOS 26.5 SDK and run on the development
Apple M5. Results:

```text
device=Apple M5
spatial=yes
temporal=yes
temporal-scale=1.000...3.000
frame-interpolation=yes
frame-interpolation-metal4=yes
frame-interpolator-320x224=created
```

This confirms that the native game dimensions are accepted and that both classic Metal and Metal 4
interpolation are available on this machine. It does not establish M1 performance or support;
shipping code still needs the runtime `supportsDevice` check.

## Performance measurements

The existing 600-second run in `build-personal/timing-600-verified.json` recorded:

- 36,001 presented frames;
- 58.138 seconds of aggregate Metal GPU duration;
- 3.230 seconds of CPU Metal encoding;
- 1.207 seconds of texture-upload time;
- zero drawable misses.

Per presentation, this is approximately:

| Existing work | Mean time |
|---|---:|
| Metal GPU work | 1.615 ms |
| CPU Metal encoding | 0.090 ms |
| Game texture upload | 0.034 ms |

Synthetic effect-only benchmarks on the same M5 measured:

| MetalFX operation | Mean GPU time |
|---|---:|
| Spatial 320x224 to 640x448 | 0.228 ms |
| Spatial 320x224 to 1920x1344 | 0.528 ms |
| Frame interpolation at 320x224 | 0.197 ms |
| Frame interpolation at 1920x1344 with 320x224 motion/depth | 3.541 ms |

These tests used valid MetalFX objects and texture dimensions but synthetic texture contents. They
measure only the effect pass. They exclude:

- rendering the scene to an offscreen texture;
- generating useful motion and depth;
- compositing scanlines and UI;
- copying or drawing the selected result to a drawable;
- presentation synchronization;
- resizing and resource recreation.

The M5 result indicates that 1920x1344 interpolation is computationally feasible within the 8.448
ms output interval, but it is not a performance guarantee for M1 hardware or larger Retina
fullscreen outputs.

## Prototype design

If frame interpolation is pursued, the smallest responsible prototype is:

1. Link MetalFX while preserving the macOS 13 deployment target.
2. Guard all interpolation code with `@available(macOS 26.0, *)`.
3. Require `MTLFXFrameInterpolatorDescriptor.supportsDevice(device)`.
4. Enable it only on displays near 120 Hz or faster and keep it off by default.
5. Render the game scene into reusable offscreen textures rather than directly into the drawable.
6. Add 320x224 motion and depth outputs to the software video renderer.
7. Keep scanlines and frontend UI out of the interpolated scene.
8. Maintain previous/current native color textures and one generated output texture.
9. Present the generated texture and then the current native texture at half-frame intervals.
10. Reset history at every discontinuity listed above.
11. Fall back immediately to the current presentation path on unsupported hardware, allocation
    failure, interpolation failure, or presentation starvation.

The ordinary `MTLFXFrameInterpolator` interface should be used first. Migrating the project to
Metal 4 would expand the scope without improving the validity of the experiment.

## Acceptance criteria

Frame interpolation should not ship unless it satisfies all of the following:

### Correctness

- Emulation fingerprints remain identical with interpolation on and off.
- Audio production and queue behavior remain unchanged.
- No generated frame advances inputs, cheats, rumble, debug state, or game state.
- Save-state load, reset, pause, and resize always reset history.
- macOS 13 through 15 and unsupported devices retain the existing renderer.

### Image quality

- No objectionable sprite trails during rapid movement.
- No doubled edges during scrolling.
- No severe artifacts at sprite overlap or disocclusion.
- Explosions, flashes, palette changes, and animation cuts remain acceptable.
- In-game HUD digits and text do not warp noticeably.
- Frontend text and scanlines remain stable and sharp.
- Pixel, sharp, and smooth native modes remain unchanged.

### Pacing and latency

- The feature is disabled at 60 Hz.
- Generated and native frames are presented in the correct order.
- Frame intervals form a stable cadence with no random long-frame spikes.
- Added visible latency is measured and presented accurately to the user.
- The setting clearly communicates that it improves smoothness, not simulation rate.

### Performance

- Interpolation plus offscreen rendering and composition retains at least 25 percent headroom
  inside the 8.448 ms interval, approximately a 6.3 ms total GPU budget.
- The budget is met on the minimum supported M1 configuration at representative Retina sizes.
- Drawable misses and audio drops remain zero in sustained runs.
- New benchmark counters distinguish native, generated, repeated, and dropped presentations.

## Decision

MetalFX upscaling should not be added to the shipping renderer because it adds cost without
reducing meaningful work and is not naturally suited to pixel art.

MetalFX frame interpolation is the only feature with a plausible user-visible benefit. It is fast
enough to justify a quality prototype on current hardware, and the simulation/presentation
separation is already correct. Its missing motion/depth inputs, artifact risk, presentation
refactor, and added latency prevent recommending it as a default feature.

Proceed only as an optional experimental branch with measurable quality, latency, pacing, and M1
performance gates.

## Apple references

- [MetalFX](https://developer.apple.com/documentation/metalfx)
- [MTLFXFrameInterpolatorDescriptor](https://developer.apple.com/documentation/metalfx/mtlfxframeinterpolatordescriptor)
- [MTLFXFrameInterpolator](https://developer.apple.com/documentation/metalfx/mtlfxframeinterpolator)
- [MTLFXSpatialScalerDescriptor](https://developer.apple.com/documentation/metalfx/mtlfxspatialscalerdescriptor)
- [MTLFXTemporalScalerDescriptor](https://developer.apple.com/documentation/metalfx/mtlfxtemporalscalerdescriptor)
- [Applying temporal antialiasing and upscaling using MetalFX](https://developer.apple.com/documentation/metalfx/applying-temporal-antialiasing-and-upscaling-using-metalfx)
- [WWDC25: Go further with Metal 4 games](https://developer.apple.com/videos/play/wwdc2025/211/)
