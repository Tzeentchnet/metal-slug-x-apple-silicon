# Building on Apple Silicon

## Install the pinned environment

Install Apple Command Line Tools, then run:

```sh
./setup/bootstrap.sh
source setup/env.sh
```

The bootstrap downloads official, hash-checked CMake, Ninja, Python, and SDL3 artifacts into
`.tools/`. It probes installed macOS SDKs with a real arm64 compile-and-link test and records the
newest coherent SDK.

Optional analysis tools:

```sh
./setup/bootstrap.sh --analysis-tools
source setup/env.sh
python3 -I setup/build_mame.py
```

This builds a focused arm64 MAME `mslugx` oracle under `.tools/mame-build/`.

## Personal native build

Put your loose MAME set in `game/mslugx/` and `game/neogeo/`, then run:

```sh
cmake -S . -B build-personal \
  -DPD_RECOMPILED=ON \
  -DPD_GAME="$PWD/game" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build-personal -j 8
ctest --test-dir build-personal --output-on-failure
```

Private outputs live under `build-personal/private/`. To add dynamic coverage:

```sh
python3 -I tools/coverage.py \
  --mame "$PD_MAME" \
  --rompath "$PD_GAME" \
  --work build-personal/private/mame-coverage \
  --output build-personal/private/analysis/coverage.json \
  --seconds 180

cmake -S . -B build-personal -DPD_RECOMPILED=ON -DPD_GAME="$PD_GAME"
cmake --build build-personal -j 8
```

## Clean build

```sh
cmake -S . -B build-dist \
  -DPD_RECOMPILED=OFF \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES=arm64
cmake --build build-dist -j 8
```

Only this build may be packaged for distribution.

## Benchmarks

```sh
python3 -I tools/benchmark.py \
  --app build-personal/src/mslugx.app/Contents/MacOS/mslugx \
  --roms game \
  --frames 1800 \
  --window-seconds 10 \
  --output build-personal/benchmark.json
```

Use `PD_CAPABILITIES=1` to print live CPU and Metal capabilities. Use Instruments with subsystem
`io.github.mslugx.recomp` and category `frame` for signposts.
